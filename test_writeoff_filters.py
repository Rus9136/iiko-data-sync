#!/usr/bin/env python3
"""
Тест фильтров для отчетов по списаниям
"""

import requests
from datetime import datetime, timedelta
import json

# Базовый URL
BASE_URL = "http://127.0.0.1:8081"

def get_stores():
    """Получить список магазинов"""
    response = requests.get(f"{BASE_URL}/reports/api/filters/stores")
    if response.status_code == 200:
        data = response.json()
        return data.get('options', [])
    return []

def get_accounts():
    """Получить список счетов"""
    response = requests.get(f"{BASE_URL}/reports/api/filters/accounts")
    if response.status_code == 200:
        data = response.json()
        return data.get('options', [])
    return []

def test_filters():
    """Тестирование фильтров"""
    print("Тестирование фильтров отчетов по списаниям")
    print("=" * 80)
    
    # Получаем списки для фильтров
    stores = get_stores()
    accounts = get_accounts()
    
    print(f"\nНайдено магазинов: {len(stores)}")
    if stores:
        print(f"Первые 3 магазина: {[s['text'] for s in stores[:3]]}")
    
    print(f"\nНайдено счетов: {len(accounts)}")
    if accounts:
        print(f"Первые 3 счета: {[a['text'] for a in accounts[:3]]}")
    
    # Базовый URL для отчетов
    url = f"{BASE_URL}/reports/api/writeoffs-by-period/data"
    
    # Тест 1: Фильтр по первому магазину
    if stores:
        print("\n1. Тест фильтра по магазину:")
        store_id = stores[0]['value']
        store_name = stores[0]['text']
        
        params = {
            'dateRange': 'month',
            'store': store_id,
            'account': 'all',
            'writeoffReportType': 'writeoffs_by_period'
        }
        
        print(f"   Фильтр по магазину: {store_name} (ID: {store_id})")
        
        response = requests.get(url, params=params)
        print(f"   Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Успех: {data.get('success', False)}")
            if not data.get('success'):
                print(f"   Ошибка: {data.get('error', 'Unknown error')[:200]}...")
            print(f"   Записей найдено: {len(data.get('data', []))}")
            
            # Проверяем, что все записи относятся к выбранному магазину
            if data.get('data'):
                unique_stores = set(record['store'] for record in data['data'])
                print(f"   Уникальные магазины в результате: {unique_stores}")
        else:
            print(f"   Ошибка: {response.text}")
    
    # Тест 2: Фильтр по первому счету
    if accounts:
        print("\n2. Тест фильтра по счету:")
        account_id = accounts[0]['value']
        account_name = accounts[0]['text']
        
        params = {
            'dateRange': 'month',
            'store': 'all',
            'account': account_id,
            'writeoffReportType': 'writeoffs_by_reason'
        }
        
        print(f"   Фильтр по счету: {account_name} (ID: {account_id})")
        
        response = requests.get(url, params=params)
        print(f"   Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Успех: {data.get('success', False)}")
            print(f"   Записей найдено: {len(data.get('data', []))}")
            
            if data.get('data'):
                print(f"   Первая запись: {json.dumps(data['data'][0], ensure_ascii=False, indent=2)}")
        else:
            print(f"   Ошибка: {response.text}")
    
    # Тест 3: Комбинированный фильтр
    if stores and accounts:
        print("\n3. Тест комбинированного фильтра (магазин + счет):")
        
        params = {
            'dateRange': 'month',
            'store': stores[0]['value'],
            'account': accounts[0]['value'],
            'writeoffReportType': 'writeoffs_by_product'
        }
        
        print(f"   Фильтры: магазин={stores[0]['text']}, счет={accounts[0]['text']}")
        
        response = requests.get(url, params=params)
        print(f"   Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Успех: {data.get('success', False)}")
            print(f"   Записей найдено: {len(data.get('data', []))}")
        else:
            print(f"   Ошибка: {response.text}")

if __name__ == "__main__":
    test_filters()