from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import HashimotoProdukt
from app.schemas import HashimotoProduktOut

router = APIRouter(prefix="/api/hashimoto", tags=["Hashimoto Produkty"])

@router.get("/produkty", response_model=List[HashimotoProduktOut])
def get_hashimoto_products(
    q: Optional[str] = Query(None, description="Wyszukiwanie po nazwie / rodzaju produktu"),
    status: Optional[str] = Query(None, description="Filtrowanie: dozwolone, umiarkowane, zakazane"),
    db: Session = Depends(get_db)
):
    """
    Pobiera listę produktów z bazy danych dla Hashimoto.
    """
    query = db.query(HashimotoProdukt)

    if q:
        query = query.filter(HashimotoProdukt.rodzaj.ilike(f"%{q.strip()}%"))
    if status:
        query = query.filter(HashimotoProdukt.status == status.strip().lower())

    return query.order_by(HashimotoProdukt.rodzaj.asc()).all()
