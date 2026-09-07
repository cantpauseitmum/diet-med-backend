import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.routers import dolegliwosci, zgloszenia, sibo

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("diet_med")

# Inicjalizacja FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API dla systemu Diet-Med: lista dolegliwości TDP, produkty SIBO, generowanie PDF i obsługa zgłoszeń pacjentów."
)

# Konfiguracja CORS (umożliwia komunikację z frontendem)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dołączenie routerów
app.include_router(dolegliwosci.router)
app.include_router(zgloszenia.router)
app.include_router(sibo.router)

@app.get("/health", tags=["System"])
def health_check():
    """
    Endpoint sprawdzający stan zdrowia serwisu backendu.
    """
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

@app.on_event("startup")
def on_startup():
    logger.info("Uruchamianie serwisu Diet-Med Backend...")
    try:
        # Upewnienie się, że tabele istnieją
        Base.metadata.create_all(bind=engine)
        logger.info("Połączenie z bazą danych i weryfikacja tabel przebiegły pomyślnie.")
    except Exception as e:
        logger.warning(f"Ostrzeżenie przy łączeniu z bazą danych na starcie: {e}")
