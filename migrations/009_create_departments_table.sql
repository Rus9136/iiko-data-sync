-- Создание таблицы departments для хранения подразделений
CREATE TABLE IF NOT EXISTS departments (
    id UUID PRIMARY KEY,
    parent_id UUID REFERENCES departments(id),
    code VARCHAR(50),
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) DEFAULT 'DEPARTMENT',
    taxpayer_id_number VARCHAR(50),
    
    -- Временные метки
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индекс для родительского ID
CREATE INDEX idx_departments_parent_id ON departments(parent_id);

-- Индекс для кода
CREATE INDEX idx_departments_code ON departments(code);

-- Индекс для типа
CREATE INDEX idx_departments_type ON departments(type);