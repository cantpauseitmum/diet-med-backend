# Diet-Med Backend API (`diet-med-backend`)

REST API systemu **Diet-Med**, oparte o framework FastAPI, zoptymalizowane do wdrożenia w stacku **Portainer** oraz jako samodzielny mikroserwis.

## Funkcjonalności
- `GET /api/dolegliwosci` – zwraca paczkę danych z listą dolegliwości z bazy danych (ważną przez 1h z nagłówkiem `Cache-Control`).
- `POST /api/zgloszenia` – odbiera JSON z adresem e-mail i listą ID dolegliwości zaznaczonych jako „Tak”:
  - Pobiera wytyczne dietetyczne dla zaznaczonych dolegliwości,
  - Rozstrzyga konflikty (priorytet: `zakazane` > `ograniczone` > `dozwolone`, mniejsza ilość przy ograniczeniach, łączenie odmiennych komentarzy),
  - Generuje dokument PDF: `ograniczenia zywieniowe.pdf`,
  - Wysyła e-mail z załącznikiem PDF i formułą grzecznościową,
  - Zapisuje zgłoszenie w bazie PostgreSQL.
- `GET /api/zgloszenia/pobierz-pdf/{filename}` – udostępnia wygenerowany plik PDF do bezpośredniego pobrania.
- `GET /api/sibo/produkty` – wyszukiwanie produktów SIBO wg nazwy (`rodzaj`) i statusu.
- `GET /docs` – interaktywna dokumentacja Swagger UI.

## Uruchomienie lokalne (Docker)

```bash
docker build -t diet-med-backend .
docker run -d \
  --name diet-med-backend \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql+psycopg://diet_user:diet_password@localhost:5432/diet_med" \
  diet-med-backend
```

## Publikacja na GitHub (jako osobne repozytorium)

```bash
cd diet-med-backend
git init
git add .
git commit -m "Initial commit: diet-med-backend API with PDF generation and email dispatcher"
git branch -M main
git remote add origin git@github.com:TWOJ_USER/diet-med-backend.git
git push -u origin main
```
