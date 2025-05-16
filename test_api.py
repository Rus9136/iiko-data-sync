import requests
import json

# Авторизация
auth_url = "https://madlen-group-so.iiko.it/resto/api/auth"
auth_params = {
    'login': 'Tanat',
    'pass': '7c4a8d09ca3762af61e59520943dc26494f8941b'
}

try:
    auth_response = requests.get(auth_url, params=auth_params)
    token = auth_response.text.strip().strip('"')
    print(f"Token: {token[:20]}...")
    
    # Получение продуктов
    products_url = "https://madlen-group-so.iiko.it/resto/api/v2/entities/products/list"
    headers = {'Cookie': f'key={token}'}
    params = {'includeDeleted': 'false'}
    
    products_response = requests.get(products_url, headers=headers, params=params)
    products = products_response.json()
    
    print(f"\nTotal products: {len(products)}")
    
    if products:
        # Анализируем первый продукт
        first_product = products[0]
        
        print("\nProduct structure:")
        for key, value in first_product.items():
            if value is None:
                value_type = "null"
            elif isinstance(value, dict):
                value_type = "object"
            elif isinstance(value, list):
                value_type = f"array[{len(value)}]"
            else:
                value_type = type(value).__name__
            print(f"  {key}: {value_type}")
        
        # Сохраняем пример
        with open('sample_product.json', 'w', encoding='utf-8') as f:
            json.dump(first_product, f, ensure_ascii=False, indent=2)
        
        print("\nSample saved to sample_product.json")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
