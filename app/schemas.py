from typing import Optional, List
from pydantic import BaseModel, EmailStr

class DolegliwoscOut(BaseModel):
    id: int
    kod: str

    class Config:
        from_attributes = True

class DolegliwosciPackageOut(BaseModel):
    dolegliwosci: List[DolegliwoscOut]
    expires_in_seconds: int = 3600
    generated_at: str

class ZgloszenieCreate(BaseModel):
    email: EmailStr
    dolegliwosci: List[int] # ID dolegliwości zaznaczonych jako "tak"

class ZgloszenieResponse(BaseModel):
    status: str
    message: str
    email: str
    dolegliwosci_wybrane: List[str]
    pdf_filename: str
    pdf_download_url: Optional[str] = None
    email_wyslany: bool

class SiboProduktOut(BaseModel):
    id: int
    rodzaj: str
    status: str
    ilosc: Optional[float] = None
    jednostka: Optional[str] = None
    komentarz: Optional[str] = None

    class Config:
        from_attributes = True
