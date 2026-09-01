from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session, select

from app.config import settings
from app.database import engine
from app.models import Bando, FonteScanLog, VoceCapitolato
from app.services import anac_client, document_reader, matcher

scheduler = AsyncIOScheduler()


async def _analizza_e_salva_voci(session: Session, bando: Bando) -> int:
    """Scarica il documento collegato al bando (se c'e' un link), lo fa leggere
    all'estrattore AI e salva ogni voce trovata. Torna il match complessivo."""

    testo_documento = ""
    if bando.link:
        testo_documento = await document_reader.scarica_testo_documento(bando.link)

    # Se non riusciamo a scaricare il documento, ripieghiamo sul solo titolo:
    # meglio un match approssimativo che nessun match.
    testo_da_analizzare = testo_documento or bando.titolo

    try:
        voci = await matcher.analizza_capitolato(testo_da_analizzare)
    except Exception:
        voci = []

    for v in voci:
        session.add(
            VoceCapitolato(
                bando_id=bando.id,
                pagina=v.get("pagina"),
                articolo=v.get("articolo"),
                quantita=v.get("quantita"),
                unita_misura=v.get("unita_misura"),
                estratto=v.get("estratto"),
                requisiti=v.get("requisiti"),
                prodotto_candidato=v.get("prodotto_candidato"),
                marca_richiesta=v.get("marca_richiesta"),
                certificazioni=v.get("certificazioni"),
                match_percentuale=v.get("match_percentuale"),
            )
        )

    return matcher.match_migliore(voci)


async def esegui_scansione() -> None:
    """Un ciclo completo: interroga ANAC OCDS, scarica il capitolato di ogni
    bando nuovo, lo fa leggere all'estrattore AI (che trova piu' voci, non una
    sola), salva tutto nel database marcando 'da_confermare' i bandi sotto
    soglia di match invece di scartarli in silenzio."""

    trovati = 0
    nuovi = 0
    errore = None

    try:
        releases = await anac_client.fetch_recent_releases()
        trovati = len(releases)

        with Session(engine) as session:
            for release in releases:
                dati = anac_client.release_to_bando_dict(release)

                esistente = session.exec(select(Bando).where(Bando.cig == dati.get("cig"))).first()
                if esistente:
                    for campo, valore in dati.items():
                        if valore is not None:
                            setattr(esistente, campo, valore)
                    esistente.aggiornato_il = datetime.utcnow()
                    session.add(esistente)
                    session.flush()
                    continue

                bando = Bando(**dati)
                session.add(bando)
                session.flush()  # per avere bando.id prima di collegare le voci

                match_pct = await _analizza_e_salva_voci(session, bando)
                bando.match_percentuale = match_pct
                bando.stato_verifica = matcher.stato_verifica_da_match(match_pct)
                session.add(bando)
                nuovi += 1

            session.add(
                FonteScanLog(fonte="anac_ocds", bandi_trovati=trovati, bandi_nuovi=nuovi)
            )
            session.commit()

    except Exception as exc:  # noqa: BLE001 - vogliamo loggare qualsiasi errore di rete/parsing
        errore = str(exc)
        with Session(engine) as session:
            session.add(FonteScanLog(fonte="anac_ocds", bandi_trovati=trovati, bandi_nuovi=nuovi, errore=errore))
            session.commit()


def avvia_scheduler() -> None:
    """Avvia il job periodico bandi solo se c'è una chiave Anthropic.
    Senza chiave l'API resta attiva per lo Scraper Aziende."""
    if not settings.anthropic_api_key:
        print("Scheduler bandi disattivato: ANTHROPIC_API_KEY non impostata (lo Scraper funziona comunque).")
        return
    scheduler.add_job(
        esegui_scansione,
        "interval",
        hours=settings.scan_interval_hours,
        id="scansione_periodica",
        next_run_time=datetime.utcnow(),
    )
    scheduler.start()
