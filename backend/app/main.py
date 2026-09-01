from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import bandi, scraper
from app.services.scheduler import avvia_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    avvia_scheduler()
    yield


app = FastAPI(title="BioTitan Tender Intelligence + Scraper Aziende API", lifespan=lifespan)

# In produzione, limita allow_origins al dominio dove è ospitato il CRM
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def verifica_token(x_api_token: str = Header(...)):
    if x_api_token != settings.crm_api_token:
        raise HTTPException(status_code=401, detail="Token non valido")


app.include_router(bandi.router, dependencies=[Depends(verifica_token)])
app.include_router(scraper.router, dependencies=[Depends(verifica_token)])


@app.get("/health")
def health():
    return {"status": "ok", "moduli": ["bandi", "scraper"]}
