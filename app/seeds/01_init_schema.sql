-- =========================================================
-- Inicjalizacja schematu bazy danych Diet-Med (diet-med-DB)
-- =========================================================

-- Czyszczenie starych, nieużywanych tabel z poprzednich wersji
DROP TABLE IF EXISTS sibo_produkty CASCADE;
DROP TABLE IF EXISTS hashimoto_produkty CASCADE;

-- 1. Tabela z listą dolegliwości (TDP)
CREATE TABLE IF NOT EXISTS dolegliwosci (
    id SERIAL PRIMARY KEY,
    kod VARCHAR(100) NOT NULL UNIQUE
);

-- 2. Tabela produktów dla Insulinooporność
DROP TABLE IF EXISTS insulinoopornosc_produkty CASCADE;
CREATE TABLE IF NOT EXISTS insulinoopornosc_produkty (
    id SERIAL PRIMARY KEY,
    rodzaj VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('zalecane', 'dozwolone', 'ograniczone', 'zakazane')),
    ilosc NUMERIC(10, 2) NULL,
    jednostka VARCHAR(50) NULL,
    komentarz TEXT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_insulinoopornosc_produkty_rodzaj ON insulinoopornosc_produkty(rodzaj);
CREATE INDEX IF NOT EXISTS idx_insulinoopornosc_produkty_status ON insulinoopornosc_produkty(status);

-- 3. Tabela produktów dla Niedoczynność tarczycy
DROP TABLE IF EXISTS niedoczynnosc_tarczycy_produkty CASCADE;
CREATE TABLE IF NOT EXISTS niedoczynnosc_tarczycy_produkty (
    id SERIAL PRIMARY KEY,
    rodzaj VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('zalecane', 'dozwolone', 'ograniczone', 'zakazane')),
    ilosc NUMERIC(10, 2) NULL,
    jednostka VARCHAR(50) NULL,
    komentarz TEXT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_niedoczynnosc_tarczycy_produkty_rodzaj ON niedoczynnosc_tarczycy_produkty(rodzaj);
CREATE INDEX IF NOT EXISTS idx_niedoczynnosc_tarczycy_produkty_status ON niedoczynnosc_tarczycy_produkty(status);

-- Tabela zgłoszeń z formularza pacjentów
CREATE TABLE IF NOT EXISTS zgloszenia (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NULL,
    dolegliwosci_ids INTEGER[] NOT NULL,
    pdf_path VARCHAR(255) NULL,
    status VARCHAR(50) DEFAULT 'wygenerowano',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
