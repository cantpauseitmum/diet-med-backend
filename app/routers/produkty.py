from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from app.database import get_db
from app.schemas import ProduktBaseOut
from app.routers.dolegliwosci import find_ailment_table

router = APIRouter(prefix="/api/produkty", tags=["Uniwersalne Produkty"])


@router.get("/{dolegliwosc}", response_model=List[ProduktBaseOut])
def get_products_by_ailment(
    dolegliwosc: str,
    q: Optional[str] = Query(None, description="Wyszukiwanie po nazwie / rodzaju produktu"),
    status: Optional[str] = Query(None, description="Filtrowanie: dozwolone, umiarkowane, zakazane"),
    db: Session = Depends(get_db)
):
    """
    Dynamicznie pobiera listę produktów dla DOWOLNEJ dolegliwości zarejestrowanej w bazie danych.
    Automatycznie odnajduje odpowiednią tabelę produktów w PostgreSQL.
    """
    # 1. Pobranie listy tabel z bazy danych
    existing_tables = set(t.lower() for t in inspect(db.get_bind()).get_table_names())

    table_name = find_ailment_table(dolegliwosc, existing_tables)
    if not table_name:
        raise HTTPException(
            status_code=404,
            detail=f"Nie odnaleziono bazy produktów dla dolegliwości '{dolegliwosc}'."
        )

    # 2. Dynamiczne budowanie zapytania SQL z zabezpieczeniem parametrów
    conditions = []
    params = {}

    if q and q.strip():
        conditions.append("LOWER(rodzaj) LIKE LOWER(:q)")
        params["q"] = f"%{q.strip()}%"

    if status and status.strip():
        conditions.append("status = :status")
        params["status"] = status.strip().lower()

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query_sql = text(f"""
        SELECT id, rodzaj, status, ilosc, jednostka, komentarz
        FROM {table_name}
        {where_clause}
        ORDER BY rodzaj ASC
    """)

    rows = db.execute(query_sql, params).fetchall()

    return [
        ProduktBaseOut(
            id=r[0],
            rodzaj=r[1],
            status=r[2],
            ilosc=r[3],
            jednostka=r[4],
            komentarz=r[5]
        )
        for r in rows
    ]
