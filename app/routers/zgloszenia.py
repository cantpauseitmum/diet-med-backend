import os
import uuid
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from app.database import get_db
from app.config import settings
from app.models import Dolegliwosc, Zgloszenie
from app.schemas import ZgloszenieCreate, ZgloszenieResponse
from app.pdf_generator import resolve_product_conflicts, generate_restrictions_pdf
from app.routers.dolegliwosci import find_ailment_table

logger = logging.getLogger("diet_med")

router = APIRouter(prefix="/api/zgloszenia", tags=["Zgłoszenia i PDF"])

@router.post("", response_model=ZgloszenieResponse)
def submit_form(data: ZgloszenieCreate, db: Session = Depends(get_db)):
    """
    Odbiera JSON z numerami ID dolegliwości zaznaczonych jako 'Tak' (oraz opcjonalnym mailem).
    Pobiera ograniczenia z bazy, rozstrzyga konflikty, generuje plik PDF 'ograniczenia zywieniowe.pdf'
    i zwraca bezpośredni URL do pobrania dokumentu.
    """
    # 1. Weryfikacja wybranych dolegliwości
    ailment_records = db.query(Dolegliwosc).filter(Dolegliwosc.id.in_(data.dolegliwosci)).all()
    selected_names = [a.kod for a in ailment_records]
    
    # 2. Pobranie produktów dla wybranych dolegliwości z ich dedykowanych tabel
    raw_products: List[dict] = []
    
    existing_tables = set(t.lower() for t in inspect(db.get_bind()).get_table_names())
    
    for ailment in ailment_records:
        table_name = find_ailment_table(ailment.kod, existing_tables)
        if table_name:
            try:
                sql_fetch = text(f"SELECT rodzaj, status, ilosc, jednostka, komentarz FROM {table_name}")
                rows = db.execute(sql_fetch).fetchall()
                for r in rows:
                    raw_products.append({
                        "rodzaj": r[0],
                        "status": r[1],
                        "ilosc": r[2],
                        "jednostka": r[3],
                        "komentarz": r[4],
                        "dolegliwosc": ailment.kod
                    })
                logger.info(f"Pobrano {len(rows)} produktów z tabeli '{table_name}' dla dolegliwości '{ailment.kod}'.")
            except Exception as err:
                logger.error(f"Błąd podczas pobierania produktów z tabeli '{table_name}' dla dolegliwości '{ailment.kod}': {err}")
        else:
            logger.warning(f"Brak dedykowanej tabeli produktów dla dolegliwości '{ailment.kod}'.")

    # Jeśli żadna z zaznaczonych dolegliwości nie miała dedykowanej tabeli,
    # w celach demonstracyjnych raport zawiera pierwszą dostępną bazę (np. sibo_produkty)
    if not raw_products and ailment_records:
        fallback_table = "sibo_produkty" if "sibo_produkty" in existing_tables else next((t for t in existing_tables if t.endswith("_produkty")), None)
        if fallback_table:
            rows = db.execute(text(f"SELECT rodzaj, status, ilosc, jednostka, komentarz FROM {fallback_table}")).fetchall()
            for r in rows:
                raw_products.append({
                    "rodzaj": r[0],
                    "status": r[1],
                    "ilosc": r[2],
                    "jednostka": r[3],
                    "komentarz": r[4],
                    "dolegliwosc": "Ogólne wytyczne"
                })

    # 3. Rozstrzygnięcie konfliktów zgodnie z logiką:
    # priorytet zakazane > ograniczone > dozwolone, min ilosc, połączenie komentarzy
    merged_products = resolve_product_conflicts(raw_products)

    # 4. Generowanie pliku PDF
    os.makedirs(settings.PDF_OUTPUT_DIR, exist_ok=True)
    pdf_filename = f"ograniczenia_zywieniowe_{uuid.uuid4().hex[:8]}.pdf"
    pdf_full_path = os.path.join(settings.PDF_OUTPUT_DIR, pdf_filename)

    generate_restrictions_pdf(
        email=data.email,
        selected_ailments=selected_names,
        merged_products=merged_products,
        output_filepath=pdf_full_path
    )

    # 5. Rejestracja w bazie danych (tabela zgloszenia)
    new_sub = Zgloszenie(
        email=data.email,
        dolegliwosci_ids=data.dolegliwosci,
        pdf_path=pdf_filename,
        status="wygenerowano"
    )
    db.add(new_sub)
    db.commit()

    return ZgloszenieResponse(
        status="success",
        message="Plik PDF z ograniczeniami żywieniowymi został pomyślnie przygotowany.",
        email=data.email,
        dolegliwosci_wybrane=selected_names,
        pdf_filename=pdf_filename,
        pdf_download_url=f"/api/zgloszenia/pobierz-pdf/{pdf_filename}"
    )


@router.get("/pobierz-pdf/{filename}")
def download_pdf(filename: str):
    """
    Udostępnia wygenerowany plik PDF do bezpośredniego pobrania.
    """
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(settings.PDF_OUTPUT_DIR, safe_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Plik PDF nie został znaleziony.")

    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename="ograniczenia zywieniowe.pdf"
    )
