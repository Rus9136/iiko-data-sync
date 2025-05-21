# IIKO Data Sync Project

## Описание проекта
Система синхронизации данных из IIKO API в локальную PostgreSQL базу данных с веб-интерфейсом для управления.

## Структура проекта
```
iiko-data-sync/
├── config/
│   └── config.py          # Конфигурация проекта (API URL, DB настройки)
├── migrations/
│   └── 002_create_products_table.sql  # SQL миграции для PostgreSQL
├── src/
│   ├── api_client.py      # Клиент для работы с IIKO API
│   ├── models.py          # SQLAlchemy модели (Product, Category, SyncLog)
│   └── synchronizer.py    # Логика синхронизации данных
├── web/
│   ├── app.py            # Flask веб-приложение
│   ├── static/           # CSS и JS файлы
│   └── templates/        # HTML шаблоны
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
  - Возвращает JSON массив продуктов
- **Подразделения**: `GET /resto/api/corporation/departments?key={token}&revisionFrom=-1`
  - Возвращает XML со списком подразделений

### Веб-интерфейс
- `GET /` - Главная страница (статистика)
- `GET /products` - Список продуктов с пагинацией
- `GET /product/<id>` - Детали продукта
- `POST /sync` - Запуск синхронизации
- `GET /upload` - Страница загрузки файлов
- `POST /upload` - Загрузка JSON файла
- `GET /logs` - История синхронизаций

## База данных (PostgreSQL)

### Таблицы
- **products** - основная таблица продуктов
  - id (UUID)
  - name, code, num, description
  - deleted, category_id, parent_id
  - created_at, updated_at, synced_at
- **categories** - категории продуктов
- **product_modifiers** - связь продуктов и модификаторов
- **sync_log** - логи синхронизации

## Быстрый старт

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 2. Настройка базы данных
```bash
createdb iiko_data
psql -U postgres -d iiko_data -f migrations/002_create_products_table.sql
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
```

## Основные компоненты

### api_client.py
- `IikoApiClient` - класс для работы с API
  - `authenticate()` - получение токена
  - `get_products()` - получение продуктов
  - `get_departments()` - получение подразделений

### models.py
- SQLAlchemy модели:
  - `Product` - продукты
  - `Category` - категории
  - `SyncLog` - логи

### synchronizer.py
- `DataSynchronizer` - синхронизация данных
  - `sync_products()` - синхронизация продуктов
  - `_sync_single_product()` - обработка одного продукта

### web/app.py
- Flask приложение с маршрутами
- Обработка загрузки файлов
- API для фронтенда

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

### TODO
- [ ] Добавить синхронизацию поставщиков
- [ ] Добавить синхронизацию подразделений
- [ ] Улучшить UI (сделать более профессиональным)
- [ ] Добавить экспорт в Excel
- [ ] Добавить автоматическую синхронизацию по расписанию
- [ ] Добавить авторизацию пользователей

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
