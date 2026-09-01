from sqlmodel import SQLModel, Session, create_engine

from app.config import settings

engine = create_engine(settings.database_url, echo=False)


def init_db() -> None:
    """Crea le tabelle se non esistono già. Da chiamare all'avvio dell'app."""
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
