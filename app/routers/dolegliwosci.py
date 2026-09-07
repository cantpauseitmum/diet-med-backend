from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Dolegliwosc
from app.schemas import DolegliwosciPackageOut, DolegliwoscOut

router = APIRouter(prefix="/api/dolegliwosci", tags=["Dolegliwości"])

@router.get("", response_model=DolegliwosciPackageOut)
def get_dolegliwosci_package(response: Response, db: Session = Depends(get_db)):
    """
    Zwraca paczkę danych z listą dolegliwości pobranych z bazy danych.
    Paczka jest ważna przez 1 godzinę (3600 s).
    """
    items = db.query(Dolegliwosc).order_by(Dolegliwosc.id.asc()).all()
    
    # Ustawienie nagłówków HTTP cache'owania na 1 godzinę
    response.headers["Cache-Control"] = "public, max-age=3600"
    
    return DolegliwosciPackageOut(
        dolegliwosci=[DolegliwoscOut.model_validate(item) for item in items],
        expires_in_seconds=3600,
        generated_at=datetime.now(timezone.utc).isoformat()
    )
