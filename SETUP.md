# Инструкция по настройке и использованию IIKO Data Sync

## Структура базы данных

На основе вашего примера ответа API создана следующая структура таблиц:

### Таблица `products`
- `id` (UUID) - уникальный идентификатор продукта
- `deleted` (BOOLEAN) - флаг удаления
- `name` (VARCHAR) - название продукта
- `description` (TEXT) - описание
- `num` (VARCHAR) - номер
- `code` (VARCHAR) - код продукта (уникальный)
- `parent_id` (UUID) - ссылка на родительский продукт
- `tax_category_id` (UUID) - налоговая категория
- `category_id` (UUID) - категория продукта
- `accounting_category_id` (UUID) - учетная категория
- `created_at`, `updated_at`, `synced_at` - временные метки

### Таблица `product_modifiers`
- Связь многие-ко-многим между продуктами и модификаторами

### Таблица `categories`
- Хранит все виды категорий (tax, product, accounting)

## Установка и настройка

1. **Создайте базу данных PostgreSQL:**
```bash
createdb iiko_data
```

2. **Примените миграции:**
```bash
psql -U postgres -d iiko_data -f migrations/002_create_products_table.sql
```

3. **Установите зависимости Python:**
```bash
pip install -r requirements.txt
```

4. **Настройте `.env` файл:**
```
IIKO_API_LOGIN=Tanat
IIKO_API_PASSWORD=7c4a8d09ca3762af61e59520943dc26494f8941b

DB_HOST=localhost
DB_PORT=5432
DB_NAME=iiko_data
DB_USER=postgres
DB_PASSWORD=your_password
```

## Использование

### Запуск синхронизации:
```bash
python main.py
```

### Проверка API подключения:
```bash
python test_api.py
```

### Только анализ структуры:
```bash
python main.py --analyze
```

## Структура данных

Пример продукта из API:
```json
{
    "id": "bcfffdde-54d5-4ef5-bf7c-6a7be4c0fc3c",
    "deleted": false,
    "name": "ДАНИШ С НУТЕЛЛОЙ НОВЫЙ 154 гр",
    "description": "",
    "num": "1746",
    "code": "1746",
    "parent": "b5613650-64a9-40b6-a8da-45d4520d575a",
    "modifiers": [],
    "taxCategory": null,
    "category": "66f522a9-03d3-e99e-0195-24ba79064eca",
    "accountingCategory": "8bc08505-c81d-075d-8572-af7b636d049b"
}
```

## Расширение функционала

Проект готов к добавлению новых типов данных. Для этого:
1. Создайте новую миграцию в `migrations/`
2. Добавьте модель в `src/models.py`
3. Расширьте API клиент в `src/api_client.py`
4. Добавьте логику синхронизации в `src/synchronizer.py`

## Мониторинг

Все операции логируются в таблицу `sync_log` и в файлы в директории `logs/`.
