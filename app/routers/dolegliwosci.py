from datetime import datetime, timezone
from typing import Optional, Set
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models import Dolegliwosc
from app.schemas import DolegliwosciPackageOut, DolegliwoscOut

router = APIRouter(prefix="/api/dolegliwosci", tags=["Dolegliwości"])

PL_TO_ASCII = str.maketrans({
    'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n',
    'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
    'Ą': 'a', 'Ć': 'c', 'Ę': 'e', 'Ł': 'l', 'Ń': 'n',
    'Ó': 'o', 'Ś': 's', 'Ź': 'z', 'Ż': 'z',
    '/': '_', ' ': '_', '-': '_'
})

IGNORED_TABLES = {"dolegliwosci", "zgloszenia", "alembic_version"}

def find_ailment_table(kod: str, existing_tables: Set[str]) -> Optional[str]:
    """
    Sprawdza, czy w bazie danych istnieje dedykowana tabela produktów/zaleceń dla podanej dolegliwości.
    """
    kod_raw = kod.lower().strip()
    clean_raw = kod_raw.replace('/', '_').replace(' ', '_').replace('-', '_')
    clean_norm = clean_raw.translate(PL_TO_ASCII)
    
    candidates = [
        f"{clean_norm}_produkty",
        f"{clean_raw}_produkty",
        f"produkty_{clean_norm}",
        f"produkty_{clean_raw}",
        clean_norm,
        clean_raw
    ]
    
    if "sibo" in kod_raw:
        candidates.insert(0, "sibo_produkty")
    if "imo" in kod_raw:
        candidates.insert(0, "imo_produkty")

    for cand in candidates:
        if cand in existing_tables and cand not in IGNORED_TABLES:
            return cand
            
    return None

@router.get("", response_model=DolegliwosciPackageOut)
def get_dolegliwosci_package(response: Response, db: Session = Depends(get_db)):
    """
    Zwraca paczkę danych z listą dolegliwości pobranych z bazy danych wraz z informacją,
    czy w bazie istnieje tabela z produktami/ograniczeniami dla danej dolegliwości (flaga dostepna).
    Paczka jest ważna przez 1 godzinę (3600 s).
    """
    items = db.query(Dolegliwosc).order_by(Dolegliwosc.id.asc()).all()
    
    # Pobranie listy tabel z bazy danych
    existing_tables = set(
        row[0].lower() for row in db.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        ).fetchall()
    )
    
    dolegliwosci_list = []
    for item in items:
        table_name = find_ailment_table(item.kod, existing_tables)
        dolegliwosci_list.append(DolegliwoscOut(
            id=item.id,
            kod=item.kod,
            dostepna=table_name is not None,
            tabela=table_name
        ))
    
    # Ustawienie nagłówków HTTP cache'owania na 1 godzinę
    response.headers["Cache-Control"] = "public, max-age=3600"
    
    return DolegliwosciPackageOut(
        dolegliwosci=dolegliwosci_list,
        expires_in_seconds=3600,
        generated_at=datetime.now(timezone.utc).isoformat()
    )
