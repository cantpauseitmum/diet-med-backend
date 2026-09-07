FROM python:3.12-slim

LABEL maintainer="Diet-Med Team"
LABEL description="Backend API container for Diet-Med"

# Ustawienia środowiska Pythona
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalacja zależności systemowych (m.in. czcionki do PDF i biblioteki pomocnicze)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Instalacja zależności Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiowanie kodu aplikacji
COPY app/ ./app

# Utworzenie katalogu na pliki PDF
RUN mkdir -p /app/generated_pdfs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
