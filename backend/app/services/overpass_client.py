"""Client Overpass/Nominatim per trovare aziende e POI in Puglia."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "BioTitan-CRM-Scraper/1.0 (lead acquisition)"

# Tag OSM più comuni. Le chiavi devono corrispondere alle categorie inviate dal CRM.
CATEGORIA_OSM: dict[str, list[str]] = {
    "edilizia": [
        'nwr["office"="construction_company"]["name"]',
        'nwr["craft"="builder"]["name"]',
        'nwr["craft"="carpenter"]["name"]',
        'nwr["craft"="plumber"]["name"]',
        'nwr["craft"="electrician"]["name"]',
        'nwr["craft"="roofer"]["name"]',
        'nwr["craft"="stonemason"]["name"]',
        'nwr["craft"="glazier"]["name"]',
        'nwr["craft"="hvac"]["name"]',
        'nwr["shop"="hardware"]["name"]',
        'nwr["shop"="doityourself"]["name"]',
        'nwr["shop"="building_materials"]["name"]',
        'nwr["name"~"edil|costruzion|impresa edile|murator|serrament|cartongess|idraulic|elettric",i]',
    ],
    "fotovoltaico": [
        'nwr["shop"="solar"]["name"]',
        'nwr["craft"="solar_panel"]["name"]',
        'nwr["office"="energy"]["name"]',
        'nwr["power"="generator"]["generator:source"="solar"]["name"]',
        'nwr["name"~"fotovolta|fotovoltaic|pannelli solari|energia solare|solar",i]',
    ],
    "pulizie": [
        'nwr["craft"="cleaner"]["name"]',
        'nwr["office"="cleaning"]["name"]',
        'nwr["shop"="cleaning"]["name"]',
        'nwr["name"~"pulizie|pulizia|sanificaz|igienizz|cleaning|facility",i]',
    ],
    "imbarcazioni": [
        'nwr["shop"="boat"]["name"]',
        'nwr["craft"="boatbuilder"]["name"]',
        'nwr["shop"="marine"]["name"]',
        'nwr["leisure"="marina"]["name"]',
        'nwr["name"~"nautica|barca|barche|cantier|marine",i]',
    ],
    "pavimentazioni": [
        'nwr["shop"="flooring"]["name"]',
        'nwr["shop"="tiles"]["name"]',
        'nwr["craft"="tiler"]["name"]',
        'nwr["name"~"paviment|piastrell|ceramic|parquet|marmo",i]',
    ],
    "default": [
        'nwr["office"="company"]["name"]',
        'nwr["shop"]["name"]',
        'nwr["craft"]["name"]',
        'nwr["industrial"]["name"]',
    ],
}


def _ql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


async def _resolve_area_id(comune: Optional[str], provincia: str) -> Optional[int]:
    """Usa Nominatim per ottenere la relazione amministrativa corretta."""
    if comune:
        q = f"{comune}, {provincia}, Puglia, Italy"
    else:
        q = f"{provincia}, Puglia, Italy"
    params = {"q": q, "format": "jsonv2", "limit": 8, "countrycodes": "it"}
    try:
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(NOMINATIM_URL, params=params)
            resp.raise_for_status()
            rows = resp.json()
        wanted = _normalizza_testo(comune or provincia)
        for row in rows:
            osm_type = row.get("osm_type")
            osm_id = row.get("osm_id")
            if osm_type != "relation" or not osm_id:
                continue
            name = _normalizza_testo(row.get("name") or row.get("display_name") or "")
            if wanted and wanted not in name and name not in wanted:
                continue
            return int(osm_id)
        # Se Nominatim non restituisce un nome perfetto, accetta la prima relazione.
        for row in rows:
            if row.get("osm_type") == "relation" and row.get("osm_id"):
                return int(row["osm_id"])
    except Exception as exc:
        logger.warning("Nominatim non disponibile per %s/%s: %s", provincia, comune or "*", exc)
    return None


def _normalizza_testo(value: str) -> str:
    value = (value or "").lower()
    return re.sub(r"[^a-z0-9àèéìòù' ]+", " ", value).strip()


def _query_area(comune: Optional[str], provincia: str, tags: list[str], timeout: int = 60, area_id: Optional[int] = None) -> str:
    if area_id:
        area_filter = f"area({3600000000 + area_id})->.searchArea;"
    elif comune:
        name = _ql_escape(comune)
        area_filter = f'area["name"="{name}"]["boundary"="administrative"]["admin_level"~"8|9"]->.searchArea;'
    else:
        name = _ql_escape(provincia)
        area_filter = f'area["name"="{name}"]["boundary"="administrative"]["admin_level"="6"]->.searchArea;'
    parts = [f"{tag}(area.searchArea)" for tag in tags]
    return f"[out:json][timeout:{timeout}];\n{area_filter}\n(\n  " + ";\n  ".join(parts) + ";\n);\nout center tags;"


def _keyword_fallback_tags(categorie: list[str]) -> list[str]:
    # Fallback leggero: cerca il nome dell'attività senza scaricare tutti i negozi della provincia.
    patterns = {
        "edilizia": "edil|costruzion|impresa edile|murator|serrament|idraulic|elettric",
        "fotovoltaico": "fotovolta|fotovoltaic|energia solare|pannelli solari|solar",
        "pulizie": "pulizie|pulizia|sanificaz|igienizz|cleaning|facility",
        "imbarcazioni": "nautica|cantier|barca|barche|marine",
        "pavimentazioni": "paviment|piastrell|parquet|marmo|ceramic",
    }
    out = []
    for c in categorie:
        p = patterns.get(c)
        if p:
            out.append(f'nwr["name"~"{p}",i]')
    return out


def _normalize_element(el: dict) -> Optional[dict[str, Any]]:
    tags = el.get("tags") or {}
    nome = tags.get("name") or tags.get("brand") or tags.get("operator")
    if not nome:
        return None
    lat = el.get("lat") or (el.get("center") or {}).get("lat")
    lon = el.get("lon") or (el.get("center") or {}).get("lon")
    parts = []
    if tags.get("addr:street"):
        street = tags["addr:street"]
        if tags.get("addr:housenumber"):
            street = f"{street} {tags['addr:housenumber']}"
        parts.append(street)
    if tags.get("addr:postcode"):
        parts.append(tags["addr:postcode"])
    if tags.get("addr:city"):
        parts.append(tags["addr:city"])
    return {
        "nome": str(nome).strip(),
        "indirizzo": ", ".join(parts) if parts else None,
        "comune": tags.get("addr:city"),
        "telefono": tags.get("phone") or tags.get("contact:phone"),
        "email": tags.get("email") or tags.get("contact:email"),
        "sito_web": tags.get("website") or tags.get("contact:website") or tags.get("url"),
        "lat": float(lat) if lat is not None else None,
        "lon": float(lon) if lon is not None else None,
        "fonte": "openstreetmap",
        "url_fonte": f"https://www.openstreetmap.org/{el.get('type', 'node')}/{el.get('id')}",
        "osm_tags": {k: v for k, v in tags.items() if k != "name"},
    }


async def _run_query(query: str) -> list[dict]:
    last_error = None
    for url in OVERPASS_URLS:
        try:
            async with httpx.AsyncClient(timeout=75.0, headers={"User-Agent": USER_AGENT}) as client:
                resp = await client.post(url, data={"data": query})
                resp.raise_for_status()
                data = resp.json()
                return data.get("elements") or []
        except Exception as exc:
            last_error = exc
            logger.warning("Overpass %s fallito: %s", url, exc)
    raise RuntimeError(f"Tutti gli endpoint Overpass non sono raggiungibili: {last_error}")


async def cerca_aziende(provincia: str, comune: Optional[str] = None, categorie: Optional[list[str]] = None, max_results: int = 200) -> list[dict[str, Any]]:
    cats = [str(c).lower().strip() for c in (categorie or []) if c]
    tags: list[str] = []
    for c in cats:
        tags.extend(CATEGORIA_OSM.get(c, []))
    if not tags:
        tags = CATEGORIA_OSM["default"]
    tags = list(dict.fromkeys(tags))

    area_id = await _resolve_area_id(comune, provincia)
    query = _query_area(comune, provincia, tags, area_id=area_id)
    try:
        elements = await _run_query(query)
    except Exception:
        # Seconda possibilità: query solo per parole chiave, molto più leggera.
        fallback_tags = _keyword_fallback_tags(cats)
        if not fallback_tags:
            raise
        elements = await _run_query(_query_area(comune, provincia, fallback_tags, timeout=45, area_id=area_id))

    # Se la query specifica è valida ma non produce nulla, la causa più comune è il mapping OSM.
    # Eseguiamo un fallback per nome/categoria prima di dichiarare zero risultati.
    if not elements:
        fallback_tags = _keyword_fallback_tags(cats)
        if fallback_tags:
            try:
                elements = await _run_query(_query_area(comune, provincia, fallback_tags, timeout=45, area_id=area_id))
            except Exception as exc:
                logger.warning("Fallback keyword fallito: %s", exc)

    risultati: list[dict[str, Any]] = []
    seen: set[str] = set()
    for el in elements:
        item = _normalize_element(el)
        if not item:
            continue
        key = _normalizza_testo(item["nome"])
        if key in seen:
            continue
        seen.add(key)
        if comune and not item.get("comune"):
            item["comune"] = comune
        if not item.get("provincia"):
            item["provincia"] = provincia
        risultati.append(item)
        if len(risultati) >= max_results:
            break

    logger.info("Ricerca aziende %s/%s categorie=%s → %d risultati", provincia, comune or "*", cats, len(risultati))
    return risultati
