# IIKO Data Synchronizer

Комплексная система для синхронизации данных из IIKO API в локальную PostgreSQL базу данных с веб-интерфейсом для управления, отчетов и аналитики.

## Структура проекта

```
iiko-data-sync/
├── config/
│   └── config.py          # Конфигурация проекта
├── migrations/            # SQL миграции БД
│   ├── 001_create_tables.sql
│   ├── 002_fixed_create_products_table.sql
│   ├── 003_fix_unique_code_constraint.sql
│   ├── 004_add_storned_field.sql
│   ├── 005_update_sales_unique_constraint.sql
│   ├── 006_create_accounts_table.sql
│   ├── 007_fix_accounts_code_constraint.sql
│   ├── 008_create_writeoff_tables.sql
│   ├── 009_create_departments_table.sql
│   ├── 010_create_prices_table.sql
│   ├── 011_create_suppliers_table.sql
│   └── 012_create_incoming_invoices_table.sql
├── src/
│   ├── api_client.py      # Клиент для работы с IIKO API
│   ├── models.py          # SQLAlchemy модели
│   ├── synchronizer.py    # Логика синхронизации продуктов
│   ├── store_synchronizer.py # Логика синхронизации складов
│   ├── sales_synchronizer.py # Логика синхронизации продаж
│   ├── department_synchronizer.py # Логика синхронизации подразделений
│   ├── price_synchronizer.py # Логика синхронизации цен
│   ├── supplier_synchronizer.py # Логика синхронизации поставщиков
│   └── incoming_invoice_synchronizer.py # Логика синхронизации приходных накладных
├── web/                   # Веб-интерфейс
│   ├── app.py            # Flask приложение с AJAX
│   ├── report_controller.py # Контроллер отчетов
│   ├── static/           # CSS файлы
│   └── templates/        # HTML шаблоны с Bootstrap
├── logs/                  # Логи работы (создается автоматически)
├── main.py               # Основной скрипт запуска
├── run_web.py            # Запуск веб-интерфейса
├── requirements.txt      # Зависимости проекта
├── .env                  # Переменные окружения
└── README.md            # Этот файл
```

## Установка

1. Клонируйте репозиторий или скопируйте файлы проекта

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Настройте базу данных PostgreSQL:
```bash
# Создайте базу данных
createdb iiko_data

# Примените миграции по порядку
psql -U postgres -d iiko_data -f migrations/001_create_tables.sql
psql -U postgres -d iiko_data -f migrations/002_fixed_create_products_table.sql
psql -U postgres -d iiko_data -f migrations/003_fix_unique_code_constraint.sql
psql -U postgres -d iiko_data -f migrations/004_add_storned_field.sql
psql -U postgres -d iiko_data -f migrations/005_update_sales_unique_constraint.sql
psql -U postgres -d iiko_data -f migrations/006_create_accounts_table.sql
psql -U postgres -d iiko_data -f migrations/007_fix_accounts_code_constraint.sql
psql -U postgres -d iiko_data -f migrations/008_create_writeoff_tables.sql
psql -U postgres -d iiko_data -f migrations/009_create_departments_table.sql
psql -U postgres -d iiko_data -f migrations/010_create_prices_table.sql
psql -U postgres -d iiko_data -f migrations/011_create_suppliers_table.sql
psql -U postgres -d iiko_data -f migrations/012_create_incoming_invoices_table.sql
```

4. Настройте переменные окружения в файле `.env`:
```
# IIKO API Credentials
IIKO_API_LOGIN=Tanat
IIKO_API_PASSWORD=your_password_here

# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=iiko_data
DB_USER=postgres
DB_PASSWORD=your_db_password
```

## Использование

### Синхронизация всех данных
```bash
python main.py
```

### Синхронизация только продуктов
```bash
python main.py --entity products
```

### Синхронизация только складов
```bash
python main.py --entity stores
```

### Синхронизация продаж
```bash
python main.py --entity sales
```

### Синхронизация продаж за определенный период
```bash
python main.py --entity sales --date-from "2025-05-19 00:00:00" --date-to "2025-05-19 23:59:59"
```

### Синхронизация списаний
```bash
python main.py --entity writeoffs --date-from "2025-05-19 00:00:00" --date-to "2025-05-19 23:59:59"
```

