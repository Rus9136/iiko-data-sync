#!/usr/bin/env python3
"""
Скрипт для проверки корректности отчета по продажам
Сравнивает данные из отчета с данными из базы данных
"""

import sys
import os
from sqlalchemy import create_engine, func, cast, Date, or_, and_
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import argparse
import json

from src.models import Sale
from config.config import DATABASE_CONFIG

# Подключение к базе данных
db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

def get_raw_data(start_date, end_date, dish_name=None):
    """
    Получение исходных данных о продажах из базы данных
    без фильтрации, которая применяется в отчете
    """
    session = Session()
    try:
        from_date = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        to_date = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
        
        # Если указана to_date, добавляем 1 день для включения всего дня
        if to_date:
            to_date = to_date + timedelta(days=1)
        
        # Базовый запрос без фильтрации по статусу
        query = session.query(Sale)
        
        # Применяем фильтры по дате
        if from_date and to_date:
            query = query.filter(Sale.close_time >= from_date, Sale.close_time < to_date)
        
        # Если указано название товара, фильтруем по нему
        if dish_name:
            query = query.filter(Sale.dish_name == dish_name)
        
        # Получаем все записи
        raw_data = query.all()
        
        print(f"Всего записей за период: {len(raw_data)}")
        
        return raw_data
    finally:
        session.close()

def get_report_data(start_date, end_date, dish_name=None):
    """
    Получение данных так, как они фильтруются в отчете
    """
    session = Session()
    try:
        from_date = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        to_date = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
        
        # Если указана to_date, добавляем 1 день для включения всего дня
        if to_date:
            to_date = to_date + timedelta(days=1)
        
        # Базовый запрос с фильтрацией как в отчете
        query = session.query(Sale).filter(
            Sale.storned == False,
            or_(Sale.deleted_with_writeoff == 'NOT_DELETED', Sale.deleted_with_writeoff == None),
            or_(Sale.dish_return_sum == 0, Sale.dish_return_sum == None),
            Sale.dish_sum > 0
        )
        
        # Применяем фильтры по дате
        if from_date and to_date:
            query = query.filter(Sale.close_time >= from_date, Sale.close_time < to_date)
        
        # Если указано название товара, фильтруем по нему
        if dish_name:
            query = query.filter(Sale.dish_name == dish_name)
        
        # Получаем все записи
        report_data = query.all()
        
        print(f"Записей после фильтрации отчета: {len(report_data)}")
        
        return report_data
    finally:
        session.close()

def calculate_totals(data):
    """
    Расчет общих сумм и количеств для данных
    """
    total_sum = sum(sale.dish_sum or 0 for sale in data)
    total_discount = sum(sale.dish_discount_sum or 0 for sale in data)
    total_amount = sum(sale.dish_amount or 0 for sale in data)
    
    # Подсчет уникальных заказов
    order_nums = set()
    for sale in data:
        if sale.order_num:
            order_nums.add(sale.order_num)
    
    result = {
        "total_records": len(data),
        "total_sum": total_sum,
        "total_discount": total_discount,
        "total_amount": total_amount,
        "unique_orders": len(order_nums)
    }
    
    return result

def group_by_product(data):
    """
    Группировка данных по продуктам, аналогично отчету
    """
    product_groups = {}
    
    for sale in data:
        dish_name = sale.dish_name
        if dish_name not in product_groups:
            product_groups[dish_name] = {
                "dish_name": dish_name,
                "dish_code": sale.dish_code,
                "total_sum": 0,
                "total_discount": 0,
                "total_amount": 0,
                "orders": set()
            }
        
        product_groups[dish_name]["total_sum"] += sale.dish_sum or 0
        product_groups[dish_name]["total_discount"] += sale.dish_discount_sum or 0
        product_groups[dish_name]["total_amount"] += sale.dish_amount or 0
        if sale.order_num:
            product_groups[dish_name]["orders"].add(sale.order_num)
    
    # Преобразуем в список
    result = []
    for dish_name, group in product_groups.items():
        group["order_count"] = len(group["orders"])
        del group["orders"]  # Удаляем ненужное множество
        result.append(group)
    
    # Сортируем по сумме продаж
    result.sort(key=lambda x: x["total_sum"], reverse=True)
    
    return result

