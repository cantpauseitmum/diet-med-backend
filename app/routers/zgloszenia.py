import os
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.config import settings
from app.models import Dolegliwosc, SiboProdukt, Zgloszenie
from app.schemas import ZgloszenieCreate, ZgloszenieResponse
from app.pdf_generator import resolve_product_conflicts, generate_restrictions_pdf
from app.email_sender import send_email_with_pdf

router = APIRouter(prefix="/api/zgloszenia", tags=["Zgłoszenia i PDF"])

@router.post("", response_model=ZgloszenieResponse)
def submit_form(data: ZgloszenieCreate, db: Session = Depends(get_db)):
    """
    Odbiera JSON z adresem e-mail oraz numerami ID dolegliwości zaznaczonych jako 'Tak'.
    Pobiera ograniczenia z bazy, rozstrzyga konflikty, generuje plik PDF 'ograniczenia zywieniowe.pdf'
    i wysyła go na podany adres e-mail.
    """
    # 1. Weryfikacja wybranych dolegliwości
    ailment_records = db.query(Dolegliwosc).filter(Dolegliwosc.id.in_(data.dolegliwosci)).all()
    selected_names = [a.kod for a in ailment_records]
    
    # 2. Pobranie produktów dla wybranych dolegliwości
    raw_products: List[dict] = []
    
    for ailment in ailment_records:
        kod_lower = ailment.kod.lower()
        if "sibo" in kod_lower:
            sibo_items = db.query(SiboProdukt).all()
            for p in sibo_items:
                raw_products.append({
                    "rodzaj": p.rodzaj,
                    "status": p.status,
                    "ilosc": p.ilosc,
                    "jednostka": p.jednostka,
                    "komentarz": p.komentarz,
                    "dolegliwosc": ailment.kod
                })
        else:
            # Sprawdzenie czy w bazie istnieje dedykowana tabela dla innej dolegliwości
            table_name = f"{kod_lower.replace('/', '_').replace(' ', '_')}_produkty"
            try:
                sql_check = text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :t)"
                )
                exists = db.execute(sql_check, {"t": table_name}).scalar()
                if exists:
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
            except Exception:
                pass

    # Jeśli nie ma jeszcze tabeli dla wybranej dolegliwości i lista produktów jest pusta,
    # w celach demonstracyjnych raport zawiera produkty SIBO jako bazę
    if not raw_products and ailment_records:
        sibo_items = db.query(SiboProdukt).all()
        for p in sibo_items:
            raw_products.append({
                "rodzaj": p.rodzaj,
                "status": p.status,
                "ilosc": p.ilosc,
                "jednostka": p.jednostka,
                "komentarz": p.komentarz,
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

    # 5. Wysłanie wiadomości e-mail z załącznikiem PDF
    email_sent = send_email_with_pdf(
        to_email=data.email,
        pdf_path=pdf_full_path,
        filename="ograniczenia zywieniowe.pdf"
    )

    # 6. Rejestracja w bazie danych (tabela zgloszenia)
    new_sub = Zgloszenie(
        email=data.email,
        dolegliwosci_ids=data.dolegliwosci,
        pdf_path=pdf_filename,
        status_wysylki="wyslano" if email_sent else "zapisano_lokalnie"
    )
    db.add(new_sub)
    db.commit()

    return ZgloszenieResponse(
        status="success",
        message="Formularz został pomyślnie przetworzony. Zestawienie PDF zostało wygenerowane.",
        email=data.email,
        dolegliwosci_wybrane=selected_names,
        pdf_filename=pdf_filename,
        pdf_download_url=f"/api/zgloszenia/pobierz-pdf/{pdf_filename}",
        email_wyslany=email_sent
    )


@router.get("/pobierz-pdf/{filename}")
def download_pdf(filename: str):
    """
    Udostępnia do bezpośredniego pobrania wygenerowany plik PDF.
    """
    # Zabezpieczenie przed path traversal
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(settings.PDF_OUTPUT_DIR, safe_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Plik PDF nie został znaleziony.")

    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename="ograniczenia zywieniowe.pdf"
    )
