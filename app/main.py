import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.config import settings
from app.database import engine, Base
from app.routers import dolegliwosci, zgloszenia, sibo, hashimoto

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
    description="API dla systemu Diet-Med: lista dolegliwości TDP, produkty SIBO, produkty Hashimoto, generowanie PDF i obsługa zgłoszeń pacjentów."
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
app.include_router(hashimoto.router)

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

def sync_product_tables(conn):
    """
    Weryfikuje i automatycznie inicjalizuje/aktualizuje tabele dolegliwosci,
    sibo_produkty i hashimoto_produkty, gwarantując, że nawet na istniejących
    wolumenach Docker w Portainerze baza danych posiada najnowsze i kompletne zbiory produktów.
    """
    seeds_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seeds")
    
    # 1. Zapewnienie pełnej listy dolegliwości TDP
    dolegliwosci_kody = [
        "hashimoto", "insulinooporność", "cukrzyca", "nietolerancja histaminy",
        "nadciśnienie tętnicze", "wysoki poziom cholesterolu", "wysoki poziom trójglicerydów",
        "lipoedema", "nadwaga/otyłość", "SIBO", "IMO", "niedoczynność tarczycy"
    ]
    for kod in dolegliwosci_kody:
        conn.execute(
            text("INSERT INTO dolegliwosci (kod) VALUES (:kod) ON CONFLICT (kod) DO NOTHING"),
            {"kod": kod}
        )

    # 2. Weryfikacja tabel z produktami
    tables_to_check = [
        ("sibo_produkty", "03_seed_sibo.sql", 350),
        ("hashimoto_produkty", "04_seed_hashimoto.sql", 350)
    ]

    for table_name, seed_file, min_expected_count in tables_to_check:
        try:
            check_sql = text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = '{table_name}'
                );
            """)
            exists = conn.execute(check_sql).scalar()
            
            row_count = 0
            if exists:
                count_sql = text(f"SELECT COUNT(*) FROM {table_name}")
                row_count = conn.execute(count_sql).scalar() or 0
                
            if not exists or row_count < min_expected_count:
                seed_path = os.path.join(seeds_dir, seed_file)
                if os.path.exists(seed_path):
                    logger.info(f"Inicjalizacja/aktualizacja tabeli '{table_name}' (obecnie: {row_count} wierszy, oczekiwano min. {min_expected_count})...")
                    with open(seed_path, "r", encoding="utf-8") as f:
                        sql_commands = f.read()
                    for stmt in sql_commands.split(";"):
                        clean_stmt = stmt.strip()
                        if clean_stmt:
                            conn.execute(text(clean_stmt))
                    logger.info(f"Pomyślnie załadowano seedy dla '{table_name}'.")
                else:
                    logger.warning(f"Plik seed {seed_path} nie został odnaleziony!")
            else:
                logger.info(f"Tabela '{table_name}' jest aktualna ({row_count} wierszy).")
        except Exception as err:
            logger.error(f"Błąd podczas weryfikacji tabeli '{table_name}': {err}")

@app.on_event("startup")
def on_startup():
    logger.info("Uruchamianie serwisu Diet-Med Backend...")
    try:
        # Upewnienie się, że tabele bazowe istnieją
        Base.metadata.create_all(bind=engine)
        
        with engine.begin() as conn:
            # Idempotentna migracja tabeli zgloszenia dla istniejących wolumenów baz danych
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
            
            # Synchronizacja i weryfikacja danych produktów dla SIBO i Hashimoto
            sync_product_tables(conn)
            
        logger.info("Połączenie z bazą danych i weryfikacja tabel przebiegły pomyślnie.")
    except Exception as e:
        logger.warning(f"Ostrzeżenie przy łączeniu z bazą danych na starcie: {e}")
