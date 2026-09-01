"""
Analisi automatica del sito aziendale: recupera contatti, descrizione,
social e attività principali dalla homepage + pagine contatti/about.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(?:\+39\s?)?(?:0\d{1,3}[\s\-/]?)?\d{5,10}|\b3\d{2}[\s\-]?\d{6,7}\b"
)
PIVA_RE = re.compile(r"(?:P\.?\s*IVA|Partita\s*IVA|VAT)[:\s]*([0-9]{11})", re.I)
CF_RE = re.compile(r"(?:C\.?\s*F\.?|Codice\s*Fiscale)[:\s]*([A-Z0-9]{11,16})", re.I)

SOCIAL_PATTERNS = {
    "facebook": re.compile(r"facebook\.com/[\w.\-]+", re.I),
    "instagram": re.compile(r"instagram\.com/[\w.\-]+", re.I),
    "linkedin": re.compile(r"linkedin\.com/(?:company|in)/[\w.\-]+", re.I),
    "youtube": re.compile(r"youtube\.com/(?:c|channel|user)/[\w.\-]+", re.I),
    "twitter": re.compile(r"(?:twitter|x)\.com/[\w.\-]+", re.I),
}


def _normalize_url(url: str) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        p = urlparse(url)
        if not p.netloc:
            return None
        return url
    except Exception:
        return None


def _extract_from_html(html: str, base_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    # Rimuovi script/style
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(" ", strip=True)

    emails = list(dict.fromkeys(EMAIL_RE.findall(text)))
    # filtra email generiche di tracking
    emails = [e for e in emails if not any(x in e.lower() for x in ("example.", "sentry", "wixpress", "wordpress", "google"))]

    phones = list(dict.fromkeys(m.group(0).strip() for m in PHONE_RE.finditer(text)))
    phones = [p for p in phones if len(re.sub(r"\D", "", p)) >= 8]

    piva = None
    m = PIVA_RE.search(text)
    if m:
        piva = m.group(1)

    cf = None
    m = CF_RE.search(text)
    if m:
        cf = m.group(1).upper()

    social: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        for name, pat in SOCIAL_PATTERNS.items():
            if name not in social and pat.search(href):
                social[name] = href if href.startswith("http") else urljoin(base_url, href)

    # Descrizione: meta description o primi paragrafi
    descrizione = None
    meta = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
    if meta and meta.get("content"):
        descrizione = meta["content"].strip()[:500]
    if not descrizione:
        for p in soup.find_all("p"):
            t = p.get_text(" ", strip=True)
            if len(t) > 80:
                descrizione = t[:500]
                break

    # Link a pagine contatti / about
    extra_paths = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        testo = (a.get_text() or "").lower()
        if any(k in href or k in testo for k in ("contatt", "contact", "about", "chi-siamo", "chi_siamo", "azienda", "company")):
            full = urljoin(base_url, a["href"])
            if urlparse(full).netloc == urlparse(base_url).netloc:
                extra_paths.add(full.split("#")[0])

    return {
        "email": emails[0] if emails else None,
        "emails": emails[:5],
        "telefono": phones[0] if phones else None,
        "telefoni": phones[:5],
        "partita_iva": piva,
        "codice_fiscale": cf,
        "social": social,
        "descrizione": descrizione,
        "extra_urls": list(extra_paths)[:4],
    }


async def analizza_sito(url: str, timeout: float = 12.0) -> dict[str, Any]:
    """
    Scarica homepage (+ eventuali pagine contatti/about) e restituisce
    contatti, social, descrizione, P.IVA se presenti.
    """
    url = _normalize_url(url)
    if not url:
        return {}

    result: dict[str, Any] = {"sito_web": url, "fonte": "sito_aziendale"}
    headers = {
        "User-Agent": "BioTitanLeadAgent/1.0 (+https://biotitan.it; lead enrichment; respectful)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.5",
    }

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
            verify=True,
        ) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                logger.info("Sito %s status %s", url, resp.status_code)
                return result

            data = _extract_from_html(resp.text, str(resp.url))
            result.update({k: v for k, v in data.items() if k != "extra_urls" and v})

            # Seconda passata su 1-2 pagine contatti/about
            for extra in data.get("extra_urls", [])[:2]:
                try:
                    r2 = await client.get(extra)
                    if r2.status_code < 400:
                        d2 = _extract_from_html(r2.text, str(r2.url))
                        if not result.get("email") and d2.get("email"):
                            result["email"] = d2["email"]
                        if not result.get("telefono") and d2.get("telefono"):
                            result["telefono"] = d2["telefono"]
                        if not result.get("partita_iva") and d2.get("partita_iva"):
                            result["partita_iva"] = d2["partita_iva"]
                        if not result.get("codice_fiscale") and d2.get("codice_fiscale"):
                            result["codice_fiscale"] = d2["codice_fiscale"]
                        if d2.get("social"):
                            social = result.get("social") or {}
                            social.update(d2["social"])
                            result["social"] = social
                        if not result.get("descrizione") and d2.get("descrizione"):
                            result["descrizione"] = d2["descrizione"]
                except Exception as e:
                    logger.debug("Extra page %s fallita: %s", extra, e)

    except Exception as e:
        logger.warning("Analisi sito %s fallita: %s", url, e)
        result["errore"] = str(e)[:200]

    return result
