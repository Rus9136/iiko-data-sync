-- Создание схемы базы данных для IIKO данных

-- Таблица групп продуктов
CREATE TABLE IF NOT EXISTS product_groups (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(100),
    parent_id UUID,
    is_deleted BOOLEAN DEFAULT FALSE,
    
    CONSTRAINT fk_parent_group FOREIGN KEY (parent_id) REFERENCES product_groups(id)
);

-- Таблица категорий
CREATE TABLE IF NOT EXISTS product_categories (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE
);

-- Таблица единиц измерения
CREATE TABLE IF NOT EXISTS measurement_units (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    short_name VARCHAR(20),
    is_deleted BOOLEAN DEFAULT FALSE
);

-- Основная таблица продуктов
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(100),
    article VARCHAR(100),
    description TEXT,
    
    -- Категории и группы
    parent_id UUID,
    category_id UUID,
    group_id UUID,
    
    -- Единицы измерения
    main_unit VARCHAR(50),
    unit_weight DECIMAL(10, 3),
    
    -- Тип продукта
    product_type VARCHAR(50),
    is_deleted BOOLEAN DEFAULT FALSE,
    is_hidden BOOLEAN DEFAULT FALSE,
    
    -- Цены и себестоимость
    default_price DECIMAL(10, 2),
    cost_price DECIMAL(10, 2),
    
    -- Дополнительные флаги
    use_balance_for_sell BOOLEAN DEFAULT TRUE,
    can_be_sold BOOLEAN DEFAULT TRUE,
    
    -- Временные метки
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    
    -- Дополнительные данные в JSON
    additional_info JSONB,
    
    CONSTRAINT fk_parent FOREIGN KEY (parent_id) REFERENCES products(id),
    CONSTRAINT fk_category FOREIGN KEY (category_id) REFERENCES product_categories(id),
    CONSTRAINT fk_group FOREIGN KEY (group_id) REFERENCES product_groups(id)
);

-- Таблица для отслеживания синхронизации
CREATE TABLE IF NOT EXISTS sync_log (
    id SERIAL PRIMARY KEY,
    sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    entity_type VARCHAR(50),
    records_count INTEGER,
    status VARCHAR(20),
    error_message TEXT
);

-- Индексы для оптимизации
CREATE INDEX idx_products_code ON products(code);
CREATE INDEX idx_products_name ON products(name);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_group ON products(group_id);
CREATE INDEX idx_products_updated_at ON products(updated_at);
CREATE INDEX idx_products_deleted ON products(is_deleted);
CREATE INDEX idx_sync_log_date ON sync_log(sync_date DESC);