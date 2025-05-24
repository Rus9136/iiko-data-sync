# IIKO Data Sync Project

## Описание проекта
Комплексная система синхронизации данных из IIKO API в локальную PostgreSQL базу данных с полнофункциональным веб-интерфейсом для управления, отчетности и аналитики.

## Структура проекта
```
iiko-data-sync/
├── config/
│   └── config.py          # Конфигурация проекта (API URL, DB настройки)
├── migrations/
│   ├── 001_create_tables.sql           # Базовые таблицы
│   ├── 002_fixed_create_products_table.sql  # Таблица продуктов
│   ├── 006_create_accounts_table.sql   # Таблица счетов
│   ├── 008_create_writeoff_tables.sql  # Таблицы списаний
│   ├── 009_create_departments_table.sql # Таблица подразделений
│   ├── 010_create_prices_table.sql     # Таблица цен
│   ├── 011_create_suppliers_table.sql  # Таблица поставщиков
│   └── 012_create_incoming_invoices_table.sql # Приходные накладные
├── src/
│   ├── api_client.py      # Клиент для работы с IIKO API
│   ├── models.py          # SQLAlchemy модели (все сущности)
│   ├── synchronizer.py    # Синхронизация продуктов
│   ├── store_synchronizer.py    # Синхронизация складов
│   ├── sales_synchronizer.py    # Синхронизация продаж
│   ├── department_synchronizer.py # Синхронизация подразделений
│   ├── price_synchronizer.py     # Синхронизация цен
│   ├── supplier_synchronizer.py  # Синхронизация поставщиков
│   └── incoming_invoice_synchronizer.py # Синхронизация приходных накладных
├── web/
│   ├── app.py            # Flask веб-приложение с AJAX
│   ├── report_controller.py # Контроллер отчетов
│   ├── static/           # CSS и JS файлы
│   └── templates/        # HTML шаблоны с Bootstrap
├── .env                  # Переменные окружения (учетные данные)
├── main.py              # CLI скрипт для синхронизации
├── run_web.py           # Запуск веб-интерфейса
└── requirements.txt     # Python зависимости
```

## API Endpoints

### IIKO API
- **Авторизация**: `GET /resto/api/auth?login={login}&pass={password}`
  - Возвращает токен авторизации
- **Продукты**: `GET /resto/api/v2/entities/products/list?includeDeleted=false`
  - Headers: `Cookie: key={token}`
  - Возвращает JSON массив продуктов с пагинацией
- **Подразделения**: `GET /resto/api/corporation/departments`
  - Headers: `Cookie: key={token}`
  - Возвращает JSON массив подразделений
- **Склады**: `GET /resto/api/corporation/stores`
  - Headers: `Cookie: key={token}`
  - Возвращает JSON массив складов
- **Поставщики**: `GET /resto/api/suppliers`
  - Headers: `Cookie: key={token}`
  - Возвращает JSON массив поставщиков
- **Продажи (OLAP)**: `POST /resto/api/v2/reports/olap`
  - Headers: `Cookie: key={token}`
  - Body: отчетные параметры с датами
- **Приходные накладные**: `GET /resto/api/documents/import/incomingInvoice`
  - Headers: `Cookie: key={token}`
  - Параметры: dateFrom, dateTo
- **Цены**: `GET /resto/api/v2/documents/priceList`
  - Headers: `Cookie: key={token}`
  - Возвращает прайс-листы

### Веб-интерфейс

#### Дашборд и навигация
- `GET /` - Дашборд со статистикой и виджетами **[НОВЫЙ ДЕКАБРЬ 2025]**

#### Справочники
- `GET /products` - Список продуктов с AJAX пагинацией
- `GET /product/<id>` - Детали продукта (исправлен full-screen режим)
- `GET /stores` - Список складов с иерархией
- `GET /store/<id>` - Детали склада
- `GET /suppliers/list` - Список поставщиков **[НОВЫЙ]**
- `GET /departments` - Список подразделений **[НОВЫЙ]**
- `GET /department/<id>` - Детали подразделения **[НОВЫЙ]**
- `GET /accounts` - Список счетов
- `GET /account/<id>` - Детали счета

