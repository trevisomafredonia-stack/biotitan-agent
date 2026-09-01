from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Bando, Partecipante, VoceCapitolato
from app.schemas import BandoRead, BandoUpdate

router = APIRouter(prefix="/bandi", tags=["bandi"])


@router.get("", response_model=list[BandoRead])
def lista_bandi(
    stato: Optional[str] = None,
    stato_verifica: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """Radar gare: lista bandi, filtrabile per stato del ciclo di vita
    (pubblicato/aggiudicato/...) e per stato di verifica (confermato/da_confermare)."""
    query = select(Bando)
    if stato:
        query = query.where(Bando.stato == stato)
    if stato_verifica:
        query = query.where(Bando.stato_verifica == stato_verifica)
    bandi = session.exec(query.order_by(Bando.aggiornato_il.desc())).all()

    risultato = []
    for b in bandi:
        partecipanti = session.exec(select(Partecipante).where(Partecipante.bando_id == b.id)).all()
        voci = session.exec(select(VoceCapitolato).where(VoceCapitolato.bando_id == b.id)).all()
        letto = BandoRead.model_validate(b)
        letto.partecipanti = partecipanti
        letto.voci = voci
        risultato.append(letto)
    return risultato


@router.get("/{bando_id}", response_model=BandoRead)
def dettaglio_bando(bando_id: int, session: Session = Depends(get_session)):
    bando = session.get(Bando, bando_id)
    if not bando:
        raise HTTPException(status_code=404, detail="Bando non trovato")
    partecipanti = session.exec(select(Partecipante).where(Partecipante.bando_id == bando_id)).all()
    voci = session.exec(select(VoceCapitolato).where(VoceCapitolato.bando_id == bando_id)).all()
    letto = BandoRead.model_validate(bando)
    letto.partecipanti = partecipanti
    letto.voci = voci
    return letto


@router.patch("/{bando_id}", response_model=BandoRead)
def aggiorna_bando(bando_id: int, dati: BandoUpdate, session: Session = Depends(get_session)):
    """Permette al CRM di correggere manualmente un bando (es. confermare
    un bando 'da_confermare', o aggiornare il referente)."""
    bando = session.get(Bando, bando_id)
    if not bando:
        raise HTTPException(status_code=404, detail="Bando non trovato")

    for campo, valore in dati.model_dump(exclude_unset=True).items():
        setattr(bando, campo, valore)

    session.add(bando)
    session.commit()
    session.refresh(bando)
    return bando
