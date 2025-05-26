#!/usr/bin/env python3
"""
Тест функциональности оперативной сводки
"""
import requests
import json
from datetime import datetime, timedelta

# Базовый URL веб-сервера
BASE_URL = "http://127.0.0.1:8080"

def test_operational_summary_page():
    """Тестируем загрузку страницы оперативной сводки"""
    print("=== Тест загрузки страницы ===")
    try:
        response = requests.get(f"{BASE_URL}/operational-summary")
        print(f"Статус страницы: {response.status_code}")
        if response.status_code == 200:
            print("✓ Страница загружается успешно")
            return True
        else:
            print(f"✗ Ошибка загрузки страницы: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Ошибка подключения: {e}")
        return False

def test_departments_api():
    """Тестируем API получения департаментов"""
    print("\n=== Тест API департаментов ===")
    try:
        response = requests.get(f"{BASE_URL}/api/departments")
        print(f"Статус API: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Получено департаментов: {len(data)}")
            if data:
                print(f"Первый департамент: {data[0]['name']}")
            return True
        else:
            print(f"✗ Ошибка API: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Ошибка API: {e}")
        return False

def test_operational_reports():
    """Тестируем генерацию отчетов"""
    print("\n=== Тест генерации отчетов ===")
    
    # Подготавливаем данные для теста
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    
    test_params = {
        'report_type': 'sales_by_period',
        'date_from': week_ago.strftime('%Y-%m-%d'),
        'date_to': today.strftime('%Y-%m-%d'),
        'periodType': 'day'
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/operational-reports",
            json=test_params,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"Статус отчета: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Отчет сгенерирован успешно")
            print(f"Статус: {data.get('status')}")
            print(f"Записей: {data.get('total_records', 0)}")
            print(f"Колонок: {len(data.get('columns', []))}")
            
            if data.get('data'):
                print(f"Первая запись: {data['data'][0] if data['data'] else 'Нет данных'}")
            
            return True
        else:
            print(f"✗ Ошибка генерации отчета: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Сообщение об ошибке: {error_data.get('message', 'Неизвестная ошибка')}")
            except:
                print(f"Ответ сервера: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"✗ Ошибка запроса: {e}")
        return False

def test_all_report_types():
    """Тестируем все типы отчетов"""
    print("\n=== Тест всех типов отчетов ===")
    
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    
    report_types = [
        'sales_by_period',
        'sales_by_hour', 
        'sales_by_weekday',
        'sales_by_department',
        'top_products',
        'average_check'
    ]
    
    success_count = 0
    
    for report_type in report_types:
        print(f"\nТестируем отчет: {report_type}")
        
        test_params = {
            'report_type': report_type,
            'date_from': week_ago.strftime('%Y-%m-%d'),
            'date_to': today.strftime('%Y-%m-%d')
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/operational-reports",
                json=test_params,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                data = response.json()
                records = data.get('total_records', 0)
                print(f"  ✓ {report_type}: {records} записей")
                success_count += 1
            else:
                print(f"  ✗ {report_type}: ошибка {response.status_code}")
                
        except Exception as e:
            print(f"  ✗ {report_type}: исключение {e}")
    
    print(f"\nУспешно: {success_count}/{len(report_types)} отчетов")
    return success_count == len(report_types)

if __name__ == "__main__":
    print("Тестирование функциональности Оперативной сводки")
    print("=" * 50)
    
    # Последовательно тестируем все компоненты
    tests = [
        test_operational_summary_page,
        test_departments_api,
        test_operational_reports,
        test_all_report_types
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
    
    print("\n" + "=" * 50)
    print("ИТОГИ ТЕСТИРОВАНИЯ:")
    print(f"Успешных тестов: {sum(results)}/{len(results)}")
    
    if all(results):
        print("✓ Все тесты прошли успешно!")
    else:
        print("✗ Есть проблемы, требующие внимания")