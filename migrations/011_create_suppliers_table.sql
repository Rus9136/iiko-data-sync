-- Создание таблицы suppliers для хранения поставщиков
CREATE TABLE IF NOT EXISTS suppliers (
    id UUID PRIMARY KEY,
    code VARCHAR(50),
    name VARCHAR(255) NOT NULL,
    login VARCHAR(100),
    card_number VARCHAR(50),
    taxpayer_id_number VARCHAR(50),
    snils VARCHAR(50),
    deleted BOOLEAN DEFAULT FALSE,
    is_supplier BOOLEAN DEFAULT TRUE,
    is_employee BOOLEAN DEFAULT FALSE,
    is_client BOOLEAN DEFAULT FALSE,
    represents_store BOOLEAN DEFAULT FALSE,
    
    -- Временные метки
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для производительности
CREATE INDEX idx_suppliers_code ON suppliers(code);
CREATE INDEX idx_suppliers_name ON suppliers(name);
CREATE INDEX idx_suppliers_deleted ON suppliers(deleted);

-- Комментарии к таблице
COMMENT ON TABLE suppliers IS 'Поставщики';
COMMENT ON COLUMN suppliers.id IS 'Уникальный идентификатор';
COMMENT ON COLUMN suppliers.code IS 'Код поставщика';
COMMENT ON COLUMN suppliers.name IS 'Наименование поставщика';
COMMENT ON COLUMN suppliers.login IS 'Логин';
COMMENT ON COLUMN suppliers.card_number IS 'Номер карты';
COMMENT ON COLUMN suppliers.taxpayer_id_number IS 'ИНН';
COMMENT ON COLUMN suppliers.snils IS 'СНИЛС';
COMMENT ON COLUMN suppliers.deleted IS 'Признак удаления';
COMMENT ON COLUMN suppliers.is_supplier IS 'Является поставщиком';
COMMENT ON COLUMN suppliers.is_employee IS 'Является сотрудником';
COMMENT ON COLUMN suppliers.is_client IS 'Является клиентом';
COMMENT ON COLUMN suppliers.represents_store IS 'Представляет склад';