# Diet-Med Backend API (`diet-med-backend`)

REST API systemu **Diet-Med**, oparte o framework FastAPI, zoptymalizowane do wdrożenia w stacku **Portainer** oraz jako samodzielny mikroserwis.

## Funkcjonalności
- `GET /api/dolegliwosci` – zwraca paczkę danych z listą dolegliwości z bazy danych (ważną przez 1h z nagłówkiem `Cache-Control`).
- `POST /api/zgloszenia` – odbiera JSON z listą ID dolegliwości zaznaczonych jako „Tak”:
  - Pobiera wytyczne dietetyczne dla zaznaczonych dolegliwości,
  - Rozstrzyga konflikty (priorytet: `zakazane` > `ograniczone` > `dozwolone`, mniejsza ilość przy ograniczeniach, łączenie odmiennych komentarzy),
  - Generuje dokument PDF: `ograniczenia zywieniowe.pdf`,
  - Zapisuje zgłoszenie w bazie PostgreSQL,
  - Zwraca link do bezpośredniego pobrania pliku PDF.
- `GET /api/zgloszenia/pobierz-pdf/{filename}` – bezpośrednie pobieranie pliku PDF `ograniczenia zywieniowe.pdf`.
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
