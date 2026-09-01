"""
Agente Scraper Aziende: orchestra Overpass → analisi sito → dati camerali pubblici
→ deduplicazione → scoring → salvataggio in PostgreSQL.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session, select

from app.models import Azienda, AziendaFonte, Scansione
from app.services.overpass_client import cerca_aziende as overpass_cerca
from app.services.website_analyzer import analizza_sito
from app.services.registro_imprese_public import arricchisci_da_piva_o_nome

logger = logging.getLogger(__name__)


def _normalizza_nome(nome: str) -> str:
    if not nome:
        return ""
    n = unicodedata.normalize("NFKD", nome)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = n.lower()
    n = re.sub(r"[^\w\s]", " ", n)
    n = re.sub(r"\b(srl|spa|snc|sas|ss|ditta|impresa|azienda|societa|società)\b", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _calcola_completezza(az: dict) -> int:
    campi = [
        "nome", "indirizzo", "telefono", "email", "sito_web",
        "partita_iva", "descrizione", "pec", "comune",
    ]
    presenti = sum(1 for c in campi if az.get(c))
    return int(100 * presenti / len(campi))


def _calcola_score(az: dict) -> int:
    """Score qualità lead 0-100."""
    score = 0
    if az.get("nome"):
        score += 10
    if az.get("telefono"):
        score += 15
    if az.get("email"):
        score += 20
    if az.get("sito_web"):
        score += 10
    if az.get("partita_iva"):
        score += 15
    if az.get("pec"):
        score += 5
    if az.get("descrizione"):
        score += 10
    if az.get("indirizzo") and az.get("comune"):
        score += 10
    if az.get("stato_azienda") == "attiva" or az.get("stato_azienda") is None:
        score += 5
    return min(100, score)


def _trova_duplicato(session: Session, nome_norm: str, piva: Optional[str]) -> Optional[Azienda]:
    if piva:
        az = session.exec(select(Azienda).where(Azienda.partita_iva == piva)).first()
        if az:
            return az
    if nome_norm:
        az = session.exec(
            select(Azienda).where(Azienda.nome_normalizzato == nome_norm)
        ).first()
        if az:
            return az
    return None


def _merge_dati(esistente: Azienda, nuovi: dict) -> list[str]:
    """Aggiorna solo i campi vuoti. Ritorna lista campi aggiornati."""
    aggiornati = []
    mapping = {
        "telefono": "telefono",
        "email": "email",
        "pec": "pec",
        "sito_web": "sito_web",
        "indirizzo": "indirizzo",
        "descrizione": "descrizione",
        "partita_iva": "partita_iva",
        "codice_fiscale": "codice_fiscale",
        "rea": "rea",
        "forma_giuridica": "forma_giuridica",
        "stato_azienda": "stato_azienda",
        "sede_legale": "sede_legale",
        "ateco": "ateco",
        "lat": "lat",
        "lon": "lon",
    }
    for src, dst in mapping.items():
        if nuovi.get(src) and not getattr(esistente, dst, None):
            setattr(esistente, dst, nuovi[src])
            aggiornati.append(dst)
    if nuovi.get("social") and isinstance(nuovi["social"], dict):
        social = dict(esistente.social or {})
        social.update({k: v for k, v in nuovi["social"].items() if v})
        esistente.social = social
    esistente.aggiornato_il = datetime.utcnow()
    return aggiornati


async def esegui_scansione(
    session: Session,
    scansione_id: int,
    arricchisci_sito: bool = True,
    cerca_dati_camerali: bool = True,
) -> Scansione:
    """
    Esegue l'intera pipeline per una Scansione già creata.
    """
    scansione = session.get(Scansione, scansione_id)
    if not scansione:
        raise ValueError(f"Scansione {scansione_id} non trovata")

    scansione.stato = "in_corso"
    session.add(scansione)
    session.commit()

    try:
        # 1) Ricerca multi-fonte (Overpass)
        grezzi = await overpass_cerca(
            provincia=scansione.provincia,
            comune=scansione.comune,
            categorie=scansione.categorie or [],
        )
        logger.info("Scansione %s: %d risultati grezzi da Overpass", scansione_id, len(grezzi))

        nuove = 0
        duplicate = 0
        incomplete = 0
        scores: list[int] = []

        for raw in grezzi:
            nome = (raw.get("nome") or "").strip()
            if not nome or len(nome) < 3:
                continue

            nome_norm = _normalizza_nome(nome)
            piva = raw.get("partita_iva")

            # 2) Analisi sito (se presente e richiesto)
            if arricchisci_sito and raw.get("sito_web"):
                try:
                    sito_data = await analizza_sito(raw["sito_web"])
                    for k in ("email", "telefono", "partita_iva", "codice_fiscale", "descrizione", "social"):
                        if sito_data.get(k) and not raw.get(k):
                            raw[k] = sito_data[k]
                    if sito_data.get("partita_iva"):
                        piva = sito_data["partita_iva"]
                except Exception as e:
                    logger.debug("Analisi sito fallita per %s: %s", nome, e)

            # 3) Dati camerali pubblici
            if cerca_dati_camerali:
                try:
                    cam = await arricchisci_da_piva_o_nome(
                        nome=nome,
                        partita_iva=piva,
                        pec=raw.get("pec"),
                    )
                    for k, v in cam.items():
                        if v and k not in ("visura_ufficiale_disponibile",) and not raw.get(k):
                            raw[k] = v
                    raw["visura_ufficiale_disponibile"] = cam.get("visura_ufficiale_disponibile", True)
                    raw["data_verifica_camerale"] = cam.get("data_verifica_camerale")
                    raw["fonte_camerale"] = cam.get("fonte_camerale")
                    if cam.get("partita_iva"):
                        piva = cam["partita_iva"]
                except Exception as e:
                    logger.debug("Dati camerali falliti per %s: %s", nome, e)

            # 4) Dedup
            esistente = _trova_duplicato(session, nome_norm, piva)
            if esistente:
                _merge_dati(esistente, raw)
                esistente.score_qualita = _calcola_score({
                    "nome": esistente.nome,
                    "telefono": esistente.telefono,
                    "email": esistente.email,
                    "sito_web": esistente.sito_web,
                    "partita_iva": esistente.partita_iva,
                    "pec": esistente.pec,
                    "descrizione": esistente.descrizione,
                    "indirizzo": esistente.indirizzo,
                    "comune": esistente.comune,
                    "stato_azienda": esistente.stato_azienda,
                })
                esistente.completezza = _calcola_completezza({
                    "nome": esistente.nome,
                    "indirizzo": esistente.indirizzo,
                    "telefono": esistente.telefono,
                    "email": esistente.email,
                    "sito_web": esistente.sito_web,
                    "partita_iva": esistente.partita_iva,
                    "descrizione": esistente.descrizione,
                    "pec": esistente.pec,
                    "comune": esistente.comune,
                })
                session.add(esistente)
                duplicate += 1
                scores.append(esistente.score_qualita or 0)
                continue

            # 5) Nuova azienda
            az_dict = {
                "nome": nome,
                "nome_normalizzato": nome_norm,
                "categoria": (scansione.categorie or [None])[0],
                "categorie": scansione.categorie or [],
                "indirizzo": raw.get("indirizzo"),
                "comune": raw.get("comune") or scansione.comune,
                "provincia": raw.get("provincia") or scansione.provincia,
                "telefono": raw.get("telefono"),
                "email": raw.get("email"),
                "pec": raw.get("pec"),
                "sito_web": raw.get("sito_web"),
                "social": raw.get("social") or {},
                "descrizione": raw.get("descrizione"),
                "attivita": raw.get("attivita"),
                "ateco": raw.get("ateco"),
                "partita_iva": piva,
                "codice_fiscale": raw.get("codice_fiscale"),
                "rea": raw.get("rea"),
                "forma_giuridica": raw.get("forma_giuridica"),
                "stato_azienda": raw.get("stato_azienda"),
                "sede_legale": raw.get("sede_legale"),
                "data_verifica_camerale": raw.get("data_verifica_camerale"),
                "fonte_camerale": raw.get("fonte_camerale"),
                "visura_ufficiale_disponibile": raw.get("visura_ufficiale_disponibile", True),
                "lat": raw.get("lat"),
                "lon": raw.get("lon"),
                "fonte": raw.get("fonte") or "openstreetmap",
                "url_fonte": raw.get("url_fonte"),
                "scansione_id": scansione_id,
            }
            az_dict["score_qualita"] = _calcola_score(az_dict)
            az_dict["completezza"] = _calcola_completezza(az_dict)

            azienda = Azienda(**az_dict)
            session.add(azienda)
            session.flush()

            # Traccia fonti
            for campo in ("telefono", "email", "partita_iva", "sito_web", "descrizione"):
                if az_dict.get(campo):
                    session.add(AziendaFonte(
                        azienda_id=azienda.id,
                        campo=campo,
                        valore=str(az_dict[campo])[:500],
                        fonte=az_dict.get("fonte") or "openstreetmap",
                        url_fonte=az_dict.get("url_fonte"),
                    ))

            nuove += 1
            scores.append(az_dict["score_qualita"])
            if az_dict["completezza"] < 40:
                incomplete += 1

        session.commit()

        scansione.trovate = nuove + duplicate
        scansione.nuove = nuove
        scansione.duplicate = duplicate
        scansione.incomplete = incomplete
        scansione.score_medio = round(sum(scores) / len(scores), 1) if scores else None
        scansione.stato = "completata"
        scansione.completato_il = datetime.utcnow()
        session.add(scansione)
        session.commit()
        session.refresh(scansione)
        return scansione

    except Exception as e:
        logger.exception("Errore scansione %s", scansione_id)
        scansione.stato = "errore"
        scansione.errore = str(e)[:500]
        scansione.completato_il = datetime.utcnow()
        session.add(scansione)
        session.commit()
        session.refresh(scansione)
        return scansione
