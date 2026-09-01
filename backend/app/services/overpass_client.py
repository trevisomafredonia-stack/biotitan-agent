"""
Client Overpass API per recuperare punti di interesse / aziende
da OpenStreetMap in un comune o provincia della Puglia.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Mapping categorie CRM → tag OSM più utili
CATEGORIA_OSM: dict[str, list[str]] = {
    "edilizia": [
        'nwr["shop"="doityourself"]',
        'nwr["craft"="builder"]',
        'nwr["office"="construction_company"]',
        'nwr["building"="commercial"]["name"]',
        'nwr["shop"="hardware"]',
        'nwr["craft"="carpenter"]',
        'nwr["craft"="electrician"]',
        'nwr["craft"="plumber"]',
    ],
    "fotovoltaico": [
        'nwr["shop"="solar"]',
        'nwr["craft"="solar_panel"]',
        'nwr["office"="energy"]',
        'nwr["power"="generator"]["generator:source"="solar"]',
        'nwr["name"~"fotovolta|solar|fotovolt",i]',
    ],
    "pulizie": [
        'nwr["shop"="cleaning"]',
        'nwr["craft"="cleaner"]',
        'nwr["office"="cleaning"]',
    ],
    "imbarcazioni": [
        'nwr["shop"="boat"]',
        'nwr["craft"="boatbuilder"]',
        'nwr["leisure"="marina"]',
        'nwr["shop"="marine"]',
    ],
    "pavimentazioni": [
        'nwr["shop"="flooring"]',
        'nwr["shop"="tiles"]',
        'nwr["craft"="tiler"]',
    ],
    "default": [
        'nwr["office"="company"]',
        'nwr["shop"]["name"]',
        'nwr["craft"]["name"]',
        'nwr["industrial"]["name"]',
    ],
}


def _query_area(comune: Optional[str], provincia: str, tags: list[str], timeout: int = 45) -> str:
    """Costruisce una query Overpass QL basata su area amministrativa."""
    # Cerca l'area per nome (comune prioritario, altrimenti provincia)
    if comune:
        area_filter = f'area["name"="{comune}"]["admin_level"~"8|9"]->.searchArea;'
    else:
        area_filter = f'area["name"="{provincia}"]["admin_level"~"6|4"]->.searchArea;'

    parts = []
    for t in tags:
        # nwr[...]  →  nwr[...](area.searchArea)
        if t.startswith("nwr"):
            parts.append(t.replace("nwr", "nwr", 1) + "(area.searchArea)")
        else:
            parts.append(f"{t}(area.searchArea)")

    union = ";\n  ".join(parts)
    return f"""
[out:json][timeout:{timeout}];
{area_filter}
(
  {union};
);
out center tags;
"""


def _normalize_element(el: dict) -> Optional[dict[str, Any]]:
    tags = el.get("tags") or {}
    nome = tags.get("name") or tags.get("brand") or tags.get("operator")
    if not nome:
        return None

    lat = el.get("lat") or (el.get("center") or {}).get("lat")
    lon = el.get("lon") or (el.get("center") or {}).get("lon")

    indirizzo_parts = []
    if tags.get("addr:street"):
        street = tags["addr:street"]
        if tags.get("addr:housenumber"):
            street = f"{street} {tags['addr:housenumber']}"
        indirizzo_parts.append(street)
    if tags.get("addr:postcode"):
        indirizzo_parts.append(tags["addr:postcode"])
    if tags.get("addr:city"):
        indirizzo_parts.append(tags["addr:city"])

    return {
        "nome": nome.strip(),
        "indirizzo": ", ".join(indirizzo_parts) if indirizzo_parts else None,
        "comune": tags.get("addr:city"),
        "telefono": tags.get("phone") or tags.get("contact:phone"),
        "email": tags.get("email") or tags.get("contact:email"),
        "sito_web": tags.get("website") or tags.get("contact:website") or tags.get("url"),
        "lat": float(lat) if lat is not None else None,
        "lon": float(lon) if lon is not None else None,
        "fonte": "openstreetmap",
        "url_fonte": f"https://www.openstreetmap.org/{el.get('type', 'node')}/{el.get('id')}",
        "osm_tags": {k: v for k, v in tags.items() if k not in ("name",)},
    }


async def cerca_aziende(
    provincia: str,
    comune: Optional[str] = None,
    categorie: Optional[list[str]] = None,
    max_results: int = 200,
) -> list[dict[str, Any]]:
    """
    Interroga Overpass e restituisce una lista di dict normalizzati.
    """
    tags: list[str] = []
    cats = [c.lower().strip() for c in (categorie or [])]
    for c in cats:
        tags.extend(CATEGORIA_OSM.get(c, []))
    if not tags:
        tags = CATEGORIA_OSM["default"]

    # Dedup tag
    tags = list(dict.fromkeys(tags))
    query = _query_area(comune, provincia, tags)

    last_error = None
    for url in OVERPASS_URLS:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, data={"data": query})
                resp.raise_for_status()
                data = resp.json()
                elements = data.get("elements") or []
                risultati = []
                seen_names: set[str] = set()
                for el in elements:
                    item = _normalize_element(el)
                    if not item:
                        continue
                    key = item["nome"].lower().strip()
                    if key in seen_names:
                        continue
                    seen_names.add(key)
                    if comune and not item.get("comune"):
                        item["comune"] = comune
                    if not item.get("provincia"):
                        item["provincia"] = provincia
                    risultati.append(item)
                    if len(risultati) >= max_results:
                        break
                logger.info(
                    "Overpass %s/%s → %d elementi grezzi, %d normalizzati",
                    provincia, comune or "*", len(elements), len(risultati),
                )
                return risultati
        except Exception as e:
            last_error = e
            logger.warning("Overpass endpoint %s fallito: %s", url, e)
            continue

    logger.error("Tutti gli endpoint Overpass falliti: %s", last_error)
    return []
