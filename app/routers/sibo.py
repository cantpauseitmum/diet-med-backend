from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SiboProdukt
from app.schemas import SiboProduktOut

router = APIRouter(prefix="/api/sibo", tags=["SIBO Produkty"])

@router.get("/produkty", response_model=List[SiboProduktOut])
def get_sibo_products(
    q: Optional[str] = Query(None, description="Wyszukiwanie po nazwie / rodzaju produktu"),
    status: Optional[str] = Query(None, description="Filtrowanie: dozwolone, umiarkowane, zakazane"),
    db: Session = Depends(get_db)
):
    """
    Pobiera listę produktów z bazy danych dla SIBO.
    """
    query = db.query(SiboProdukt)

    if q:
        query = query.filter(SiboProdukt.rodzaj.ilike(f"%{q.strip()}%"))
    if status:
        query = query.filter(SiboProdukt.status == status.strip().lower())

    return query.order_by(SiboProdukt.rodzaj.asc()).all()
