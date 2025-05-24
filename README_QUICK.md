# IIKO Data Sync - Quick Reference

## Что это?
Комплексная система для синхронизации данных из IIKO API в PostgreSQL с полнофункциональным веб-интерфейсом, отчетами и экспортом в Excel.

## Быстрый запуск
```bash
# 1. Установка
pip install -r requirements.txt

# 2. База данных
createdb iiko_data
# Применить все миграции
for f in migrations/*.sql; do psql -U postgres -d iiko_data -f "$f"; done

# 3. Запуск веб-интерфейса
python run_web.py
# Откроется http://127.0.0.1:8082
```

## Основные файлы
- `run_web.py` - запуск веб-интерфейса
- `main.py` - консольная синхронизация
- `web/app.py` - Flask приложение с AJAX
- `src/api_client.py` - работа с IIKO API
- `src/*_synchronizer.py` - синхронизаторы для разных сущностей
- `.env` - настройки (логин/пароль)

## API IIKO
- База: `https://madlen-group-so.iiko.it/resto/api`
- Авторизация: `/auth?login={login}&pass={password}`
- Продукты: `/v2/entities/products/list`
- Подразделения: `/corporation/departments`
- Склады: `/corporation/stores`
- Поставщики: `/suppliers`
- Продажи: `/v2/reports/olap`
- Приходные: `/documents/import/incomingInvoice`

## Веб-интерфейс (с боковой панелью)
### Справочники
- `/products` - номенклатура
- `/stores` - склады
- `/suppliers/list` - поставщики
- `/departments` - подразделения
- `/accounts` - счета

### Документы
- `/sales` - продажи (чеки)
- `/writeoffs` - списания
- `/incoming_invoices` - приходные

### Сервис
- `/` - дашборд
- `/upload` - синхронизация
- `/logs` - история
- `/operational-summary` - оперативная сводка
- `/sales/report` - отчеты Excel

## База данных
### Справочники
- `products` - номенклатура
- `stores` - склады
- `departments` - подразделения
- `suppliers` - поставщики
- `accounts` - счета
- `categories` - категории
- `prices` - цены

### Документы
- `sales` - продажи
- `writeoff_documents/items` - списания
- `incoming_invoices/items` - приходные

### Системные
- `sync_log` - история синхронизаций

## Выполненные задачи (декабрь 2025)
✓ Улучшен дизайн с боковой панелью
✓ Добавлены поставщики
✓ Добавлены подразделения
✓ Приходные накладные с CRUD
✓ Отчеты по продажам в Excel
✓ AJAX навигация
✓ Дашборд со статистикой
✓ Цены на продукты

## Команды синхронизации
```bash
# Синхронизация всего
python main.py

# Отдельные сущности
python main.py --entity products
python main.py --entity sales --date-from "2025-05-19"
python main.py --entity incoming_invoices --date-from "2025-05-19"
```

## Проблемы?
1. Проверь `.env` файл
2. Проверь доступность БД
3. Порт 8080 свободен?
4. Смотри логи в консоли
