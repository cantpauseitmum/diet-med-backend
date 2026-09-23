-- =========================================================
-- Wypełnienie tabeli dolegliwości (TDP)
-- =========================================================
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
