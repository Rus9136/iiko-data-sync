#!/usr/bin/env python3
"""
Тест для проверки отчетов по списаниям
"""

import requests
from datetime import datetime, timedelta
import json

# Базовый URL
BASE_URL = "http://127.0.0.1:8081"

def test_writeoff_reports():
    """Тестирование всех типов отчетов по списаниям"""
    
    # Параметры для тестирования
    date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    date_to = datetime.now().strftime('%Y-%m-%d')
    
    print(f"Тестирование отчетов по списаниям за период: {date_from} - {date_to}")
    print("=" * 80)
    
    # Тест 1: Отчет по периодам
    print("\n1. Тестирование отчета 'Списания по периодам':")
    url = f"{BASE_URL}/reports/api/writeoffs-by-period/data"
    params = {
        'dateRange': 'month',
        'store': 'all',
        'account': 'all',
        'writeoffReportType': 'writeoffs_by_period'
    }
    
    response = requests.get(url, params=params)
    print(f"   Статус: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"   Успех: {data.get('success', False)}")
        print(f"   Количество записей: {len(data.get('data', []))}")
        if data.get('data'):
            first_record = data['data'][0]
            print(f"   Первая запись: {json.dumps(first_record, ensure_ascii=False, indent=2)}")
    else:
        print(f"   Ошибка: {response.text}")
    
    # Тест 2: Отчет по причинам
    print("\n2. Тестирование отчета 'Списания по причинам':")
    params['writeoffReportType'] = 'writeoffs_by_reason'
    
    response = requests.get(url, params=params)
    print(f"   Статус: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"   Успех: {data.get('success', False)}")
        print(f"   Количество записей: {len(data.get('data', []))}")
        if data.get('data'):
            # Показываем топ-3 причины
            print("   Топ-3 причины списания:")
            for i, record in enumerate(data['data'][:3], 1):
                print(f"     {i}. {record['account_name']}: {record['total_cost']:.2f} ₸ ({record['percentage']:.2f}%)")
    
    # Тест 3: Отчет по товарам
    print("\n3. Тестирование отчета 'Списания по товарам':")
    params['writeoffReportType'] = 'writeoffs_by_product'
    
    response = requests.get(url, params=params)
    print(f"   Статус: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"   Успех: {data.get('success', False)}")
        print(f"   Количество записей: {len(data.get('data', []))}")
        if data.get('data'):
            # Показываем топ-5 товаров
            print("   Топ-5 списываемых товаров:")
            for record in data['data'][:5]:
                print(f"     {record['rank']}. [{record['product_code']}] {record['product_name']}: {record['total_cost']:.2f} ₸")
    
    # Тест 4: Проверка Excel экспорта
    print("\n4. Тестирование экспорта в Excel:")
    export_url = f"{BASE_URL}/reports/api/writeoffs-by-period/export"
    
    response = requests.get(export_url, params=params)
    print(f"   Статус: {response.status_code}")
    
    if response.status_code == 200:
        print(f"   Размер файла: {len(response.content)} байт")
        # Сохраняем файл для проверки
        with open('/tmp/test_writeoffs_export.xlsx', 'wb') as f:
            f.write(response.content)
        print("   Файл сохранен: /tmp/test_writeoffs_export.xlsx")
    
    # Тест 5: Проверка страницы отчета
    print("\n5. Тестирование страницы отчета:")
    page_url = f"{BASE_URL}/reports/writeoffs-by-period"
    
    response = requests.get(page_url)
    print(f"   Статус: {response.status_code}")
    if response.status_code == 200:
        print("   Страница загружена успешно")

if __name__ == "__main__":
    test_writeoff_reports()