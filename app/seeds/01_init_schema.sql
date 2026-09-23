-- =========================================================
-- Inicjalizacja schematu bazy danych Diet-Med (diet-med-DB)
-- =========================================================

-- 1. Tabela z listą dolegliwości (TDP)
CREATE TABLE IF NOT EXISTS dolegliwosci (
    id SERIAL PRIMARY KEY,
    kod VARCHAR(100) NOT NULL UNIQUE
);

-- 2. Tabela produktów dla SIBO
DROP TABLE IF EXISTS sibo_produkty CASCADE;
CREATE TABLE IF NOT EXISTS sibo_produkty (
    id SERIAL PRIMARY KEY,
    rodzaj VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('dozwolone', 'umiarkowane', 'zakazane')),
    ilosc NUMERIC(10, 2) NULL,
    jednostka VARCHAR(50) NULL,
    komentarz TEXT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sibo_rodzaj ON sibo_produkty(rodzaj);
CREATE INDEX IF NOT EXISTS idx_sibo_status ON sibo_produkty(status);

-- 3. Tabela produktów dla Hashimoto
DROP TABLE IF EXISTS hashimoto_produkty CASCADE;
CREATE TABLE IF NOT EXISTS hashimoto_produkty (
    id SERIAL PRIMARY KEY,
    rodzaj VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('dozwolone', 'umiarkowane', 'zakazane')),
    ilosc NUMERIC(10, 2) NULL,
    jednostka VARCHAR(50) NULL,
    komentarz TEXT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_hashimoto_rodzaj ON hashimoto_produkty(rodzaj);
CREATE INDEX IF NOT EXISTS idx_hashimoto_status ON hashimoto_produkty(status);

-- 4. Tabela produktów dla Insulinooporności
DROP TABLE IF EXISTS insulinoopornosc_produkty CASCADE;
CREATE TABLE IF NOT EXISTS insulinoopornosc_produkty (
    id SERIAL PRIMARY KEY,
    rodzaj VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('dozwolone', 'umiarkowane', 'zakazane')),
    ilosc NUMERIC(10, 2) NULL,
    jednostka VARCHAR(50) NULL,
    komentarz TEXT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_insulinoopornosc_rodzaj ON insulinoopornosc_produkty(rodzaj);
CREATE INDEX IF NOT EXISTS idx_insulinoopornosc_status ON insulinoopornosc_produkty(status);

-- 5. Tabela zgłoszeń z formularza pacjentów
CREATE TABLE IF NOT EXISTS zgloszenia (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NULL,
    dolegliwosci_ids INTEGER[] NOT NULL,
    pdf_path VARCHAR(255) NULL,
    status VARCHAR(50) DEFAULT 'wygenerowano',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
