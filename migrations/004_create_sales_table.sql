-- Создание таблицы для хранения чеков (продаж)
CREATE TABLE IF NOT EXISTS sales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_num INTEGER NOT NULL,
    fiscal_cheque_number VARCHAR(50),
    cash_register_name VARCHAR(255),
    cash_register_serial_number VARCHAR(100),
    cash_register_number INTEGER,
    close_time TIMESTAMP WITH TIME ZONE,
    precheque_time TIMESTAMP WITH TIME ZONE,
    deleted_with_writeoff VARCHAR(50),
    department VARCHAR(255),
    department_id UUID,
    dish_amount INTEGER,
    dish_code VARCHAR(50),
    dish_discount_sum INTEGER,
    dish_measure_unit VARCHAR(20),
    dish_name VARCHAR(255),
    dish_return_sum INTEGER,
    dish_sum INTEGER,
    increase_sum INTEGER,
    order_increase_type VARCHAR(100),
    order_items INTEGER,
    order_type VARCHAR(100),
    pay_types VARCHAR(255),
    store_name VARCHAR(255),
    store_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    synced_at TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE SET NULL,
    CONSTRAINT unique_order_fiscal_number UNIQUE(order_num, fiscal_cheque_number)
);

-- Индексы для ускорения запросов
CREATE INDEX IF NOT EXISTS idx_sales_order_num ON sales(order_num);
CREATE INDEX IF NOT EXISTS idx_sales_close_time ON sales(close_time);
CREATE INDEX IF NOT EXISTS idx_sales_dish_code ON sales(dish_code);
CREATE INDEX IF NOT EXISTS idx_sales_department_id ON sales(department_id);
CREATE INDEX IF NOT EXISTS idx_sales_store_id ON sales(store_id);

COMMENT ON TABLE sales IS 'Таблица чеков и продаж';