### Синхронизация поставщиков
```bash
python main.py --entity suppliers
```

### Синхронизация подразделений
```bash
python main.py --entity departments
```

### Синхронизация цен
```bash
python main.py --entity prices
```

### Синхронизация приходных накладных
```bash
python main.py --entity incoming_invoices --date-from "2025-05-19 00:00:00" --date-to "2025-05-19 23:59:59"
```

### Запуск веб-интерфейса
```bash
python run_web.py
```

### Тестирование API продаж
```bash
python test_sales.py --api
```

### Тестирование синхронизации продаж
```bash
python test_sales.py --sync
```

### Анализ структуры данных API
```bash
python main.py --analyze
```

### Тестирование подключения к API
```bash
python test_api.py
```

## Таблицы базы данных

- `products` - основная таблица продуктов
- `product_modifiers` - связь продуктов и модификаторов
- `categories` - категории продуктов (налоговые, продуктовые, бухгалтерские)
- `stores` - склады и подразделения
- `departments` - подразделения организации
- `sales` - продажи и чеки (с группировкой по чекам в веб-интерфейсе)
- `writeoff_documents` - документы списания
- `writeoff_items` - позиции списания (с точностью до 3 знаков после запятой)
- `accounts` - счета для фильтрации списаний
- `suppliers` - поставщики и контрагенты
- `prices` - цены на продукты по подразделениям
- `incoming_invoices` - приходные накладные
- `incoming_invoice_items` - позиции приходных накладных
- `sync_log` - лог синхронизации

## Веб-интерфейс

Веб-интерфейс с боковой панелью навигации, организованной по разделам:

### Справочники
- `/products` - Список продуктов с пагинацией и поиском
- `/stores` - Список складов с иерархией
- `/suppliers/list` - Список поставщиков
- `/departments` - Подразделения организации
- `/accounts` - Счета учета

### Документы
- `/sales` - Продажи (группировка по чекам)
- `/writeoffs` - Документы списания
- `/incoming_invoices` - Приходные накладные

### Сервис
- `/` - Дашборд со статистикой
- `/upload` - Универсальная страница синхронизации
- `/logs` - История синхронизаций
- `/operational-summary` - Оперативная сводка
- `/sales/report` - Отчеты по продажам с экспортом в Excel

### Последние улучшения (декабрь 2025)
- **Дашборд**: новая главная страница со статистикой и виджетами
- **Приходные накладные**: полный CRUD для работы с приходными документами
- **Отчеты по продажам**: экспорт в Excel с использованием pandas
- **Боковая панель**: улучшенная навигация с группировкой по разделам
- **AJAX навигация**: бесшовные переходы между страницами
- **Синхронизация поставщиков**: новый тип данных для контрагентов
- **Цены на продукты**: управление ценами по подразделениям
- **Исправления интерфейса**: решены проблемы с полноэкранными модальными окнами

### Предыдущие улучшения (май 2025)
- **Интерфейс продаж**: полностью переработан для отображения чеков
- **Детали чека**: структурированный вид с шапкой и таблицей
- **Списания**: отображение количества с 3 знаками после запятой

## Расширение функциональности

Для добавления новых сущностей:

1. Создайте миграцию в `migrations/`
2. Добавьте модель в `src/models.py`
3. Расширьте `src/api_client.py` новыми методами
4. Создайте новый файл синхронизатора в `src/`
5. Добавьте маршруты в `web/app.py`
6. Создайте шаблоны в `web/templates/`

## Зависимости

- Flask 3.0.0 - веб-фреймворк
- SQLAlchemy 2.0.23 - ORM
- psycopg2-binary 2.9.9 - драйвер PostgreSQL
- pandas 2.1.1 - обработка данных для отчетов
- xlsxwriter 3.1.9 - экспорт в Excel
- flask-cors 4.0.0 - поддержка CORS
- python-dotenv 1.0.0 - переменные окружения
- requests 2.31.0 - HTTP-запросы

## Логирование

Логи сохраняются в директории `logs/` с именем формата `sync_YYYYMMDD_HHMMSS.log`

## Примечания

- Проект готов к расширению для работы с другими сущностями IIKO API
- Поддерживается инкрементальная синхронизация
- Дополнительные поля сохраняются в JSON колонке `additional_info`
