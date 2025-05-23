-- Создание таблицы prices для хранения цен товаров по подразделениям
CREATE TABLE IF NOT EXISTS prices (
    id SERIAL PRIMARY KEY,
    department_id UUID NOT NULL REFERENCES departments(id),
    product_id UUID NOT NULL REFERENCES products(id),
    product_size_id UUID,
    price_type VARCHAR(50) DEFAULT 'BASE',
    date_from DATE NOT NULL,
    date_to DATE NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    tax_category_id UUID,
    tax_category_enabled BOOLEAN DEFAULT FALSE,
    included BOOLEAN DEFAULT TRUE,
    dish_of_day BOOLEAN DEFAULT FALSE,
    flyer_program BOOLEAN DEFAULT FALSE,
    document_id UUID,
    schedule TEXT,
    
    -- Временные метки
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Уникальный индекс для предотвращения дублирования
    UNIQUE(department_id, product_id, product_size_id, price_type, date_from, date_to)
);

-- Индексы для производительности
CREATE INDEX idx_prices_department_id ON prices(department_id);
CREATE INDEX idx_prices_product_id ON prices(product_id);
CREATE INDEX idx_prices_date_range ON prices(date_from, date_to);
CREATE INDEX idx_prices_price_type ON prices(price_type);

-- Комментарии к таблице
COMMENT ON TABLE prices IS 'Цены товаров по подразделениям';
COMMENT ON COLUMN prices.department_id IS 'ID подразделения';
COMMENT ON COLUMN prices.product_id IS 'ID товара';
COMMENT ON COLUMN prices.product_size_id IS 'ID размера товара (если применимо)';
COMMENT ON COLUMN prices.price_type IS 'Тип цены (BASE, DELIVERY и т.д.)';
COMMENT ON COLUMN prices.date_from IS 'Дата начала действия цены';
COMMENT ON COLUMN prices.date_to IS 'Дата окончания действия цены';
COMMENT ON COLUMN prices.price IS 'Цена товара';
COMMENT ON COLUMN prices.document_id IS 'ID документа установки цены';