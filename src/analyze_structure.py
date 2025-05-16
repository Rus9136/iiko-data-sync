import json
import sys
sys.path.append('/Users/rus/Projects/iiko-data-sync')

from src.api_client import IIKOApiClient

def analyze_api_response():
    """Анализ структуры ответа API для создания таблиц БД"""
    client = IIKOApiClient()
    
    try:
        # Получаем токен
        token = client.authenticate()
        print(f"Токен авторизации получен: {token[:10]}...")
        
        # Получаем данные продуктов
        products = client.get_products()
        print(f"\nПолучено продуктов: {len(products)}")
        
        # Анализируем структуру
        structure = client.analyze_products_structure()
        
        print("\n=== Структура данных продуктов ===")
        print("\nОсновные поля:")
        for key in sorted(structure['main_keys']):
            print(f"  - {key}")
        
        print("\nВложенные структуры:")
        for key, fields in structure['nested_structures'].items():
            print(f"\n  {key}:")
            for field in sorted(fields):
                print(f"    - {field}")
        
        # Сохраняем пример данных для анализа
        with open('/Users/rus/Projects/iiko-data-sync/sample_product.json', 'w', encoding='utf-8') as f:
            json.dump(products[0] if products else {}, f, ensure_ascii=False, indent=2)
        
        print("\nПример продукта сохранен в sample_product.json")
        
        return structure
        
    except Exception as e:
        print(f"Ошибка: {e}")
        return None

if __name__ == "__main__":
    analyze_api_response()
