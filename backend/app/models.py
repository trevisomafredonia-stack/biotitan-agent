from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Column, JSON


class Bando(SQLModel, table=True):
    """Un bando/gara intercettato, dal piano gare fino all'aggiudicazione."""

    id: Optional[int] = Field(default=None, primary_key=True)

    # Identificazione
    titolo: str
    cig: Optional[str] = Field(default=None, index=True)  # Codice Identificativo Gara ANAC
    fonte: str  # es. "acquisti_in_rete", "anac_ocds", "stazione_locale:Comune di X"
    link: Optional[str] = None

    # Ciclo di vita
    stato: str = "preinformazione"  # preinformazione | pubblicato | in_valutazione | aggiudicato | chiuso
    data_pubblicazione: Optional[datetime] = None
    data_scadenza: Optional[datetime] = None

    # Match commerciale BioTitan
    match_percentuale: Optional[int] = None
    priorita_commerciale: Optional[str] = None  # bassa | media | alta
    stato_verifica: str = "confermato"  # confermato | da_confermare (sotto soglia match)

    # Esito gara
    aggiudicatario: Optional[str] = None
    importo_offerta: Optional[float] = None
    importo_aggiudicazione: Optional[float] = None
    ribasso_percentuale: Optional[float] = None

    # Referente stazione appaltante
    referente_nome: Optional[str] = None
    referente_ruolo: Optional[str] = None  # RUP | progettista | direttore_lavori | responsabile_tecnico
    referente_contatto: Optional[str] = None

    creato_il: datetime = Field(default_factory=datetime.utcnow)
    aggiornato_il: datetime = Field(default_factory=datetime.utcnow)


class Partecipante(SQLModel, table=True):
    """Un operatore economico collegato a un bando (partecipante o aggiudicatario)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    bando_id: int = Field(foreign_key="bando.id", index=True)
    azienda: str
    ruolo: Optional[str] = None  # partecipante | aggiudicatario | progettista | RUP | direttore_lavori
    esito: Optional[str] = None  # es. "vincitore", "escluso", importo offerto


class Attivita(SQLModel, table=True):
    """Prossima attività commerciale in agenda, generata da un bando."""

    id: Optional[int] = Field(default=None, primary_key=True)
    bando_id: int = Field(foreign_key="bando.id", index=True)
    descrizione: str
    scadenza: Optional[datetime] = None
    completata: bool = False
    creato_il: datetime = Field(default_factory=datetime.utcnow)


class VoceCapitolato(SQLModel, table=True):
    """Una singola voce rilevante trovata dall'AI dentro il capitolato di un
    bando (equivalente alle voci "analisi" già gestite manualmente nel CRM).
    Un bando può avere più voci: pagina 47, pagina 63, pagina 91..."""

    id: Optional[int] = Field(default=None, primary_key=True)
    bando_id: int = Field(foreign_key="bando.id", index=True)

    pagina: Optional[str] = None
    articolo: Optional[str] = None
    quantita: Optional[str] = None
    unita_misura: Optional[str] = None
    estratto: Optional[str] = None
    requisiti: Optional[str] = None
    prodotto_candidato: Optional[str] = None
    marca_richiesta: Optional[str] = None
    certificazioni: Optional[str] = None
    match_percentuale: Optional[int] = None

    creato_il: datetime = Field(default_factory=datetime.utcnow)


class FonteScanLog(SQLModel, table=True):
    """Log di ogni ciclo di scansione, per diagnosticare l'agente."""

    id: Optional[int] = Field(default=None, primary_key=True)
    fonte: str
    eseguito_il: datetime = Field(default_factory=datetime.utcnow)
    bandi_trovati: int = 0
    bandi_nuovi: int = 0
    errore: Optional[str] = None


# ---------------------------------------------------------------------------
# Agente Scraper Aziende (lead acquisition + enrichment)
# ---------------------------------------------------------------------------

class Scansione(SQLModel, table=True):
    """Una sessione di ricerca territoriale per categorie."""

    id: Optional[int] = Field(default=None, primary_key=True)
    regione: str = "Puglia"
    provincia: str
    comune: Optional[str] = None
    categorie: list = Field(default_factory=list, sa_column=Column(JSON))
    stato: str = "in_corso"  # in_corso | completata | errore | annullata
    trovate: int = 0
    nuove: int = 0
    duplicate: int = 0
    incomplete: int = 0
    score_medio: Optional[float] = None
    errore: Optional[str] = None
    creato_il: datetime = Field(default_factory=datetime.utcnow)
    completato_il: Optional[datetime] = None


class Azienda(SQLModel, table=True):
    """Scheda azienda arricchita (lead + dati pubblici)."""

    id: Optional[int] = Field(default=None, primary_key=True)

    # Identità base
    nome: str = Field(index=True)
    nome_normalizzato: Optional[str] = Field(default=None, index=True)  # per dedup
    categoria: Optional[str] = None
    categorie: list = Field(default_factory=list, sa_column=Column(JSON))

    # Contatti
    indirizzo: Optional[str] = None
    comune: Optional[str] = None
    provincia: Optional[str] = None
    cap: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    pec: Optional[str] = None
    sito_web: Optional[str] = None
    social: dict = Field(default_factory=dict, sa_column=Column(JSON))  # {facebook, linkedin, ...}

    # Descrizione e attività
    descrizione: Optional[str] = None
    attivita: Optional[str] = None
    ateco: Optional[str] = None

    # Dati camerali pubblici (gratuiti)
    partita_iva: Optional[str] = Field(default=None, index=True)
    codice_fiscale: Optional[str] = Field(default=None, index=True)
    rea: Optional[str] = None
    forma_giuridica: Optional[str] = None
    stato_azienda: Optional[str] = None  # attiva | cessata | in_liquidazione | ...
    sede_legale: Optional[str] = None
    data_verifica_camerale: Optional[datetime] = None
    fonte_camerale: Optional[str] = None
    visura_ufficiale_disponibile: bool = True  # sempre True: è a pagamento

    # Geo
    lat: Optional[float] = None
    lon: Optional[float] = None

    # Provenienza e qualità
    fonte: Optional[str] = None  # overpass | web | sito | registro_imprese | ...
    url_fonte: Optional[str] = None
    score_qualita: Optional[int] = None  # 0-100
    completezza: Optional[int] = None  # % campi valorizzati
    scansione_id: Optional[int] = Field(default=None, foreign_key="scansione.id", index=True)

    # CRM
    note: Optional[str] = None
    stato_lead: str = "nuovo"  # nuovo | contattato | qualificato | cliente | scartato
    in_crm: bool = True

    creato_il: datetime = Field(default_factory=datetime.utcnow)
    aggiornato_il: datetime = Field(default_factory=datetime.utcnow)


class AziendaFonte(SQLModel, table=True):
    """Traccia ogni fonte da cui è arrivato un dato per un'azienda."""

    id: Optional[int] = Field(default=None, primary_key=True)
    azienda_id: int = Field(foreign_key="azienda.id", index=True)
    campo: str  # es. "telefono", "partita_iva", "descrizione"
    valore: Optional[str] = None
    fonte: str
    url_fonte: Optional[str] = None
    verificato_il: datetime = Field(default_factory=datetime.utcnow)
