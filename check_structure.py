#!/usr/bin/env python3
"""
Скрипт для быстрой проверки структуры данных из IIKO API
"""
import requests
import json
import sys

def check_product_structure():
    # Параметры авторизации
    auth_url = "https://madlen-group-so.iiko.it/resto/api/auth"
    auth_params = {
        'login': 'Tanat',
        'pass': '7c4a8d09ca3762af61e59520943dc26494f8941b'
    }
    
    try:
        # Получаем токен
        print("Получаем токен авторизации...")
        auth_response = requests.get(auth_url, params=auth_params)
        token = auth_response.text.strip().strip('"')
        print(f"Токен получен: {token[:20]}...")
        
        # Получаем продукты
        products_url = "https://madlen-group-so.iiko.it/resto/api/v2/entities/products/list"
        headers = {
            'Cookie': f'key={token}'
        }
        params = {
            'includeDeleted': 'false'
        }
        
        print("\nЗапрашиваем продукты...")
        products_response = requests.get(products_url, headers=headers, params=params)
        products = products_response.json()
        
        print(f"Получено продуктов: {len(products)}")
        
        if products:
            # Анализируем первые несколько продуктов
            print("\nПример структуры продукта:")
            example_product = products[0]
            
            # Красивый вывод
            for key, value in example_product.items():
                if isinstance(value, list):
                    print(f"  {key}: {type(value).__name__} (length: {len(value)})")
                else:
                    print(f"  {key}: {type(value).__name__} = {value}")
            
            # Сохраняем примеры для анализа
            with open('product_examples.json', 'w', encoding='utf-8') as f:
                json.dump(products[:5], f, ensure_ascii=False, indent=2)
            
            print("\nПримеры продуктов сохранены в product_examples.json")
            
            # Анализ всех уникальных ключей
            all_keys = set()
            for product in products:
                all_keys.update(product.keys())
            
            print("\nВсе уникальные поля:")
            for key in sorted(all_keys):
                print(f"  - {key}")
            
            # Проверяем наличие null значений
            null_fields = {}
            for product in products:
                for key, value in product.items():
                    if value is None:
                        null_fields[key] = null_fields.get(key, 0) + 1
            
            if null_fields:
                print("\nПоля с NULL значениями:")
                for key, count in null_fields.items():
                    print(f"  {key}: {count} раз")
            
            return products
        
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    check_product_structure()
