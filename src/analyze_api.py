#!/usr/bin/env python3
"""
Скрипт для анализа структуры данных из IIKO API
и создания соответствующих таблиц в PostgreSQL
"""
import requests
import json
import sys

def main():
    # Авторизация
    auth_url = "https://madlen-group-so.iiko.it/resto/api/auth"
    auth_params = {
        'login': 'Tanat',
        'pass': '7c4a8d09ca3762af61e59520943dc26494f8941b'
    }
    
    try:
        print("Получаем токен авторизации...")
        auth_response = requests.get(auth_url, params=auth_params)
        token = auth_response.text.strip().strip('"')
        print(f"Токен получен: {token[:20]}...")
        
        # Получение продуктов
        products_url = "https://madlen-group-so.iiko.it/resto/api/v2/entities/products/list"
        headers = {
            'Cookie': f'key={token}'
        }
        params = {
            'includeDeleted': 'false'
        }
        
        print("\nЗапрашиваем список продуктов...")
        products_response = requests.get(products_url, headers=headers, params=params)
        products = products_response.json()
        
        print(f"Получено продуктов: {len(products)}")
        
        # Анализ структуры
        if products:
            first_product = products[0]
            
            # Сохраняем пример
            with open('/Users/rus/Projects/iiko-data-sync/sample_product.json', 'w', encoding='utf-8') as f:
                json.dump(first_product, f, ensure_ascii=False, indent=2)
            
            print("\nПример продукта сохранен в sample_product.json")
            
            # Выводим структуру
            print("\nСтруктура продукта:")
            analyze_object(first_product)
            
            # Собираем типы данных
            field_types = collect_field_types(products)
            
            print("\n\nТипы полей:")
            for field, types in field_types.items():
                print(f"  {field}: {', '.join(types)}")
                
        else:
            print("Нет данных для анализа")
            
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

def analyze_object(obj, prefix=""):
    """Рекурсивный анализ структуры объекта"""
    for key, value in obj.items():
        if value is None:
            print(f"{prefix}{key}: null")
        elif isinstance(value, dict):
            print(f"{prefix}{key}: object")
            analyze_object(value, prefix + "  ")
        elif isinstance(value, list):
            print(f"{prefix}{key}: array[{len(value)}]")
            if value and isinstance(value[0], dict):
                print(f"{prefix}  [0]:")
                analyze_object(value[0], prefix + "    ")
        else:
            print(f"{prefix}{key}: {type(value).__name__} = {repr(value)[:50]}")

def collect_field_types(products):
    """Собирает информацию о типах полей"""
    field_types = {}
    
    for product in products:
        for key, value in product.items():
            if key not in field_types:
                field_types[key] = set()
            
            if value is None:
                field_types[key].add('null')
            elif isinstance(value, bool):
                field_types[key].add('boolean')
            elif isinstance(value, int):
                field_types[key].add('integer')
            elif isinstance(value, float):
                field_types[key].add('float')
            elif isinstance(value, str):
                field_types[key].add('string')
            elif isinstance(value, dict):
                field_types[key].add('object')
            elif isinstance(value, list):
                field_types[key].add('array')
    
    return field_types

if __name__ == "__main__":
    main()
