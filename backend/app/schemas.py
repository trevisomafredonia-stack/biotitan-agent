from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


class PartecipanteRead(BaseModel):
    id: int
    azienda: str
    ruolo: Optional[str]
    esito: Optional[str]

    class Config:
        from_attributes = True


class VoceCapitolatoRead(BaseModel):
    id: int
    pagina: Optional[str]
    articolo: Optional[str]
    quantita: Optional[str]
    unita_misura: Optional[str]
    estratto: Optional[str]
    requisiti: Optional[str]
    prodotto_candidato: Optional[str]
    marca_richiesta: Optional[str]
    certificazioni: Optional[str]
    match_percentuale: Optional[int]

    class Config:
        from_attributes = True


class BandoRead(BaseModel):
    id: int
    titolo: str
    cig: Optional[str]
    fonte: str
    link: Optional[str]
    stato: str
    data_pubblicazione: Optional[datetime]
    data_scadenza: Optional[datetime]
    match_percentuale: Optional[int]
    priorita_commerciale: Optional[str]
    stato_verifica: str
    aggiudicatario: Optional[str]
    importo_offerta: Optional[float]
    importo_aggiudicazione: Optional[float]
    ribasso_percentuale: Optional[float]
    referente_nome: Optional[str]
    referente_ruolo: Optional[str]
    referente_contatto: Optional[str]
    partecipanti: list[PartecipanteRead] = []
    voci: list[VoceCapitolatoRead] = []

    class Config:
        from_attributes = True


class BandoUpdate(BaseModel):
    """Campi che il CRM può modificare manualmente (es. referente, priorità, note)."""

    stato: Optional[str] = None
    priorita_commerciale: Optional[str] = None
    stato_verifica: Optional[str] = None
    referente_nome: Optional[str] = None
    referente_ruolo: Optional[str] = None
    referente_contatto: Optional[str] = None


# ---------------------------------------------------------------------------
# Scraper Aziende
# ---------------------------------------------------------------------------

class TerritorioOut(BaseModel):
    regione: str
    province: list[dict[str, Any]]


class ScansioneCreate(BaseModel):
    regione: str = "Puglia"
    provincia: str
    comune: Optional[str] = None
    categorie: list[str]
    arricchisci_sito: bool = True
    cerca_dati_camerali: bool = True


class ScansioneRead(BaseModel):
    id: int
    regione: str
    provincia: str
    comune: Optional[str]
    categorie: list
    stato: str
    trovate: int
    nuove: int
    duplicate: int
    incomplete: int
    score_medio: Optional[float]
    errore: Optional[str]
    creato_il: datetime
    completato_il: Optional[datetime]

    class Config:
        from_attributes = True


class AziendaRead(BaseModel):
    id: int
    nome: str
    categoria: Optional[str]
    categorie: list = []
    indirizzo: Optional[str]
    comune: Optional[str]
    provincia: Optional[str]
    telefono: Optional[str]
    email: Optional[str]
    pec: Optional[str]
    sito_web: Optional[str]
    social: dict = {}
    descrizione: Optional[str]
    attivita: Optional[str]
    ateco: Optional[str]
    partita_iva: Optional[str]
    codice_fiscale: Optional[str]
    rea: Optional[str]
    forma_giuridica: Optional[str]
    stato_azienda: Optional[str]
    sede_legale: Optional[str]
    data_verifica_camerale: Optional[datetime]
    fonte_camerale: Optional[str]
    visura_ufficiale_disponibile: bool
    lat: Optional[float]
    lon: Optional[float]
    fonte: Optional[str]
    url_fonte: Optional[str]
    score_qualita: Optional[int]
    completezza: Optional[int]
    scansione_id: Optional[int]
    stato_lead: str
    creato_il: datetime
    aggiornato_il: datetime

    class Config:
        from_attributes = True


class AziendaUpdate(BaseModel):
    stato_lead: Optional[str] = None
    note: Optional[str] = None
    categoria: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
