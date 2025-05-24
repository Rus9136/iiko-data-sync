# Инструкция по настройке и использованию IIKO Data Sync

**Обновлено: декабрь 2025**

## Структура базы данных

Полная структура базы данных для всех сущностей IIKO:

### Основные таблицы

#### `products` - Номенклатура
- `id` (UUID) - уникальный идентификатор
- `code` (VARCHAR) - код продукта
- `name` (VARCHAR) - название
- `deleted` (BOOLEAN) - флаг удаления
- Категории: `tax_category_id`, `category_id`, `accounting_category_id`

#### `stores` - Склады
- `id` (UUID) - идентификатор
- `code`, `name` - код и название
- `type` (ENUM) - тип: STORE, PRODUCTION, OTHER
- `parent_id` - иерархия

#### `departments` - Подразделения
- `id` (UUID) - идентификатор
- `code`, `name` - код и название
- `taxpayer_id_number` - ИНН
- `parent_id` - иерархия

#### `suppliers` - Поставщики
- `id` (UUID) - идентификатор
- `code`, `name` - код и название
- `taxpayer_id_number`, `snils` - ИНН и СНИЛС
- Роли: `is_supplier`, `is_employee`, `is_client`

#### `accounts` - Счета учета
- `id` (UUID) - идентификатор
- `code`, `name` - код и название
- `type` - тип счета
- `account_parent_id` - иерархия

### Документы

#### `sales` - Продажи
- Составной ключ: `order_num`, `fiscal_cheque_number`, `dish_code`, `cash_register_number`
- Данные чека: время, сумма, скидки
- `storned` - флаг отмены

#### `writeoff_documents` / `writeoff_items` - Списания
- Документы со статусами: NEW, PROCESSED
- Позиции с точностью Numeric(10,3)

#### `incoming_invoices` / `incoming_invoice_items` - Приходные накладные
- Связь с поставщиками и складами
- НДС: `vat_percent`, `vat_sum`
- Высокая точность: Numeric(15,9)

#### `prices` - Цены
- Цены по подразделениям
- Периоды действия: `date_from`, `date_to`
- Типы цен: BASE и другие

## Установка и настройка

1. **Создайте базу данных PostgreSQL:**
```bash
createdb iiko_data
```

2. **Примените все миграции по порядку:**
```bash
# Применить все миграции автоматически
for f in migrations/*.sql; do
    echo "Применяю: $f"
    psql -U postgres -d iiko_data -f "$f"
done

# Или вручную по очереди:
psql -U postgres -d iiko_data -f migrations/001_create_tables.sql
psql -U postgres -d iiko_data -f migrations/002_fixed_create_products_table.sql
# ... и так далее до 012_create_incoming_invoices_table.sql
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

### Веб-интерфейс
```bash
# Запуск с автооткрытием браузера
python run_web.py
```
Откроется на http://127.0.0.1:8082

### Консольная синхронизация
```bash
# Все сущности
python main.py

# Конкретные сущности
python main.py --entity products
python main.py --entity stores
python main.py --entity departments
python main.py --entity suppliers
python main.py --entity prices
python main.py --entity accounts

# С датами
python main.py --entity sales --date-from "2025-05-19" --date-to "2025-05-19"
python main.py --entity writeoffs --date-from "2025-05-19" --date-to "2025-05-19"
python main.py --entity incoming_invoices --date-from "2025-05-19" --date-to "2025-05-19"
```

### Тестирование
```bash
# Проверка API
python test_api.py

# Проверка базы данных
python test_db.py

# Анализ структуры API
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

Для добавления новых сущностей:
1. Создайте новую миграцию в `migrations/`
2. Добавьте модель в `src/models.py`
3. Расширьте API клиент в `src/api_client.py`
4. Создайте новый синхронизатор в `src/`
5. Добавьте маршруты в `web/app.py`
6. Создайте шаблоны в `web/templates/`

## Основные функции веб-интерфейса

### Справочники
- Номенклатура с поиском и фильтрами
- Склады с иерархией
- Поставщики с фильтрацией по ролям
- Подразделения с ИНН
- Счета учета

### Документы
- Продажи с группировкой по чекам
- Списания с фильтрацией по статусам
- Приходные накладные с CRUD

### Сервис
- Дашборд со статистикой
- Универсальная страница синхронизации
- Оперативная сводка с OLAP
- Отчеты с экспортом в Excel
- Управление ценами
- История синхронизаций

## Мониторинг и логирование

1. **База данных**: таблица `sync_log` с детальной статистикой
2. **Файлы**: логи в `logs/sync_YYYYMMDD_HHMMSS.log`
3. **Веб-интерфейс**: страница `/logs` с историей

## Отличительные особенности

- **AJAX навигация**: переходы без перезагрузки страниц
- **Боковая панель**: удобная навигация по разделам
- **Excel экспорт**: отчеты с pandas и xlsxwriter
- **Высокая точность**: Numeric(15,9) для финансовых данных
- **macOS совместимость**: использование 127.0.0.1:8082
