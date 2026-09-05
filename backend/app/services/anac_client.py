import re
from datetime import datetime
from typing import Any

import httpx

CKAN_BASE = "https://dati.anticorruzione.it/opendata/api/3/action"

# Un User-Agent "da browser": il portale ANAC blocca le richieste che
# sembrano provenire da script/bot senza questa intestazione.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Limite di sicurezza: non scaricare risorse più grandi di questo,
# per non esaurire la memoria di un servizio Render free (~512MB).
MAX_RESOURCE_BYTES = 60 * 1024 * 1024  # 60 MB

# Parole chiave nell'oggetto/CPV del bando che segnalano rilevanza per
# BioTitan (pulizie, facility, manutenzione, trattamenti superficiali).
KEYWORDS_RILEVANTI = [
    "pulizia", "pulizie", "sanificazione", "igien", "facility",
    "manutenzione", "fotovoltaic", "pannelli solari", "verde pubblico",
    "disinfestazione", "derattizzazione", "vetri", "pavimentazion",
]


async def _ckan_action_get(client: httpx.AsyncClient, action: str) -> dict:
    """Le action CKAN senza parametri (es. package_list) funzionano in GET."""
    r = await client.get(f"{CKAN_BASE}/{action}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


async def _ckan_action_post(client: httpx.AsyncClient, action: str, payload: dict) -> dict:
    """Le action CKAN con parametri vanno in POST con body JSON: il WAF
    rifiuta le richieste GET con query string."""
    r = await client.post(
        f"{CKAN_BASE}/{action}",
        headers={**HEADERS, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _e_recente_e_rilevante(url_risorsa: str) -> bool:
    nome = url_risorsa.lower()
    return "delta" in nome or "bandi" in nome or "cig" in nome


async def _trova_risorse_delta(client: httpx.AsyncClient) -> list[str]:
    """Individua le risorse JSON 'delta' più recenti (dataset bandi/cig),
    invece di scaricare gli enormi dataset FULL annuali."""
    lista = await _ckan_action_get(client, "package_list")
    nomi_dataset = lista.get("result", [])

    anno_corrente = str(datetime.utcnow().year)
    candidati = [
        n for n in nomi_dataset
        if ("bandi" in n or "cig" in n) and (anno_corrente in n or "delta" in n)
    ]

    urls_json: list[str] = []
    for nome in candidati[:8]:  # non interrogare l'intero catalogo: limite di sicurezza
        try:
            dettaglio = await _ckan_action_post(client, "package_show", {"id": nome})
        except httpx.HTTPStatusError:
            continue
        for risorsa in dettaglio.get("result", {}).get("resources", []):
            fmt = (risorsa.get("format") or "").lower()
            url = risorsa.get("url") or ""
            if fmt == "json" and _e_recente_e_rilevante(url):
                urls_json.append(url)
    return urls_json


async def fetch_recent_releases() -> list[dict[str, Any]]:
    """Recupera le release OCDS più recenti dalle risorse 'delta' di ANAC
    (solo i record nuovi/aggiornati), filtrate per rilevanza BioTitan e
    per scadenza non ancora passata (bandi ancora aperti)."""
    async with httpx.AsyncClient() as client:
        urls = await _trova_risorse_delta(client)

        release_trovate: list[dict[str, Any]] = []
        oggi = datetime.utcnow()

        for url in urls:
            corpo = b""
            try:
                async with client.stream("GET", url, headers=HEADERS, timeout=60) as resp:
                    resp.raise_for_status()
                    lunghezza = int(resp.headers.get("content-length") or 0)
                    if lunghezza and lunghezza > MAX_RESOURCE_BYTES:
                        continue  # risorsa troppo grande: salta, non rischiare la memoria
                    async for chunk in resp.aiter_bytes():
                        corpo += chunk
                        if len(corpo) > MAX_RESOURCE_BYTES:
                            corpo = b""
                            break
                if not corpo:
                    continue
                import json as _json
                dati = _json.loads(corpo)
            except Exception:
                continue  # una risorsa che fallisce non deve bloccare le altre

            releases = dati.get("releases", dati if isinstance(dati, list) else [])
            for release in releases:
                tender = release.get("tender", {}) or {}
                testo = (tender.get("title", "") + " " + tender.get("description", "")).lower()
                if not any(k in testo for k in KEYWORDS_RILEVANTI):
                    continue

                scadenza = tender.get("tenderPeriod", {}).get("endDate")
                if scadenza:
                    try:
                        if datetime.fromisoformat(scadenza.replace("Z", "+00:00")).replace(tzinfo=None) < oggi:
                            continue  # bando già scaduto: non interessa per "trova bandi aperti"
                    except ValueError:
                        pass

                release_trovate.append(release)

        return release_trovate


def release_to_bando_dict(release: dict[str, Any]) -> dict[str, Any]:
    """Traduce una release OCDS nei campi usati dal nostro modello Bando."""
    tender = release.get("tender", {}) or {}
    awards = release.get("awards", []) or []
    award = awards[0] if awards else {}

    cig = None
    for tag in release.get("tag", []) or []:
        candidato = tag.get("id") if isinstance(tag, dict) else None
        if candidato and re.match(r"^[A-Z0-9]{10}$", str(candidato)):
            cig = candidato
            break

    return {
        "titolo": tender.get("title") or "Bando senza titolo",
        "cig": cig,
        "fonte": "anac_ocds_delta",
        "link": (tender.get("documents") or [{}])[0].get("url"),
        "stato": "aggiudicato" if award else "pubblicato",
        "data_pubblicazione": tender.get("tenderPeriod", {}).get("startDate"),
        "data_scadenza": tender.get("tenderPeriod", {}).get("endDate"),
        "aggiudicatario": (award.get("suppliers") or [{}])[0].get("name") if award else None,
        "importo_aggiudicazione": (award.get("value") or {}).get("amount"),
    }
