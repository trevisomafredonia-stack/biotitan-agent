"""
Scarica un documento collegato a un bando (capitolato, disciplinare...) e ne
estrae il testo, così l'estrattore AI può leggerlo pagina per pagina invece
di limitarsi al solo titolo del bando.
"""

import io

import httpx
from pypdf import PdfReader


async def scarica_testo_documento(url: str, max_pagine: int = 60) -> str:
    """Scarica un PDF (o una pagina HTML) e torna il testo con marcatori di pagina,
    così l'AI può citare esattamente "pagina N" nei match che trova.
    Se il documento non è un PDF valido o il download fallisce, torna stringa vuota:
    il chiamante deve prevedere questo caso e ripiegare sul solo titolo."""
    try:
        async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")

            if "pdf" in content_type or url.lower().endswith(".pdf"):
                reader = PdfReader(io.BytesIO(resp.content))
                pagine_testo = []
                for numero, pagina in enumerate(reader.pages[:max_pagine], start=1):
                    testo_pagina = pagina.extract_text() or ""
                    if testo_pagina.strip():
                        pagine_testo.append(f"[PAGINA {numero}]\n{testo_pagina}")
                return "\n\n".join(pagine_testo)

            # Fallback: pagina HTML semplice, nessuna numerazione di pagina reale
            return resp.text[:200000]

    except Exception:
        return ""
