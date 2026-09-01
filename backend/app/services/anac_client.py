"""
Client per la fonte nazionale ufficiale: il portale Open Data di ANAC
(dati.anticorruzione.it), che espone i contratti pubblici in formato
OCDS (Open Contracting Data Standard) tramite API aggiornate in tempo reale.

Usiamo questa fonte al posto di uno scraper HTML perché:
- i dati sono strutturati (JSON), quindi non serve fare parsing fragile di pagine web
- sono dati aperti pubblicati esplicitamente per il riuso, quindi nessun problema
  di termini d'uso legati allo scraping
- includono già aggiudicatario, importo, ribasso, stazione appaltante

NOTA IMPORTANTE: l'URL esatto dell'endpoint API e i parametri di query vanno
verificati sullo swagger ufficiale pubblicato su dati.anticorruzione.it/opendata/ocds_it
prima del primo utilizzo in produzione: ANAC può aggiornare la struttura del portale.
Questo modulo prevede un punto unico (BASE_URL) da aggiornare se cambia.
"""

from datetime import datetime
from typing import Any

import httpx

BASE_URL = "https://dati.anticorruzione.it/superset/api/v1"  # verificare su swagger ufficiale


async def fetch_recent_releases(cpv_filter: list[str] | None = None) -> list[dict[str, Any]]:
    """
    Recupera le release OCDS più recenti. In assenza di un filtro CPV,
    torna i bandi generici: il filtro andrebbe impostato sui codici CPV
    rilevanti per BioTitan (trattamenti superficiali, nanotecnologie,
    manutenzione, edilizia) una volta identificati dallo swagger ufficiale.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        # Placeholder di chiamata reale: da adattare ai parametri esatti
        # documentati nello swagger (paginazione, filtro data, filtro CPV).
        resp = await client.get(f"{BASE_URL}/ocds/releases", params={"cpv": cpv_filter})
        resp.raise_for_status()
        return resp.json().get("releases", [])


def release_to_bando_dict(release: dict[str, Any]) -> dict[str, Any]:
    """Traduce una release OCDS nei campi usati dal nostro modello Bando."""
    tender = release.get("tender", {})
    awards = release.get("awards", [])
    award = awards[0] if awards else {}

    return {
        "titolo": tender.get("title", "Bando senza titolo"),
        "cig": release.get("tag", [{}])[0].get("id") if release.get("tag") else None,
        "fonte": "anac_ocds",
        "link": tender.get("documents", [{}])[0].get("url") if tender.get("documents") else None,
        "stato": "aggiudicato" if award else "pubblicato",
        "data_pubblicazione": tender.get("tenderPeriod", {}).get("startDate"),
        "data_scadenza": tender.get("tenderPeriod", {}).get("endDate"),
        "aggiudicatario": award.get("suppliers", [{}])[0].get("name") if award.get("suppliers") else None,
        "importo_aggiudicazione": award.get("value", {}).get("amount"),
    }