#### Документы
- `GET /sales` - Список продаж (группировка по чекам) **[ПЕРЕРАБОТАН МАЙ 2025]**
- `GET /sale/<sale_id>` - Детали чека с позициями
- `GET /writeoffs` - Список документов списания
- `GET /writeoff/<id>` - Детали документа списания
- `GET /incoming_invoices` - Приходные накладные **[НОВЫЙ]**
- `GET /incoming_invoice/<id>` - Детали приходной накладной **[НОВЫЙ]**

#### Сервисы
- `GET /upload` - Универсальная страница синхронизации **[ОБНОВЛЕН]**
- `POST /sync` - API для запуска синхронизации
- `GET /logs` - История синхронизаций
- `GET /operational-summary` - Оперативная сводка **[НОВЫЙ]**
- `GET /sales/report` - Отчеты по продажам с Excel экспортом **[НОВЫЙ]**
- `GET /prices` - Управление ценами **[НОВЫЙ]**

#### API эндпоинты
- `GET /api/departments` - JSON список подразделений
- `POST /api/operational-reports` - Генерация оперативных отчетов

## База данных (PostgreSQL)

### Таблицы
- **products** - основная таблица продуктов
  - id (UUID)
  - name, code, num, description
  - deleted, category_id, parent_id
  - created_at, updated_at, synced_at
- **categories** - категории продуктов (налоговые, продуктовые, бухгалтерские)
- **product_modifiers** - связь продуктов и модификаторов
- **stores** - склады и подразделения с иерархией
- **departments** - подразделения организации
- **sales** - продажи и чеки (составной ключ: order_num, fiscal_cheque_number, dish_code, cash_register_number)
- **writeoff_documents** - документы списания со статусами NEW/PROCESSED
- **writeoff_items** - позиции списания (amount с точностью до 3 знаков)
- **accounts** - счета учета с иерархией
- **suppliers** - поставщики и контрагенты
- **prices** - цены на продукты по подразделениям с датами действия
- **incoming_invoices** - приходные накладные
- **incoming_invoice_items** - позиции приходных накладных с НДС
- **sync_log** - логи синхронизации всех сущностей

## Быстрый старт

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 2. Настройка базы данных
```bash
createdb iiko_data
# Применить все миграции по порядку
for f in migrations/*.sql; do psql -U postgres -d iiko_data -f "$f"; done
```

### 3. Настройка переменных окружения
Отредактируйте `.env` файл:
```
IIKO_API_LOGIN=Tanat
IIKO_API_PASSWORD=your_password_here
DB_HOST=localhost
DB_PORT=5432
DB_NAME=iiko_data
DB_USER=postgres
DB_PASSWORD=your_db_password
```

### 4. Запуск

#### Веб-интерфейс:
```bash
python run_web.py
# Откройте http://localhost:8080
```

#### Консольная синхронизация:
```bash
python main.py               # Синхронизировать все
python main.py --analyze     # Только анализ структуры
python main.py --entity products  # Только продукты
python main.py --entity sales --date-from "2025-05-19" --date-to "2025-05-19"  # Продажи за день
python main.py --entity suppliers  # Поставщики
python main.py --entity departments  # Подразделения
python main.py --entity prices  # Цены
python main.py --entity incoming_invoices --date-from "2025-05-19"  # Приходные накладные
```

## Основные компоненты

### api_client.py
- `IikoApiClient` - класс для работы с API
  - `authenticate()` - получение токена с автообновлением
  - `get_products()` - получение продуктов с пагинацией
  - `get_departments()` - получение подразделений
  - `get_stores()` - получение складов
  - `get_suppliers()` - получение поставщиков
  - `get_sales_report()` - OLAP отчет по продажам
  - `get_writeoff_documents()` - документы списания
  - `get_incoming_invoices()` - приходные накладные
  - `get_price_lists()` - прайс-листы

### models.py
- SQLAlchemy модели:
  - `Product` - продукты с UUID идентификаторами
  - `Category` - категории (налоговые, продуктовые, бухгалтерские)
  - `Store` - склады с типами (STORE, PRODUCTION, OTHER)
  - `Department` - подразделения с иерархией
  - `Sale` - продажи с составными ключами
  - `WriteoffDocument`, `WriteoffItem` - документы списания
  - `Account` - счета учета
  - `Supplier` - поставщики с множественными ролями
  - `Price` - цены с датами действия
  - `IncomingInvoice`, `IncomingInvoiceItem` - приходные накладные
  - `SyncLog` - логи синхронизации

