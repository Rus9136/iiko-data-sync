# IIKO Data Sync - Quick Reference

## Что это?
Система для синхронизации данных из IIKO API в PostgreSQL с веб-интерфейсом.

## Быстрый запуск
```bash
# 1. Установка
pip install -r requirements.txt

# 2. База данных
createdb iiko_data
psql -U postgres -d iiko_data -f migrations/002_create_products_table.sql

# 3. Запуск веб-интерфейса
python run_web.py
# Открыть http://localhost:8080
```

## Основные файлы
- `run_web.py` - запуск веб-интерфейса
- `main.py` - консольная синхронизация
- `web/app.py` - Flask приложение
- `src/api_client.py` - работа с IIKO API
- `src/synchronizer.py` - логика синхронизации
- `.env` - настройки (логин/пароль)

## API IIKO
- База: `https://madlen-group-so.iiko.it/resto/api`
- Авторизация: `/auth?login={login}&pass={password}`
- Продукты: `/v2/entities/products/list`
- Подразделения: `/corporation/departments`

## Веб-интерфейс
- `/` - главная (статистика)
- `/products` - список продуктов
- `/upload` - загрузка JSON
- `/sync` - синхронизация
- `/logs` - история

## База данных
- Таблица: `products` (основные данные)
- Таблица: `categories` (категории)
- Таблица: `sync_log` (логи)

## Текущие задачи
- [ ] Улучшить дизайн интерфейса
- [ ] Добавить поставщиков
- [ ] Добавить подразделения
- [ ] Убрать лишние кнопки

## Проблемы?
1. Проверь `.env` файл
2. Проверь доступность БД
3. Порт 8080 свободен?
4. Смотри логи в консоли
