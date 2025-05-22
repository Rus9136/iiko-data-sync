# IIKO Data Synchronizer

Проект для синхронизации данных из IIKO API в локальную PostgreSQL базу данных.

## Структура проекта

```
iiko-data-sync/
├── config/
│   └── config.py          # Конфигурация проекта
├── migrations/            # SQL миграции БД
│   ├── 002_fixed_create_products_table.sql
│   ├── 003_fix_unique_code_constraint.sql
│   ├── 004_add_storned_field.sql
│   └── 005_update_sales_unique_constraint.sql
├── src/
│   ├── api_client.py      # Клиент для работы с IIKO API
│   ├── models.py          # SQLAlchemy модели
│   ├── synchronizer.py    # Логика синхронизации продуктов
│   ├── store_synchronizer.py # Логика синхронизации складов
│   └── sales_synchronizer.py # Логика синхронизации продаж
├── web/                   # Веб-интерфейс
│   ├── app.py            # Flask приложение
│   ├── static/           # CSS файлы
│   └── templates/        # HTML шаблоны
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

### Синхронизация продаж за определенный период
```bash
python main.py --entity sales --date-from "2025-05-19 00:00:00" --date-to "2025-05-19 23:59:59"
```

### Синхронизация списаний
```bash
python main.py --entity writeoffs --date-from "2025-05-19 00:00:00" --date-to "2025-05-19 23:59:59"
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
- `sales` - продажи и чеки (с группировкой по чекам в веб-интерфейсе)
- `writeoff_documents` - документы списания
- `writeoff_items` - позиции списания (с точностью до 3 знаков после запятой)
- `accounts` - счета для фильтрации списаний
- `sync_log` - лог синхронизации

## Веб-интерфейс

Доступные страницы:
- `/` - Главная страница со статистикой
- `/products` - Список продуктов с пагинацией и поиском
- `/sales` - Список продаж (группировка по чекам)
- `/writeoffs` - Список документов списания с фильтрацией
- `/logs` - История синхронизаций

### Последние улучшения (май 2025)
- **Интерфейс продаж**: полностью переработан для отображения чеков, а не отдельных позиций
- **Детали чека**: структурированный вид с информацией о чеке и таблицей позиций
- **Списания**: отображение количества с точностью до 3 знаков после запятой (например, 10.001)

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