### Синхронизаторы
- `synchronizer.py` - `DataSynchronizer` для продуктов и счетов
- `store_synchronizer.py` - `StoreSynchronizer` для складов
- `sales_synchronizer.py` - `SalesSynchronizer` для продаж с OLAP
- `department_synchronizer.py` - `DepartmentSynchronizer` для подразделений
- `price_synchronizer.py` - `PriceSynchronizer` для цен
- `supplier_synchronizer.py` - `SupplierSynchronizer` для поставщиков
- `incoming_invoice_synchronizer.py` - `IncomingInvoiceSynchronizer` для приходных

### web/app.py
- Flask приложение с AJAX поддержкой
- Боковая панель навигации с разделами:
  - Справочники (продукты, склады, поставщики, подразделения, счета)
  - Документы (продажи, списания, приходные накладные)
  - Сервис (загрузка, логи, оперативная сводка)
- Обработка загрузки файлов
- API эндпоинты для AJAX
- Экспорт отчетов в Excel через pandas

### web/report_controller.py
- Контроллер для генерации отчетов
- Перенаправление на оперативную сводку

## Формат данных

### Продукт (JSON)
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

### Подразделение (XML)
```xml
<employee>
    <id>c56d4fb2-5a59-4683-8080-468de0bdebbf</id>
    <code>195</code>
    <name>11 мкр</name>
    <deleted>false</deleted>
    <supplier>true</supplier>
    <employee>false</employee>
    <client>false</client>
</employee>
```

## Известные проблемы

1. Порт 5000 может быть занят на macOS (AirPlay Receiver)
   - Решение: используется порт 8080

2. CSRF защита отключена для упрощения
   - TODO: добавить правильную CSRF защиту

3. Нет автоматической миграции БД
   - TODO: интегрировать Alembic

## Расширение функционала

### Добавление новых сущностей
1. Создать миграцию в `migrations/`
2. Добавить модель в `src/models.py`
3. Расширить `api_client.py` новыми методами
4. Добавить логику в `synchronizer.py`
5. Создать веб-страницы в `web/templates/`

### ВЫПОЛНЕНО (МАЙ 2025)
- [x] Синхронизация продаж с OLAP API
- [x] Синхронизация списаний с фильтрацией по статусам
- [x] Улучшение UI интерфейса продаж (группировка по чекам)
- [x] Детальная страница чека с структурированной информацией
- [x] Точность до 3 знаков после запятой для списаний
- [x] Решение проблем с PostgreSQL агрегацией через raw SQL

### ВЫПОЛНЕНО (ДЕКАБРЬ 2025)
- [x] Дашборд со статистикой и виджетами
- [x] Синхронизация поставщиков
- [x] Синхронизация подразделений с иерархией
- [x] Синхронизация приходных накладных с позициями
- [x] Управление ценами по подразделениям
- [x] Экспорт отчетов в Excel с pandas
- [x] AJAX навигация без перезагрузки страниц
- [x] Боковая панель с группировкой по разделам
- [x] Исправление проблем с full-screen модальными окнами
- [x] Улучшенная страница загрузки с множественной синхронизацией

### TODO
- [ ] Добавить автоматическую синхронизацию по расписанию
- [ ] Добавить авторизацию пользователей
- [ ] Оптимизация производительности SQL запросов
- [ ] Добавить кеширование для часто запрашиваемых данных
- [ ] Реализовать WebSocket для real-time обновлений
- [ ] Добавить экспорт/импорт конфигурации

## Полезные команды

```bash
# Проверка структуры API
python check_structure.py

# Анализ данных API
python src/analyze_api.py

# Тест подключения
python test_api.py

# Просмотр логов
tail -f logs/sync_*.log
```

## Контакты и поддержка

Проект разработан для синхронизации данных IIKO.
При возникновении проблем проверьте:
1. Правильность учетных данных в .env
2. Доступность IIKO API
3. Наличие и доступность базы данных PostgreSQL
