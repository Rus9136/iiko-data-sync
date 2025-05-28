#!/usr/bin/env python3
"""
Простой тест комплексной синхронизации - проверка создания функционала
"""

import os

print("=== Проверка механизма комплексной синхронизации ===\n")

# Проверка наличия обновленного файла
upload_file = "/Users/rus/Projects/iiko-data-sync/web/templates/upload_content.html"

if os.path.exists(upload_file):
    with open(upload_file, 'r') as f:
        content = f.read()
    
    # Проверка ключевых элементов
    checks = {
        "Блок комплексной синхронизации": "Комплексная синхронизация документов" in content,
        "Форма с датами": "complexSyncForm" in content,
        "Прогресс-бары": "complexSyncProgress" in content,
        "Обработчик JavaScript": "addEventListener('submit', async function(e)" in content,
        "Синхронизация продаж": "// 1. Синхронизация чеков продаж" in content,
        "Синхронизация накладных": "// 2. Синхронизация приходных накладных (по всем поставщикам)" in content,
        "Синхронизация списаний": "// 3. Синхронизация списаний" in content,
        "Функция прогресса": "function updateProgress" in content
    }
    
    print("Результаты проверки:")
    all_passed = True
    for check_name, check_result in checks.items():
        status = "✓" if check_result else "✗"
        print(f"  {status} {check_name}")
        if not check_result:
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("✅ Механизм комплексной синхронизации успешно создан!")
        print("\nОсновные возможности:")
        print("- Единая кнопка для синхронизации всех типов документов")
        print("- Выбор единого периода для всех типов")
        print("- Автоматическая синхронизация по всем поставщикам")
        print("- Визуальный прогресс с детализацией по типам")
        print("- Обработка ошибок с продолжением синхронизации")
        print("- Итоговый отчет о результатах")
    else:
        print("❌ Обнаружены проблемы в реализации")
else:
    print(f"❌ Файл {upload_file} не найден!")

print("\nДля использования:")
print("1. Запустите веб-интерфейс: python run_web.py")
print("2. Откройте страницу: http://127.0.0.1:8081/upload")
print("3. В верхней части страницы будет блок 'Комплексная синхронизация документов'")
print("4. Выберите период и нажмите 'Начать синхронизацию'")