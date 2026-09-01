"""
Endpoint per l'Agente Scraper Aziende.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, col

from app.database import get_session, engine
from app.models import Azienda, Scansione
from app.schemas import (
    AziendaRead,
    AziendaUpdate,
    ScansioneCreate,
    ScansioneRead,
    TerritorioOut,
)
from app.services.territori_puglia import get_territorio
from app.services.scraper_agent import esegui_scansione

router = APIRouter(prefix="/scraper", tags=["scraper"])


@router.get("/territori", response_model=TerritorioOut)
def territori():
    """Puglia → province → comuni (257 totali)."""
    data = get_territorio()
    return TerritorioOut(regione=data["regione"], province=data["province"])


@router.post("/scansioni", response_model=ScansioneRead)
def avvia_scansione(
    body: ScansioneCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    Avvia una nuova scansione territoriale.
    L'esecuzione vera e propria avviene in background.
    """
    if not body.categorie:
        raise HTTPException(400, "Seleziona almeno una categoria")
    if not body.provincia:
        raise HTTPException(400, "Provincia obbligatoria")

    scansione = Scansione(
        regione=body.regione or "Puglia",
        provincia=body.provincia,
        comune=body.comune,
        categorie=body.categorie,
        stato="in_corso",
    )
    session.add(scansione)
    session.commit()
    session.refresh(scansione)

    def _run(sid: int, arricchisci: bool, camerali: bool):
        with Session(engine) as s:
            import asyncio
            asyncio.run(esegui_scansione(s, sid, arricchisci, camerali))

    background_tasks.add_task(
        _run,
        scansione.id,
        body.arricchisci_sito,
        body.cerca_dati_camerali,
    )
    return scansione


@router.get("/scansioni", response_model=list[ScansioneRead])
def lista_scansioni(
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(Scansione).order_by(Scansione.creato_il.desc()).limit(limit)
    ).all()
    return rows


@router.get("/scansioni/{scansione_id}", response_model=ScansioneRead)
def dettaglio_scansione(scansione_id: int, session: Session = Depends(get_session)):
    s = session.get(Scansione, scansione_id)
    if not s:
        raise HTTPException(404, "Scansione non trovata")
    return s


@router.get("/aziende", response_model=list[AziendaRead])
def lista_aziende(
    scansione_id: Optional[int] = None,
    provincia: Optional[str] = None,
    comune: Optional[str] = None,
    categoria: Optional[str] = None,
    q: Optional[str] = None,
    min_score: Optional[int] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    query = select(Azienda)
    if scansione_id is not None:
        query = query.where(Azienda.scansione_id == scansione_id)
    if provincia:
        query = query.where(Azienda.provincia == provincia)
    if comune:
        query = query.where(Azienda.comune == comune)
    if categoria:
        query = query.where(Azienda.categoria == categoria)
    if min_score is not None:
        query = query.where(Azienda.score_qualita >= min_score)
    if q:
        like = f"%{q}%"
        query = query.where(
            (col(Azienda.nome).ilike(like))
            | (col(Azienda.email).ilike(like))
            | (col(Azienda.partita_iva).ilike(like))
        )
    rows = session.exec(
        query.order_by(Azienda.score_qualita.desc().nullslast(), Azienda.creato_il.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return rows


@router.get("/aziende/{azienda_id}", response_model=AziendaRead)
def dettaglio_azienda(azienda_id: int, session: Session = Depends(get_session)):
    a = session.get(Azienda, azienda_id)
    if not a:
        raise HTTPException(404, "Azienda non trovata")
    return a


@router.patch("/aziende/{azienda_id}", response_model=AziendaRead)
def aggiorna_azienda(
    azienda_id: int,
    body: AziendaUpdate,
    session: Session = Depends(get_session),
):
    a = session.get(Azienda, azienda_id)
    if not a:
        raise HTTPException(404, "Azienda non trovata")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    a.aggiornato_il = datetime.utcnow()
    session.add(a)
    session.commit()
    session.refresh(a)
    return a


@router.get("/aziende/export/csv")
def export_csv(
    scansione_id: Optional[int] = None,
    provincia: Optional[str] = None,
    session: Session = Depends(get_session),
):
    query = select(Azienda)
    if scansione_id is not None:
        query = query.where(Azienda.scansione_id == scansione_id)
    if provincia:
        query = query.where(Azienda.provincia == provincia)
    rows = session.exec(query.order_by(Azienda.nome)).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "nome", "categoria", "indirizzo", "comune", "provincia",
        "telefono", "email", "pec", "sito_web", "partita_iva", "codice_fiscale",
        "rea", "stato_azienda", "descrizione", "score_qualita", "completezza",
        "fonte", "url_fonte", "stato_lead", "creato_il",
    ])
    for a in rows:
        writer.writerow([
            a.id, a.nome, a.categoria, a.indirizzo, a.comune, a.provincia,
            a.telefono, a.email, a.pec, a.sito_web, a.partita_iva, a.codice_fiscale,
            a.rea, a.stato_azienda, (a.descrizione or "")[:300],
            a.score_qualita, a.completezza, a.fonte, a.url_fonte,
            a.stato_lead, a.creato_il.isoformat() if a.creato_il else "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=aziende_biotitan.csv"},
    )
