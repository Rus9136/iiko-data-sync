-- Основная таблица продуктов IIKO
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY,
    deleted BOOLEAN DEFAULT FALSE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    num VARCHAR(50),
    code VARCHAR(50),
    parent_id UUID,
    tax_category_id UUID,
    category_id UUID,
    accounting_category_id UUID,
    
    -- Временные метки для отслеживания изменений
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Индексы
    CONSTRAINT fk_parent FOREIGN KEY (parent_id) REFERENCES products(id) ON DELETE SET NULL,
    UNIQUE (code),
    INDEX idx_deleted (deleted),
    INDEX idx_name (name),
    INDEX idx_num (num),
    INDEX idx_category (category_id),
    INDEX idx_parent (parent_id)
);

-- Таблица для модификаторов продуктов (many-to-many)
CREATE TABLE IF NOT EXISTS product_modifiers (
    id SERIAL PRIMARY KEY,
    product_id UUID NOT NULL,
    modifier_id UUID NOT NULL,
    position INTEGER,
    
    CONSTRAINT fk_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    CONSTRAINT fk_modifier FOREIGN KEY (modifier_id) REFERENCES products(id) ON DELETE CASCADE,
    UNIQUE KEY unique_product_modifier (product_id, modifier_id),
    INDEX idx_product_modifiers (product_id)
);

-- Таблица категорий
CREATE TABLE IF NOT EXISTS categories (
    id UUID PRIMARY KEY,
    name VARCHAR(255),
    deleted BOOLEAN DEFAULT FALSE,
    category_type VARCHAR(50), -- 'tax', 'product', 'accounting'
    parent_id UUID,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_parent_category FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL,
    INDEX idx_category_type (category_type)
);

-- Таблица для логирования синхронизации
CREATE TABLE IF NOT EXISTS sync_log (
    id SERIAL PRIMARY KEY,
    sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    entity_type VARCHAR(50),
    records_count INTEGER,
    status VARCHAR(20),
    error_message TEXT,
    details JSONB
);

-- Функция для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггер для автоматического обновления updated_at
CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_categories_updated_at BEFORE UPDATE ON categories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
