-- Создание таблицы accounts (Счета)
CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY,
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    code VARCHAR(50) UNIQUE,
    name VARCHAR(255) NOT NULL,
    account_parent_id UUID REFERENCES accounts(id),
    parent_corporate_id UUID,
    type VARCHAR(100),
    system BOOLEAN NOT NULL DEFAULT FALSE,
    custom_transactions_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание индексов для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_accounts_code ON accounts(code);
CREATE INDEX IF NOT EXISTS idx_accounts_parent ON accounts(account_parent_id);
CREATE INDEX IF NOT EXISTS idx_accounts_deleted ON accounts(deleted);
CREATE INDEX IF NOT EXISTS idx_accounts_type ON accounts(type);

-- Комментарии к таблице и колонкам
COMMENT ON TABLE accounts IS 'Таблица счетов из IIKO API';
COMMENT ON COLUMN accounts.id IS 'Уникальный идентификатор счета';
COMMENT ON COLUMN accounts.deleted IS 'Флаг удаления записи';
COMMENT ON COLUMN accounts.code IS 'Код счета (уникальный)';
COMMENT ON COLUMN accounts.name IS 'Название счета';
COMMENT ON COLUMN accounts.account_parent_id IS 'ID родительского счета';
COMMENT ON COLUMN accounts.parent_corporate_id IS 'ID корпоративного родителя';
COMMENT ON COLUMN accounts.type IS 'Тип счета';
COMMENT ON COLUMN accounts.system IS 'Системный счет';
COMMENT ON COLUMN accounts.custom_transactions_allowed IS 'Разрешены пользовательские транзакции';
COMMENT ON COLUMN accounts.created_at IS 'Дата создания записи';
COMMENT ON COLUMN accounts.updated_at IS 'Дата последнего обновления';
COMMENT ON COLUMN accounts.synced_at IS 'Дата последней синхронизации с API';