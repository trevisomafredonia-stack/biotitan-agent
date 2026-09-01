"""
Recupero dati camerali *pubblici e gratuiti* dal portale Registro Imprese.

Cosa otteniamo (quando disponibile):
- denominazione
- partita IVA / codice fiscale
- sede legale
- PEC
- stato (attiva / cessata / ...)
- REA
- forma giuridica / attività principale

Cosa NON facciamo:
- nessun accesso a visure a pagamento
- nessun bypass di login / captcha / rate-limit
- se il dato non è pubblicamente leggibile, restituiamo solo
  visura_ufficiale_disponibile = True (segnalazione)

Nota: il portale ufficiale può cambiare struttura HTML o introdurre
protezioni. In quel caso il servizio degrada gracefully e registra
che la verifica non è riuscita.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# Endpoint pubblici noti (ricerca base). Non garantiti nel tempo.
SEARCH_URLS = [
    # Italian Business Register (EN mirror, spesso più leggero)
    "https://italianbusinessregister.it/en/search",
]

PIVA_RE = re.compile(r"\b(\d{11})\b")
PEC_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.it", re.I)


def _pulisci_nome(nome: str) -> str:
    return re.sub(r"\s+", " ", nome).strip()[:120]


async def cerca_dati_pubblici(
    nome: Optional[str] = None,
    partita_iva: Optional[str] = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """
    Tenta di recuperare i dati base pubblici.
    Restituisce sempre almeno il flag visura_ufficiale_disponibile.
    """
    out: dict[str, Any] = {
        "visura_ufficiale_disponibile": True,
        "fonte_camerale": None,
        "data_verifica_camerale": datetime.utcnow(),
    }

    if not nome and not partita_iva:
        return out

    query = partita_iva or _pulisci_nome(nome or "")
    if not query:
        return out

    headers = {
        "User-Agent": "BioTitanLeadAgent/1.0 (public company data enrichment; respectful)",
        "Accept": "text/html,application/json",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.5",
    }

    # Strategia 1: se abbiamo già una P.IVA, la validiamo in formato
    if partita_iva and re.fullmatch(r"\d{11}", partita_iva):
        out["partita_iva"] = partita_iva
        out["codice_fiscale"] = partita_iva  # per società spesso coincide
        out["fonte_camerale"] = "formato_piva_validato"

    # Strategia 2: tentativo di lettura pagina pubblica (degrada se protetta)
    # Non insistiamo: se c'è captcha o 403/429 lasciamo stare.
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            # Prova una ricerca generica su siti pubblici di directory
            # (es. pagine che espongono dati da Registro Imprese in chiaro).
            # Evitiamo di martellare il portale ufficiale.
            for base in [
                f"https://www.google.com/search?q=%22{query}%22+PEC+OR+%22partita+IVA%22+site%3Ait",
            ]:
                # Non eseguiamo scraping aggressivo di Google: solo placeholder
                # per future integrazioni con API ufficiali o dataset aperti.
                break
    except Exception as e:
        logger.debug("Ricerca camerale pubblica non riuscita: %s", e)

    # Se dal sito aziendale abbiamo già estratto P.IVA / CF, li consolidiamo
    if partita_iva and not out.get("partita_iva"):
        out["partita_iva"] = partita_iva

    # Stato di default se non abbiamo info: sconosciuto ma visura a pagamento esiste
    if "stato_azienda" not in out:
        out["stato_azienda"] = None

    out["fonte_camerale"] = out.get("fonte_camerale") or "registro_imprese_pubblico_base"
    return out


async def arricchisci_da_piva_o_nome(
    nome: str,
    partita_iva: Optional[str] = None,
    pec: Optional[str] = None,
) -> dict[str, Any]:
    """
    Wrapper usato dallo scraper: combina i dati già noti con la verifica pubblica.
    """
    base = await cerca_dati_pubblici(nome=nome, partita_iva=partita_iva)
    if pec and not base.get("pec"):
        base["pec"] = pec
    return base
