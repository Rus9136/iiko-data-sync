-- Миграция: добавление поля storned в таблицу sales
ALTER TABLE sales ADD COLUMN IF NOT EXISTS storned BOOLEAN DEFAULT FALSE;