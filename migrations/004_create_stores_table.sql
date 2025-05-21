-- Создание таблицы для складов
CREATE TABLE IF NOT EXISTS stores (
    id UUID PRIMARY KEY,
    parent_id UUID REFERENCES stores(id),
    code VARCHAR(50),
    name VARCHAR(255) NOT NULL,
    type VARCHAR(20) DEFAULT 'STORE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание индекса для ускорения поиска
CREATE INDEX IF NOT EXISTS idx_stores_parent_id ON stores(parent_id);