#!/usr/bin/env python3
"""
Тест комплексной синхронизации
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_complex_sync():
    """Тест механизма комплексной синхронизации"""
    print("=== Тестирование комплексной синхронизации ===")
    
    # Параметры тестирования
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=7)  # Последние 7 дней
    
    print(f"Тестовые параметры:")
    print(f"  Период: с {start_date} по {end_date}")
    print(f"  Типы документов: Чеки, Приходные накладные, Списания")
    
    # Проверяем наличие необходимых endpoint'ов
    from web.app import app
    
    with app.test_client() as client:
        # 1. Тест синхронизации продаж
        print("\n1. Проверка endpoint синхронизации продаж...")
        response = client.post('/sync', json={
            'entity': 'sales',
            'start_date': f'{start_date}T00:00:00',
            'end_date': f'{end_date}T23:59:59',
            'clear_existing': False
        })
        print(f"   Статус: {response.status_code}")
        if response.status_code == 200:
            data = response.get_json()
            print(f"   Результат: {data.get('status')}")
            if data.get('stats'):
                print(f"   Создано: {data['stats'].get('created', 0)}")
        
        # 2. Тест получения поставщиков
        print("\n2. Проверка endpoint списка поставщиков...")
        response = client.get('/suppliers/list')
        print(f"   Статус: {response.status_code}")
        if response.status_code == 200:
            data = response.get_json()
            supplier_count = len(data.get('suppliers', []))
            print(f"   Найдено поставщиков: {supplier_count}")
            
            # 3. Тест синхронизации накладных
            if supplier_count > 0:
                print("\n3. Проверка endpoint синхронизации накладных...")
                first_supplier = data['suppliers'][0]
                response = client.post('/incoming_invoices/sync', json={
                    'from_date': str(start_date),
                    'to_date': str(end_date),
                    'supplier_id': first_supplier['id']
                })
                print(f"   Статус: {response.status_code}")
                if response.status_code == 200:
                    data = response.get_json()
                    print(f"   Результат: {data.get('status')}")
        
        # 4. Тест синхронизации списаний
        print("\n4. Проверка endpoint синхронизации списаний...")
        response = client.post('/sync', json={
            'entity': 'writeoffs',
            'start_date': str(start_date),
            'end_date': str(end_date)
        })
        print(f"   Статус: {response.status_code}")
        if response.status_code == 200:
            data = response.get_json()
            print(f"   Результат: {data.get('status')}")
            if data.get('stats'):
                print(f"   Документов создано: {data['stats'].get('documents_created', 0)}")
        
        # 5. Проверка страницы загрузки
        print("\n5. Проверка страницы /upload...")
        response = client.get('/upload')
        print(f"   Статус: {response.status_code}")
        if response.status_code == 200:
            content = response.get_data(as_text=True)
            if 'Комплексная синхронизация документов' in content:
                print("   ✓ Блок комплексной синхронизации найден")
            else:
                print("   ✗ Блок комплексной синхронизации НЕ найден")
    
    print("\n✅ Тестирование завершено!")
    return True

if __name__ == "__main__":
    test_complex_sync()