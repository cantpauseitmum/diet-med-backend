from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY
from app.database import Base

class Dolegliwosc(Base):
    __tablename__ = "dolegliwosci"

    id = Column(Integer, primary_key=True, index=True)
    kod = Column(String(100), unique=True, nullable=False, index=True)

class SiboProdukt(Base):
    __tablename__ = "sibo_produkty"

    id = Column(Integer, primary_key=True, index=True)
    rodzaj = Column(String(255), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True) # 'dozwolone', 'umiarkowane', 'zakazane'
    ilosc = Column(Numeric(10, 2), nullable=True)
    jednostka = Column(String(50), nullable=True)
    komentarz = Column(Text, nullable=True)

class Zgloszenie(Base):
    __tablename__ = "zgloszenia"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    dolegliwosci_ids = Column(ARRAY(Integer), nullable=False)
    pdf_path = Column(String(255), nullable=True)
    status = Column(String(50), default="wygenerowano")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
