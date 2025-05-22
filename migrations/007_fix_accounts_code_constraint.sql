-- Исправление ограничения уникальности для кода счета
-- Удаляем старое ограничение
ALTER TABLE accounts DROP CONSTRAINT IF EXISTS accounts_code_key;

-- Добавляем новое ограничение, которое позволяет NULL но не пустые строки
ALTER TABLE accounts ADD CONSTRAINT accounts_code_unique 
    UNIQUE (code) 
    DEFERRABLE INITIALLY DEFERRED;

-- Обновляем пустые строки в код на NULL
UPDATE accounts SET code = NULL WHERE code = '';

-- Добавляем проверочное ограничение для предотвращения пустых строк
ALTER TABLE accounts ADD CONSTRAINT accounts_code_not_empty 
    CHECK (code IS NULL OR code <> '');