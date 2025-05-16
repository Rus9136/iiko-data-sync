import requests
import json
from typing import Dict, Any, Optional
from config.config import IIKO_API_BASE_URL, IIKO_API_LOGIN, IIKO_API_PASSWORD

class IIKOApiClient:
    def __init__(self):
        self.base_url = IIKO_API_BASE_URL
        self.token = None
        
    def authenticate(self) -> str:
        """Получение токена авторизации"""
        auth_url = f"{self.base_url}/auth"
        params = {
            'login': IIKO_API_LOGIN,
            'pass': IIKO_API_PASSWORD
        }
        
        response = requests.get(auth_url, params=params)
        response.raise_for_status()
        
        self.token = response.text.strip().strip('"')
        return self.token
    
    def get_products(self, include_deleted: bool = False) -> list:
        """Получение списка продуктов с поддержкой пагинации"""
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.token:
            self.authenticate()
            
        products_url = f"{self.base_url}/v2/entities/products/list"
        headers = {
            'Cookie': f'key={self.token}'
        }
        
        all_products = []
        page = 0
        page_size = 4000  # Оптимальный размер страницы
        has_more = True
        
        logger.info(f"Начинаем загрузку продуктов с пагинацией (размер страницы: {page_size})...")
        
        while has_more:
            params = {
                'includeDeleted': str(include_deleted).lower(),
                'pageSize': page_size,
                'page': page
            }
            
            logger.info(f"Загрузка страницы {page}...")
            
            response = requests.get(products_url, params=params, headers=headers)
            response.raise_for_status()
            
            products_page = response.json()
            if not products_page:
                logger.info(f"Получена пустая страница {page}, завершаем загрузку")
                break
                
            logger.info(f"Загружено {len(products_page)} продуктов со страницы {page}")
            all_products.extend(products_page)
            
            # Проверяем, есть ли еще страницы
            if len(products_page) < page_size:
                logger.info(f"Достигнут конец списка продуктов (получено {len(products_page)} из {page_size})")
                has_more = False
            else:
                page += 1
        
        logger.info(f"Загрузка завершена. Всего загружено {len(all_products)} продуктов")
        return all_products
    
    def analyze_products_structure(self) -> Dict[str, set]:
        """Анализ структуры данных продуктов"""
        products_data = self.get_products()
        
        # Собираем все уникальные ключи
        all_keys = set()
        nested_structures = {}
        
        for product in products_data:
            all_keys.update(product.keys())
            
            # Анализируем вложенные структуры
            for key, value in product.items():
                if isinstance(value, dict):
                    nested_structures[key] = set(value.keys())
                elif isinstance(value, list) and value and isinstance(value[0], dict):
                    nested_structures[f"{key}[]"] = set(value[0].keys())
        
        return {
            'main_keys': all_keys,
            'nested_structures': nested_structures
        }