def compare_records(raw_data, report_data, dish_name=None):
    """
    Сравнение исходных данных с данными отчета
    """
    raw_totals = calculate_totals(raw_data)
    report_totals = calculate_totals(report_data)
    
    print("\n========== СРАВНЕНИЕ ДАННЫХ ==========")
    print(f"Всего записей в базе: {raw_totals['total_records']}")
    print(f"Всего записей в отчете: {report_totals['total_records']}")
    print(f"Отфильтровано записей: {raw_totals['total_records'] - report_totals['total_records']}")
    
    print("\n---------- СУММЫ ----------")
    print(f"Сумма продаж в базе: {raw_totals['total_sum']:,.3f} ₸")
    print(f"Сумма продаж в отчете: {report_totals['total_sum']:,.3f} ₸")
    print(f"Разница: {raw_totals['total_sum'] - report_totals['total_sum']:,.3f} ₸")
    
    print("\n---------- СКИДКИ ----------")
    print(f"Сумма скидок в базе: {raw_totals['total_discount']:,.3f} ₸")
    print(f"Сумма скидок в отчете: {report_totals['total_discount']:,.3f} ₸")
    print(f"Разница: {raw_totals['total_discount'] - report_totals['total_discount']:,.3f} ₸")
    
    print("\n---------- КОЛИЧЕСТВО ----------")
    print(f"Количество в базе: {raw_totals['total_amount']:,}")
    print(f"Количество в отчете: {report_totals['total_amount']:,}")
    print(f"Разница: {raw_totals['total_amount'] - report_totals['total_amount']:,}")
    
    print("\n---------- УНИКАЛЬНЫЕ ЗАКАЗЫ ----------")
    print(f"Уникальных заказов в базе: {raw_totals['unique_orders']:,}")
    print(f"Уникальных заказов в отчете: {report_totals['unique_orders']:,}")
    print(f"Разница: {raw_totals['unique_orders'] - report_totals['unique_orders']:,}")
    
    # Если указано название товара, проводим более детальный анализ
    if dish_name:
        print(f"\n========== ДЕТАЛИ ПО ТОВАРУ: {dish_name} ==========")
        
        # Анализируем отфильтрованные записи
        filtered_out = [s for s in raw_data if s not in report_data]
        
        if filtered_out:
            print(f"\nОтфильтровано записей: {len(filtered_out)}")
            print("Причины фильтрации:")
            storned_count = sum(1 for s in filtered_out if s.storned == True)
            deleted_count = sum(1 for s in filtered_out if s.deleted_with_writeoff != 'NOT_DELETED' and s.deleted_with_writeoff is not None)
            return_count = sum(1 for s in filtered_out if s.dish_return_sum and s.dish_return_sum > 0)
            zero_sum_count = sum(1 for s in filtered_out if s.dish_sum is None or s.dish_sum <= 0)
            
            print(f"- Отмененные чеки (storned=True): {storned_count}")
            print(f"- Удаленные чеки (deleted_with_writeoff != NOT_DELETED): {deleted_count}")
            print(f"- Возвраты (dish_return_sum > 0): {return_count}")
            print(f"- Нулевая сумма (dish_sum <= 0): {zero_sum_count}")
    
    return {
        "raw_totals": raw_totals,
        "report_totals": report_totals
    }

def analyze_product(start_date, end_date, dish_name):
    """
    Анализ конкретного товара
    """
    print(f"\n========== АНАЛИЗ ТОВАРА: {dish_name} ==========")
    
    # Получаем данные о товаре
    raw_data = get_raw_data(start_date, end_date, dish_name)
    report_data = get_report_data(start_date, end_date, dish_name)
    
    # Сравниваем данные
    result = compare_records(raw_data, report_data, dish_name)
    
    # Группируем данные как в отчете
    raw_grouped = group_by_product(raw_data)
    report_grouped = group_by_product(report_data)
    
    # Находим данные о товаре
    raw_product = next((item for item in raw_grouped if item["dish_name"] == dish_name), None)
    report_product = next((item for item in report_grouped if item["dish_name"] == dish_name), None)
    
    if raw_product and report_product:
        print("\n---------- ДАННЫЕ ТОВАРА В БАЗЕ ----------")
        print(f"Код товара: {raw_product['dish_code']}")
        print(f"Количество: {raw_product['total_amount']}")
        print(f"Сумма продаж: {raw_product['total_sum']:,.3f} ₸")
        print(f"Сумма скидок: {raw_product['total_discount']:,.3f} ₸")
        print(f"Количество заказов: {raw_product['order_count']}")
        
        print("\n---------- ДАННЫЕ ТОВАРА В ОТЧЕТЕ ----------")
        print(f"Код товара: {report_product['dish_code']}")
        print(f"Количество: {report_product['total_amount']}")
        print(f"Сумма продаж: {report_product['total_sum']:,.3f} ₸")
        print(f"Сумма скидок: {report_product['total_discount']:,.3f} ₸")
        print(f"Количество заказов: {report_product['order_count']}")
        
        # Рассчитываем рентабельность
        if report_product['total_sum'] + report_product['total_discount'] > 0:
            profitability = 100 - (report_product['total_discount'] * 100 / (report_product['total_sum'] + report_product['total_discount']))
            print(f"\nРентабельность: {profitability:.2f}%")
    
    return {
        "raw_product": raw_product,
        "report_product": report_product
    }

def main():
    parser = argparse.ArgumentParser(description='Проверка корректности отчета по продажам')
    parser.add_argument('--start-date', default='2025-05-01', help='Начальная дата в формате YYYY-MM-DD')
    parser.add_argument('--end-date', default='2025-05-20', help='Конечная дата в формате YYYY-MM-DD')
    parser.add_argument('--dish', help='Название товара для детального анализа')
    
    args = parser.parse_args()
    
    print(f"Проверка отчета за период: {args.start_date} - {args.end_date}")
    
    # Получаем исходные данные
    raw_data = get_raw_data(args.start_date, args.end_date)
    
    # Получаем данные отчета
    report_data = get_report_data(args.start_date, args.end_date)
    
    # Сравниваем данные
    result = compare_records(raw_data, report_data)
    
    # Если указано название товара, анализируем его
    if args.dish:
        product_result = analyze_product(args.start_date, args.end_date, args.dish)
    elif raw_data:
        # Если товар не указан, но есть данные, анализируем первый товар из отчета
        grouped_data = group_by_product(report_data)
        if grouped_data:
            top_product = grouped_data[0]["dish_name"]
            print(f"\nАвтоматический анализ популярного товара: {top_product}")
            product_result = analyze_product(args.start_date, args.end_date, top_product)

if __name__ == "__main__":
    main()