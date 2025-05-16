-- Исправляем ограничение unique для поля code в таблице products
-- Удаляем старое ограничение
ALTER TABLE products DROP CONSTRAINT IF EXISTS unique_code;

-- Создаем функциональный индекс для ненулевых и непустых значений кода
CREATE UNIQUE INDEX idx_unique_non_empty_code ON products ((code)) 
WHERE code IS NOT NULL AND code != '';