-- Создание таблицы приходных накладных
CREATE TABLE IF NOT EXISTS incoming_invoices (
    id UUID PRIMARY KEY,
    transport_invoice_number VARCHAR(100),
    incoming_document_number VARCHAR(100),
    incoming_date DATE,
    use_default_document_time BOOLEAN DEFAULT FALSE,
    due_date DATE,
    supplier_id UUID REFERENCES suppliers(id),
    default_store_id UUID REFERENCES stores(id),
    invoice VARCHAR(255),
    date_incoming TIMESTAMP,
    document_number VARCHAR(100) NOT NULL,
    comment TEXT,
    conception UUID,
    conception_code VARCHAR(50),
    status VARCHAR(50),
    distribution_algorithm VARCHAR(100),
    -- Временные метки
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для приходных накладных
CREATE INDEX idx_incoming_invoices_supplier_id ON incoming_invoices(supplier_id);
CREATE INDEX idx_incoming_invoices_store_id ON incoming_invoices(default_store_id);
CREATE INDEX idx_incoming_invoices_date_incoming ON incoming_invoices(date_incoming);
CREATE INDEX idx_incoming_invoices_document_number ON incoming_invoices(document_number);
CREATE INDEX idx_incoming_invoices_status ON incoming_invoices(status);

-- Создание таблицы позиций приходных накладных
CREATE TABLE IF NOT EXISTS incoming_invoice_items (
    id SERIAL PRIMARY KEY,
    invoice_id UUID REFERENCES incoming_invoices(id) ON DELETE CASCADE,
    is_additional_expense BOOLEAN DEFAULT FALSE,
    actual_amount NUMERIC(15, 9),
    store_id UUID REFERENCES stores(id),
    code VARCHAR(50),
    price NUMERIC(15, 9),
    price_without_vat NUMERIC(15, 9),
    sum NUMERIC(15, 9),
    vat_percent NUMERIC(15, 9),
    vat_sum NUMERIC(15, 9),
    discount_sum NUMERIC(15, 9),
    amount_unit UUID,
    num INTEGER,
    product_id UUID REFERENCES products(id),
    product_article VARCHAR(50),
    amount NUMERIC(15, 9),
    supplier_id UUID REFERENCES suppliers(id), -- Дублируем для удобства фильтрации
    -- Временные метки
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для позиций приходных накладных
CREATE INDEX idx_incoming_invoice_items_invoice_id ON incoming_invoice_items(invoice_id);
CREATE INDEX idx_incoming_invoice_items_product_id ON incoming_invoice_items(product_id);
CREATE INDEX idx_incoming_invoice_items_store_id ON incoming_invoice_items(store_id);
CREATE INDEX idx_incoming_invoice_items_supplier_id ON incoming_invoice_items(supplier_id);
CREATE INDEX idx_incoming_invoice_items_code ON incoming_invoice_items(code);

-- Комментарии к таблицам
COMMENT ON TABLE incoming_invoices IS 'Приходные накладные из IIKO';
COMMENT ON TABLE incoming_invoice_items IS 'Позиции приходных накладных';

-- Комментарии к полям таблицы incoming_invoices
COMMENT ON COLUMN incoming_invoices.id IS 'Уникальный идентификатор документа';
COMMENT ON COLUMN incoming_invoices.transport_invoice_number IS 'Номер транспортной накладной';
COMMENT ON COLUMN incoming_invoices.incoming_document_number IS 'Входящий номер документа';
COMMENT ON COLUMN incoming_invoices.incoming_date IS 'Дата прихода';
COMMENT ON COLUMN incoming_invoices.supplier_id IS 'Идентификатор поставщика';
COMMENT ON COLUMN incoming_invoices.default_store_id IS 'Склад по умолчанию';
COMMENT ON COLUMN incoming_invoices.date_incoming IS 'Дата и время поступления';
COMMENT ON COLUMN incoming_invoices.document_number IS 'Номер документа';
COMMENT ON COLUMN incoming_invoices.status IS 'Статус документа';
COMMENT ON COLUMN incoming_invoices.distribution_algorithm IS 'Алгоритм распределения';

-- Комментарии к полям таблицы incoming_invoice_items
COMMENT ON COLUMN incoming_invoice_items.invoice_id IS 'Ссылка на документ';
COMMENT ON COLUMN incoming_invoice_items.is_additional_expense IS 'Является дополнительным расходом';
COMMENT ON COLUMN incoming_invoice_items.actual_amount IS 'Фактическое количество';
COMMENT ON COLUMN incoming_invoice_items.price IS 'Цена с НДС';
COMMENT ON COLUMN incoming_invoice_items.price_without_vat IS 'Цена без НДС';
COMMENT ON COLUMN incoming_invoice_items.sum IS 'Сумма';
COMMENT ON COLUMN incoming_invoice_items.vat_percent IS 'Процент НДС';
COMMENT ON COLUMN incoming_invoice_items.vat_sum IS 'Сумма НДС';
COMMENT ON COLUMN incoming_invoice_items.product_id IS 'Ссылка на продукт';
COMMENT ON COLUMN incoming_invoice_items.amount IS 'Количество';
COMMENT ON COLUMN incoming_invoice_items.supplier_id IS 'Идентификатор поставщика (дублируется для удобства)';