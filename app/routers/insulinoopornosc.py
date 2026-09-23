from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import InsulinoopornoscProdukt
from app.schemas import InsulinoopornoscProduktOut

router = APIRouter(prefix="/api/insulinoopornosc", tags=["Insulinooporność Produkty"])

@router.get("/produkty", response_model=List[InsulinoopornoscProduktOut])
def get_insulinoopornosc_products(
    q: Optional[str] = Query(None, description="Wyszukiwanie po nazwie / rodzaju produktu"),
    status: Optional[str] = Query(None, description="Filtrowanie: dozwolone, umiarkowane, zakazane"),
    db: Session = Depends(get_db)
):
    """
    Pobiera listę produktów z bazy danych dla Insulinooporności.
    """
    query = db.query(InsulinoopornoscProdukt)

    if q:
        query = query.filter(InsulinoopornoscProdukt.rodzaj.ilike(f"%{q.strip()}%"))
    if status:
        query = query.filter(InsulinoopornoscProdukt.status == status.strip().lower())

    return query.order_by(InsulinoopornoscProdukt.rodzaj.asc()).all()
