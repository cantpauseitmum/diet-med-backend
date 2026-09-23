import os
import re
import glob
import logging
import hashlib
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.config import settings
from app.database import engine, Base
from app.routers import dolegliwosci, zgloszenia, produkty

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("diet_med")


@asynccontextmanager
async def lifespan(app: FastAPI):
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

            # Dynamiczna weryfikacja i synchronizacja danych produktów
            sync_product_tables(conn)

        logger.info("Połączenie z bazą danych i weryfikacja tabel przebiegły pomyślnie.")
    except Exception as e:
        logger.warning(f"Ostrzeżenie przy łączeniu z bazą danych na starcie: {e}")

    yield
    logger.info("Zamykanie serwisu Diet-Med Backend...")


# Inicjalizacja FastAPI z asynchronicznym cyklem życia lifespan
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API dla systemu Diet-Med: lista dolegliwości TDP, uniwersalna baza produktów, generowanie dynamicznych raportów PDF i obsługa zgłoszeń pacjentów.",
    lifespan=lifespan
)

# Konfiguracja CORS (umożliwia komunikację z frontendem)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dołączenie aktywnych routerów
app.include_router(dolegliwosci.router)
app.include_router(zgloszenia.router)
app.include_router(produkty.router)


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
    Dynamicznie weryfikuje i automatycznie inicjalizuje/aktualizuje tabele dolegliwosci oraz dowolne
    tabele produktów na podstawie plików w katalogu 'seeds/', gwarantując, że nawet na istniejących
    wolumenach Docker w Portainerze baza danych posiada najnowsze i kompletne zbiory danych.
    """
    seeds_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seeds")
    if not os.path.exists(seeds_dir):
        logger.warning(f"Katalog seeds nie istnieje: {seeds_dir}")
        return

    # 1. Zapewnienie pełnej listy dolegliwości TDP
    tdp_seed_path = os.path.join(seeds_dir, "02_seed_tdp.sql")
    if os.path.exists(tdp_seed_path):
        try:
            with open(tdp_seed_path, "r", encoding="utf-8") as f:
                tdp_sql = f.read()
            for stmt in tdp_sql.split(";"):
                clean = stmt.strip()
                if clean:
                    conn.execute(text(clean))
            logger.info("Załadowano bazową listę dolegliwości TDP.")
        except Exception as err:
            logger.error(f"Błąd podczas ładowania 02_seed_tdp.sql: {err}")
    else:
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

    # Czyszczenie ewentualnych zdublowanych rekordów (np. 'sibo' vs 'SIBO', 'insulinoopornosc' vs 'insulinooporność')
    try:
        conn.execute(text("DELETE FROM dolegliwosci WHERE LOWER(kod) = 'sibo' AND kod != 'SIBO'"))
        conn.execute(text("DELETE FROM dolegliwosci WHERE kod = 'insulinoopornosc' AND EXISTS (SELECT 1 FROM dolegliwosci WHERE kod = 'insulinooporność')"))
    except Exception as err:
        logger.warning(f"Ostrzeżenie przy czyszczeniu duplikatów w dolegliwosci: {err}")

    # 2. Dynamiczne wykrywanie i weryfikacja wszystkich plików seedów tabel produktów
    try:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS _seed_metadata (
                filename VARCHAR(100) PRIMARY KEY,
                checksum VARCHAR(64) NOT NULL
            );
        """))
    except Exception as e:
        logger.warning(f"Ostrzeżenie przy tworzeniu _seed_metadata: {e}")

    seed_files = sorted(glob.glob(os.path.join(seeds_dir, "*.sql")))
    for seed_path in seed_files:
        fn = os.path.basename(seed_path)
        if fn in ("01_init_schema.sql", "02_seed_tdp.sql"):
            continue

        try:
            with open(seed_path, "r", encoding="utf-8") as f:
                content = f.read()

            file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

            # Dynamicznie odczytaj nazwę tabeli z CREATE TABLE
            m_table = re.search(r"CREATE TABLE IF NOT EXISTS\s+([a-zA-Z0-9_]+)", content, re.IGNORECASE)
            if not m_table:
                continue
            table_name = m_table.group(1)

            # Policz oczekiwaną liczbę wierszy z instrukcji INSERT
            expected_count = len(re.findall(r"(?m)^\s*\('", content))

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

            stored_hash = None
            try:
                stored_hash = conn.execute(
                    text("SELECT checksum FROM _seed_metadata WHERE filename = :fn"),
                    {"fn": fn}
                ).scalar()
            except Exception:
                pass

            if not exists or stored_hash != file_hash or (expected_count > 0 and row_count != expected_count):
                logger.info(f"Dynamiczna inicjalizacja/aktualizacja tabeli '{table_name}' z {fn} (obecnie: {row_count}, oczekiwano: {expected_count})...")
                for stmt in content.split(";"):
                    clean_stmt = stmt.strip()
                    if clean_stmt:
                        conn.execute(text(clean_stmt))
                try:
                    conn.execute(
                        text("INSERT INTO _seed_metadata (filename, checksum) VALUES (:fn, :hash) ON CONFLICT (filename) DO UPDATE SET checksum = :hash"),
                        {"fn": fn, "hash": file_hash}
                    )
                except Exception:
                    pass
                logger.info(f"Pomyślnie załadowano seedy dla '{table_name}' ({expected_count} wierszy).")
            else:
                logger.info(f"Tabela '{table_name}' jest aktualna ({row_count} wierszy, plik: {fn}).")

            # Jeśli tabela reprezentuje zupełnie nową dolegliwość, dodaj ją ostrożnie do tabeli dolegliwosci
            ailment_derived = table_name.replace("_produkty", "").replace("produkty_", "")
            if ailment_derived:
                PL_TO_ASCII = str.maketrans({
                    'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n',
                    'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
                    'Ą': 'a', 'Ć': 'c', 'Ę': 'e', 'Ł': 'l', 'Ń': 'n',
                    'Ó': 'o', 'Ś': 's', 'Ź': 'z', 'Ż': 'z',
                    '/': '_', ' ': '_', '-': '_'
                })
                existing_kody = [r[0] for r in conn.execute(text("SELECT kod FROM dolegliwosci")).fetchall()]
                existing_norms = {
                    k.lower().strip().translate(PL_TO_ASCII).replace('/', '_').replace(' ', '_').replace('-', '_')
                    for k in existing_kody
                }
                derived_norm = ailment_derived.lower().strip().translate(PL_TO_ASCII).replace('/', '_').replace(' ', '_').replace('-', '_')
                if derived_norm not in existing_norms:
                    conn.execute(
                        text("INSERT INTO dolegliwosci (kod) VALUES (:kod) ON CONFLICT (kod) DO NOTHING"),
                        {"kod": ailment_derived}
                    )

        except Exception as err:
            logger.error(f"Błąd podczas weryfikacji seeda {fn}: {err}")

