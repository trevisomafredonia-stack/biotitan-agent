"""Client Overpass più resistente per Render free tier."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "BioTitan-CRM/1.0"

CATEGORIA_OSM = {
    "edilizia": [
        'nwr["craft"="builder"]["name"]',
        'nwr["craft"="carpenter"]["name"]',
        'nwr["craft"="plumber"]["name"]',
        'nwr["craft"="electrician"]["name"]',
        'nwr["shop"="hardware"]["name"]',
        'nwr["shop"="doityourself"]["name"]',
        'nwr["name"~"edil|costruzion|impresa|murator|idraulic|elettric|serrament",i]',
    ],
    "fotovoltaico": [
        'nwr["name"~"fotovolta|solar|energia solare|pannelli",i]',
    ],
    "pulizie": [
        'nwr["name"~"pulizie|pulizia|sanificaz|cleaning",i]',
    ],
    "imbarcazioni": [
        'nwr["name"~"nautica|barca|cantier|marine",i]',
    ],
    "pavimentazioni": [
        'nwr["name"~"paviment|piastrell|ceramic|parquet",i]',
    ],
    "default": [
        'nwr["office"="company"]["name"]',
        'nwr["shop"]["name"]',
        'nwr["craft"]["name"]',
    ],
}


def _normalizza(v: str) -> str:
    return re.sub(r"[^a-z0-9àèéìòù ]+", " ", (v or "").lower()).strip()


async def _resolve_area_id(comune: Optional[str], provincia: str) -> Optional[int]:
    q = f"{comune}, {provincia}, Italy" if comune else f"{provincia}, Puglia, Italy"
    try:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": USER_AGENT}) as c:
            r = await c.get(NOMINATIM_URL, params={"q": q, "format": "json", "limit": 3, "countrycodes": "it"})
            r.raise_for_status()
            for row in r.json():
                if row.get("osm_type") == "relation" and row.get("osm_id"):
                    return int(row["osm_id"])
    except Exception as e:
        logger.warning("Nominatim area fallito: %s", e)
    return None


def _build_query(comune, provincia, tags, area_id=None, timeout=35):
    if area_id:
        area = f"area({3600000000 + area_id})->.a;"
    elif comune:
        area = f'area["name"="{comune}"]["admin_level"~"8|9"]->.a;'
    else:
        area = f'area["name"="{provincia}"]["admin_level"="6"]->.a;'
    parts = [f"{t}(area.a)" for t in tags]
    return f"[out:json][timeout:{timeout}];{area}({';'.join(parts)};);out center tags;"


async def _try_overpass(query: str) -> list:
    for url in OVERPASS_URLS:
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=50, headers={"User-Agent": USER_AGENT}) as c:
                    r = await c.post(url, data={"data": query})
                    if r.status_code == 200:
                        return r.json().get("elements") or []
            except Exception as e:
                logger.warning("Overpass %s tentativo %s: %s", url, attempt + 1, str(e)[:80])
            await asyncio.sleep(1)
    return []


def _normalize_el(el: dict) -> Optional[dict]:
    tags = el.get("tags") or {}
    nome = tags.get("name") or tags.get("brand") or tags.get("operator")
    if not nome:
        return None
    lat = el.get("lat") or (el.get("center") or {}).get("lat")
    lon = el.get("lon") or (el.get("center") or {}).get("lon")
    indirizzo = []
    if tags.get("addr:street"):
        s = tags["addr:street"]
        if tags.get("addr:housenumber"):
            s += " " + tags["addr:housenumber"]
        indirizzo.append(s)
    if tags.get("addr:city"):
        indirizzo.append(tags["addr:city"])
    return {
        "nome": nome.strip(),
        "indirizzo": ", ".join(indirizzo) or None,
        "comune": tags.get("addr:city"),
        "telefono": tags.get("phone") or tags.get("contact:phone"),
        "email": tags.get("email") or tags.get("contact:email"),
        "sito_web": tags.get("website") or tags.get("contact:website"),
        "lat": float(lat) if lat else None,
        "lon": float(lon) if lon else None,
        "fonte": "openstreetmap",
        "url_fonte": f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}",
    }


async def cerca_aziende(provincia: str, comune: Optional[str] = None, categorie: Optional[list[str]] = None, max_results: int = 120) -> list[dict[str, Any]]:
    cats = [c.lower().strip() for c in (categorie or []) if c]
    tags = []
    for c in cats:
        tags.extend(CATEGORIA_OSM.get(c, []))
    if not tags:
        tags = CATEGORIA_OSM["default"]
    tags = list(dict.fromkeys(tags))

    area_id = await _resolve_area_id(comune, provincia)
    query = _build_query(comune, provincia, tags, area_id)

    elements = await _try_overpass(query)

    # fallback molto leggero solo nomi
    if not elements and cats:
        light = [f'nwr["name"~"{cats[0]}",i]']
        elements = await _try_overpass(_build_query(comune, provincia, light, area_id, timeout=25))

    risultati = []
    seen = set()
    for el in elements:
        item = _normalize_el(el)
        if not item:
            continue
        key = _normalizza(item["nome"])
        if key in seen:
            continue
        seen.add(key)
        if comune and not item.get("comune"):
            item["comune"] = comune
        item["provincia"] = provincia
        risultati.append(item)
        if len(risultati) >= max_results:
            break

    logger.info("Overpass %s/%s → %d risultati", provincia, comune or "*", len(risultati))
    return risultati
