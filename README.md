# IIKO Data Synchronizer

Проект для синхронизации данных из IIKO API в локальную PostgreSQL базу данных.

## Структура проекта

```
iiko-data-sync/
├── config/
│   └── config.py          # Конфигурация проекта
├── migrations/
│   └── 001_create_tables.sql  # SQL схема БД
├── src/
│   ├── api_client.py      # Клиент для работы с IIKO API
│   ├── models.py          # SQLAlchemy модели
│   ├── synchronizer.py    # Логика синхронизации продуктов
│   ├── store_synchronizer.py # Логика синхронизации складов
│   └── sales_synchronizer.py # Логика синхронизации продаж
├── logs/                  # Логи работы (создается автоматически)
├── main.py               # Основной скрипт запуска
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

# Примените миграции
psql -U postgres -d iiko_data -f migrations/001_create_tables.sql
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
- `sales` - продажи и чеки
- `receipts` - квитанции
- `receipt_items` - позиции квитанций
- `sync_log` - лог синхронизации

## Расширение функциональности

Для добавления новых сущностей:

1. Создайте миграцию в `migrations/`
2. Добавьте модель в `src/models.py`
3. Расширьте `src/api_client.py` новыми методами
4. Добавьте логику синхронизации в `src/synchronizer.py`

## Логирование

Логи сохраняются в директории `logs/` с именем формата `sync_YYYYMMDD_HHMMSS.log`

## Примечания

- Проект готов к расширению для работы с другими сущностями IIKO API
- Поддерживается инкрементальная синхронизация
- Дополнительные поля сохраняются в JSON колонке `additional_info`
