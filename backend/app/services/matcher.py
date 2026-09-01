"""
Estrattore AI: dato il testo (anche lungo, multi-pagina) di un capitolato,
chiede a Claude di leggerlo come farebbe un agente commerciale — cercando
OGNI punto in cui si parla di qualcosa che BioTitan può vendere, non solo il
primo che trova. Il risultato e' una LISTA di voci (una per pagina/articolo
rilevante), compatibile con l'array "analisi" gia' usato dal CRM.
"""

import json
from typing import Any

import httpx

from app.config import settings

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """Sei un assistente che analizza capitolati di gare d'appalto per
conto di un'azienda che vende trattamenti superficiali nanotecnologici (BioTitan):
protezione e igienizzazione di superfici, pavimentazioni, materiali edili,
imbarcazioni e strutture pubbliche. I prodotti disponibili sono: BioTitan FLOOR,
BioTitan GLASS / Solar Protect, BioTitan METAL, BioTitan CLEANER, BioTitan
PROTECTIVE, BioTitan VB SAFE.

Il testo che ricevi e' un capitolato, possibilmente lungo, con marcatori
"[PAGINA N]" quando disponibili. Leggilo per intero e trova OGNI punto
(non solo il primo) in cui si richiede qualcosa di compatibile con i prodotti
BioTitan: trattamenti protettivi, impermeabilizzanti, idrorepellenti,
consolidanti, detergenti professionali, sanificazione, manutenzione superfici,
lavaggio pannelli fotovoltaici, trattamento vetro.

Se non trovi marcatori di pagina, usa null per "pagina" e basati sulla
posizione nel testo per "articolo" quando riconoscibile.

Rispondi SOLO con un array JSON (anche vuoto se non trovi nulla di rilevante),
senza testo prima o dopo. Ogni elemento ha questi campi:
{
  "pagina": string o null,
  "articolo": string o null,
  "quantita": string o null,
  "unita_misura": string o null,
  "estratto": string (max 400 caratteri, in italiano, parafrasato, mai copiato verbatim),
  "requisiti": string o null,
  "prodotto_candidato": string o null (uno dei prodotti BioTitan sopra elencati),
  "marca_richiesta": string o null,
  "certificazioni": string o null,
  "match_percentuale": intero da 0 a 100
}
Massimo 8 voci: scegli le piu' rilevanti se ce ne sono di piu'.
"""


async def analizza_capitolato(testo_capitolato: str) -> list[dict[str, Any]]:
    """Torna una lista di voci trovate nel capitolato (puo' essere vuota)."""
    if not testo_capitolato or not testo_capitolato.strip():
        return []

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            CLAUDE_API_URL,
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 2000,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": testo_capitolato[:80000]}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        testo_risposta = "".join(
            blocco.get("text", "") for blocco in data.get("content", []) if blocco.get("type") == "text"
        )
        testo_pulito = testo_risposta.replace("```json", "").replace("```", "").strip()
        try:
            voci = json.loads(testo_pulito)
        except json.JSONDecodeError:
            return []
        return voci if isinstance(voci, list) else []


def match_migliore(voci: list[dict[str, Any]]) -> int:
    """Il match complessivo del bando e' il massimo tra le voci trovate."""
    if not voci:
        return 0
    return max(int(v.get("match_percentuale", 0) or 0) for v in voci)


def stato_verifica_da_match(match_percentuale: int) -> str:
    """Applica la soglia: sotto soglia il bando entra come 'da_confermare'."""
    soglia = settings.match_autoconfirm_threshold
    return "confermato" if match_percentuale >= soglia else "da_confermare"
