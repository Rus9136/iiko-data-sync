#!/usr/bin/env python3
"""
Тестирование API продуктов для проверки пагинации
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api_client import IikoApiClient
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_api_direct():
    """Тест прямого обращения к API без пагинации"""
    import requests
    
    api_client = IikoApiClient()
    token = api_client.authenticate()
    
    # Тестируем запрос без пагинации
    url = f"{api_client.base_url}/v2/entities/products/list"
    headers = {'Cookie': f'key={token}'}
    params = {'includeDeleted': 'false'}
    
    logger.info("Запрос к API без пагинации...")
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    
    products = response.json()
    logger.info(f"Получено {len(products)} продуктов без пагинации")
    
    # Проверяем уникальность ID
    ids = [p.get('id') for p in products]
    unique_ids = set(ids)
    logger.info(f"Уникальных ID: {len(unique_ids)}")
    
    if len(ids) != len(unique_ids):
        logger.warning("Есть дублирующиеся ID!")
        duplicates = len(ids) - len(unique_ids)
        logger.warning(f"Количество дубликатов: {duplicates}")
    
    # Проверяем первые и последние товары
    if products:
        logger.info(f"Первый товар: {products[0].get('name')} (ID: {products[0].get('id')})")
        logger.info(f"Последний товар: {products[-1].get('name')} (ID: {products[-1].get('id')})")
    
    return products

def test_api_pagination():
    """Тест с правильной пагинацией"""
    import requests
    
    api_client = IikoApiClient()
    token = api_client.authenticate()
    
    url = f"{api_client.base_url}/v2/entities/products/list"
    headers = {'Cookie': f'key={token}'}
    
    all_products = []
    page = 0
    page_size = 1000
    
    logger.info("Тест пагинации с меньшим размером страницы...")
    
    while True:
        params = {
            'includeDeleted': 'false',
            'pageSize': page_size,
            'page': page
        }
        
        logger.info(f"Загрузка страницы {page}...")
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        products_page = response.json()
        if not products_page:
            logger.info("Пустая страница, завершаем")
            break
            
        logger.info(f"Получено {len(products_page)} продуктов на странице {page}")
        
        # Проверяем уникальность в пределах страницы
        page_ids = [p.get('id') for p in products_page]
        unique_page_ids = set(page_ids)
        if len(page_ids) != len(unique_page_ids):
            logger.warning(f"Дубликаты на странице {page}!")
        
        all_products.extend(products_page)
        
        if len(products_page) < page_size:
            logger.info("Достигнут конец списка")
            break
            
        page += 1
        if page >= 10:  # Ограничение для тестирования
            logger.info("Достигнут лимит тестирования")
            break
    
    logger.info(f"Всего загружено {len(all_products)} продуктов через пагинацию")
    
    # Проверяем глобальную уникальность
    all_ids = [p.get('id') for p in all_products]
    unique_all_ids = set(all_ids)
    logger.info(f"Уникальных ID в общем списке: {len(unique_all_ids)}")
    
    return all_products

def main():
    try:
        # Тест без пагинации
        products_no_pagination = test_api_direct()
        
        print("\n" + "="*50 + "\n")
        
        # Тест с пагинацией
        products_with_pagination = test_api_pagination()
        
        # Сравнение
        logger.info("\n=== СРАВНЕНИЕ МЕТОДОВ ===")
        logger.info(f"Без пагинации: {len(products_no_pagination)} товаров")
        logger.info(f"С пагинацией: {len(products_with_pagination)} товаров")
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()