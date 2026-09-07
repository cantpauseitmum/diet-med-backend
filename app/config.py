import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Diet-Med Backend API"
    VERSION: str = "1.0.0"
    
    # Baza danych (domyślnie łączy się z kontenerem diet-med-DB wewnątrz sieci dockera)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://diet_user:diet_password@diet-med-DB:5432/diet_med"
    )
    
    # Katalog na generowane pliki PDF
    PDF_OUTPUT_DIR: str = os.getenv("PDF_OUTPUT_DIR", "./generated_pdfs")
    
    # Konfiguracja serwera pocztowego SMTP
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "kontakt@diet-med.pl")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "True").lower() in ("true", "1", "yes")
    
    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
