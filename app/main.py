import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
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
        # Upewnienie się, że tabele bazowe istnieją
        Base.metadata.create_all(bind=engine)
        
        # Idempotentna migracja tabeli zgloszenia dla istniejących wolumenów baz danych
        with engine.begin() as conn:
            conn.execute(text("""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'zgloszenia') THEN
                        -- 1. Zezwól na NULL w kolumnie email
                        ALTER TABLE zgloszenia ALTER COLUMN email DROP NOT NULL;
                        
                        -- 2. Zmień status_wysylki na status, jeśli istnieje stara nazwa
                        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'zgloszenia' AND column_name = 'status_wysylki')
                           AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'zgloszenia' AND column_name = 'status') THEN
                            ALTER TABLE zgloszenia RENAME COLUMN status_wysylki TO status;
                        END IF;
                        
                        -- 3. Upewnij się, że kolumna status istnieje z domyślną wartością
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'zgloszenia' AND column_name = 'status') THEN
                            ALTER TABLE zgloszenia ADD COLUMN status VARCHAR(50) DEFAULT 'wygenerowano';
                        END IF;
                    END IF;
                END $$;
            """))
            
        logger.info("Połączenie z bazą danych i weryfikacja tabel przebiegły pomyślnie.")
    except Exception as e:
        logger.warning(f"Ostrzeżenie przy łączeniu z bazą danych na starcie: {e}")
