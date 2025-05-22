-- Создание enum для статуса документов списания
CREATE TYPE writeoff_document_status AS ENUM ('NEW', 'PROCESSED', 'CANCELLED');

-- Создание таблицы документов списания
CREATE TABLE IF NOT EXISTS writeoff_documents (
    id UUID PRIMARY KEY,
    date_incoming TIMESTAMP NOT NULL,
    document_number VARCHAR(50) NOT NULL,
    status writeoff_document_status NOT NULL,
    conception_id UUID,
    comment TEXT,
    store_id UUID REFERENCES stores(id),
    account_id UUID REFERENCES accounts(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание таблицы позиций документов списания
CREATE TABLE IF NOT EXISTS writeoff_items (
    id SERIAL PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES writeoff_documents(id) ON DELETE CASCADE,
    num INTEGER NOT NULL,
    product_id UUID NOT NULL REFERENCES products(id),
    product_size_id UUID,
    amount_factor NUMERIC(10,3) NOT NULL DEFAULT 1,
    amount NUMERIC(10,3) NOT NULL,
    measure_unit_id UUID,
    container_id UUID,
    cost NUMERIC(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_writeoff_item_num UNIQUE (document_id, num)
);

-- Создание индексов для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_writeoff_documents_date_incoming ON writeoff_documents(date_incoming);
CREATE INDEX IF NOT EXISTS idx_writeoff_documents_status ON writeoff_documents(status);
CREATE INDEX IF NOT EXISTS idx_writeoff_documents_store_id ON writeoff_documents(store_id);
CREATE INDEX IF NOT EXISTS idx_writeoff_documents_account_id ON writeoff_documents(account_id);
CREATE INDEX IF NOT EXISTS idx_writeoff_documents_document_number ON writeoff_documents(document_number);

CREATE INDEX IF NOT EXISTS idx_writeoff_items_document_id ON writeoff_items(document_id);
CREATE INDEX IF NOT EXISTS idx_writeoff_items_product_id ON writeoff_items(product_id);

-- Комментарии к таблицам и колонкам
COMMENT ON TABLE writeoff_documents IS 'Документы списания из IIKO API';
COMMENT ON COLUMN writeoff_documents.id IS 'Уникальный идентификатор документа';
COMMENT ON COLUMN writeoff_documents.date_incoming IS 'Дата поступления документа';
COMMENT ON COLUMN writeoff_documents.document_number IS 'Номер документа';
COMMENT ON COLUMN writeoff_documents.status IS 'Статус документа (NEW, PROCESSED, CANCELLED)';
COMMENT ON COLUMN writeoff_documents.conception_id IS 'ID концепции';
COMMENT ON COLUMN writeoff_documents.comment IS 'Комментарий к документу';
COMMENT ON COLUMN writeoff_documents.store_id IS 'ID склада (ссылка на stores)';
COMMENT ON COLUMN writeoff_documents.account_id IS 'ID счета (ссылка на accounts)';

COMMENT ON TABLE writeoff_items IS 'Позиции документов списания';
COMMENT ON COLUMN writeoff_items.id IS 'Автоинкрементный ID позиции';
COMMENT ON COLUMN writeoff_items.document_id IS 'ID документа (ссылка на writeoff_documents)';
COMMENT ON COLUMN writeoff_items.num IS 'Номер позиции в документе';
COMMENT ON COLUMN writeoff_items.product_id IS 'ID товара (ссылка на products)';
COMMENT ON COLUMN writeoff_items.product_size_id IS 'ID размера товара';
COMMENT ON COLUMN writeoff_items.amount_factor IS 'Коэффициент количества';
COMMENT ON COLUMN writeoff_items.amount IS 'Количество';
COMMENT ON COLUMN writeoff_items.measure_unit_id IS 'ID единицы измерения';
COMMENT ON COLUMN writeoff_items.container_id IS 'ID контейнера';
COMMENT ON COLUMN writeoff_items.cost IS 'Стоимость позиции';