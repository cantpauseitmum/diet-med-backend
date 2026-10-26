-- =========================================================
-- Wypełnienie tabeli dolegliwości (TDP)
-- =========================================================
TRUNCATE TABLE dolegliwosci RESTART IDENTITY CASCADE;
INSERT INTO dolegliwosci (kod) VALUES
('hashimoto'),
('insulinooporność'),
('cukrzyca'),
('nietolerancja histaminy'),
('nadciśnienie tętnicze'),
('wysoki poziom cholesterolu'),
('wysoki poziom trójglicerydów'),
('lipoedema'),
('nadwaga/otyłość'),
('SIBO'),
('IMO'),
('niedoczynność tarczycy') ON CONFLICT (kod) DO NOTHING;
