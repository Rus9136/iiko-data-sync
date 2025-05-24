import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import request, jsonify, render_template, make_response
from sqlalchemy import create_engine, func, extract, cast, Date, distinct, and_, or_, desc, asc
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
from datetime import datetime, timedelta
import io
import pandas as pd

from src.models import Base, Product, Store, Sale
from config.config import DATABASE_CONFIG

# Подключение к базе данных
db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

def get_sales_report():
    """
    Формирование отчета по продажам с группировкой по складу, номенклатуре и дате
    """
    # Логирование запуска отчета
    print("Запуск формирования отчета по продажам")
    
    session = Session()
    try:
        # Получаем параметры фильтрации
        date_from = request.args.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        date_to = request.args.get('date_to', datetime.now().strftime('%Y-%m-%d'))
        store_id = request.args.get('store_id', '')
        group_by = request.args.get('group_by', 'product')  # По умолчанию группируем по товару
        sort_by = request.args.get('sort_by', 'sum')  # По умолчанию сортируем по сумме
        export_format = request.args.get('format', '')  # Формат экспорта (excel или пусто)
        
        # Преобразуем строки даты в объекты datetime
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d') if date_from else None
            to_date = datetime.strptime(date_to, '%Y-%m-%d') if date_to else None
            
            # Если указана to_date, добавляем 1 день для включения всего дня
            if to_date:
                to_date = to_date + timedelta(days=1)
                
            print(f"Период отчета: с {from_date} по {to_date}")
        except ValueError as e:
            print(f"Ошибка в формате даты: {e}")
            # Устанавливаем даты по умолчанию при ошибке
            from_date = datetime(2025, 5, 1)
            to_date = datetime.now() + timedelta(days=1)
            print(f"Установлены даты по умолчанию: с {from_date} по {to_date}")
        
        # Базовый запрос: фильтруем только активные продажи (не отмененные, не возвраты)
        base_query = session.query(Sale).filter(
            Sale.storned == False,
            or_(Sale.deleted_with_writeoff == 'NOT_DELETED', Sale.deleted_with_writeoff == None),
            or_(Sale.dish_return_sum == 0, Sale.dish_return_sum == None),
            Sale.dish_sum > 0
        )
        
        # Применяем фильтры по дате
        if from_date and to_date:
            base_query = base_query.filter(Sale.close_time >= from_date, Sale.close_time < to_date)
            print(f"Применен фильтр по датам: с {from_date} по {to_date}")
            
            # Проверим количество записей после фильтрации
            filtered_count = base_query.count()
            print(f"Количество записей после фильтрации по датам: {filtered_count}")
        
        # Применяем фильтр по складу
        if store_id:
            base_query = base_query.filter(Sale.store_id == store_id)
        
        # Формируем запрос в зависимости от выбранной группировки
        if group_by == 'day':
            # Группировка по дню, складу и товару
            query = session.query(
                cast(Sale.close_time, Date).label('date'),
                Sale.store_name,
                Sale.store_id,
                Sale.dish_name,
                Sale.dish_code,
                Sale.dish_measure_unit,
                func.sum(Sale.dish_amount).label('total_amount'),
                func.sum(Sale.dish_sum).label('total_sum'),
                func.sum(Sale.dish_discount_sum).label('total_discount'),
                func.count(distinct(Sale.order_num)).label('order_count')
            ).filter(base_query.whereclause).group_by(
                cast(Sale.close_time, Date),
                Sale.store_name,
                Sale.store_id,
                Sale.dish_name,
                Sale.dish_code,
                Sale.dish_measure_unit
            ).order_by(
                cast(Sale.close_time, Date).desc(),
                desc('total_sum') if sort_by == 'sum' else 
                desc('total_amount') if sort_by == 'amount' else
                desc('total_discount') if sort_by == 'discount' else
                Sale.dish_name
            )
            
        elif group_by == 'month':
            # Группировка по месяцу, складу и товару
            query = session.query(
                extract('year', Sale.close_time).label('year'),
                extract('month', Sale.close_time).label('month'),
                func.concat(
                    extract('month', Sale.close_time), '.', 
                    extract('year', Sale.close_time)
                ).label('month_year'),
                Sale.store_name,
                Sale.store_id,
                Sale.dish_name,
                Sale.dish_code,
                Sale.dish_measure_unit,
                func.sum(Sale.dish_amount).label('total_amount'),
                func.sum(Sale.dish_sum).label('total_sum'),
                func.sum(Sale.dish_discount_sum).label('total_discount'),
                func.count(distinct(Sale.order_num)).label('order_count')
            ).filter(base_query.whereclause).group_by(
                extract('year', Sale.close_time),
                extract('month', Sale.close_time),
                'month_year',
                Sale.store_name,
                Sale.store_id,
                Sale.dish_name,
                Sale.dish_code,
                Sale.dish_measure_unit
            ).order_by(
                extract('year', Sale.close_time).desc(),
                extract('month', Sale.close_time).desc(),
                desc('total_sum') if sort_by == 'sum' else 
                desc('total_amount') if sort_by == 'amount' else
                desc('total_discount') if sort_by == 'discount' else
                Sale.dish_name
            )
            
        elif group_by == 'store':
            # Группировка только по складу
            query = session.query(
                Sale.store_name,
                Sale.store_id,
                func.sum(Sale.dish_amount).label('total_amount'),
                func.sum(Sale.dish_sum).label('total_sum'),
                func.sum(Sale.dish_discount_sum).label('total_discount'),
                func.count(distinct(Sale.order_num)).label('order_count'),
                func.min(Sale.dish_measure_unit).label('dish_measure_unit')
            ).filter(base_query.whereclause).group_by(
                Sale.store_name,
                Sale.store_id
            ).order_by(
                desc('total_sum') if sort_by == 'sum' else 
                desc('total_amount') if sort_by == 'amount' else
                desc('total_discount') if sort_by == 'discount' else
                Sale.store_name
            )
            
        else:  # group_by == 'product' или по умолчанию
            # Группировка только по товару
            query = session.query(
                Sale.dish_name,
                Sale.dish_code,
                Sale.dish_measure_unit,
                func.sum(Sale.dish_amount).label('total_amount'),
                func.sum(Sale.dish_sum).label('total_sum'),
                func.sum(Sale.dish_discount_sum).label('total_discount'),
                func.count(distinct(Sale.order_num)).label('order_count')
            ).filter(base_query.whereclause).group_by(
                Sale.dish_name,
                Sale.dish_code,
                Sale.dish_measure_unit
            ).order_by(
                desc('total_sum') if sort_by == 'sum' else 
                desc('total_amount') if sort_by == 'amount' else
                desc('total_discount') if sort_by == 'discount' else
                Sale.dish_name
            )
        
        # Получаем данные отчета
        report_data = query.all()
        print(f"Получено {len(report_data)} записей в отчете")
        
        # Рассчитываем общие суммы для отчета
        total_query = session.query(
            func.sum(Sale.dish_sum).label('total_sum'),
            func.sum(Sale.dish_discount_sum).label('total_discount'),
            func.sum(Sale.dish_amount).label('total_items'),
            func.count(distinct(Sale.dish_name)).label('unique_items'),
            func.count(distinct(Sale.order_num)).label('order_count')
        ).filter(base_query.whereclause)
        
        totals = total_query.first()
        
        # Формируем данные для отображения
        report_result = []
        for row in report_data:
            # Рассчитываем средний чек и рентабельность
            order_count = getattr(row, 'order_count', 0) or 1
            total_sum = getattr(row, 'total_sum', 0) or 0
            total_discount = getattr(row, 'total_discount', 0) or 0
            average_check = total_sum / order_count if order_count > 0 else 0
            
            # Рентабельность (процент скидки от общей суммы)
            profitability = 100 - (total_discount * 100 / (total_sum + total_discount)) if (total_sum + total_discount) > 0 else 100
            
            # Добавляем дополнительные поля в зависимости от группировки
            report_item = {
                'dish_name': getattr(row, 'dish_name', 'Общий итог'),
                'dish_code': getattr(row, 'dish_code', '-'),
                'store_name': getattr(row, 'store_name', 'Все склады'),
                'store_id': getattr(row, 'store_id', None),
                'total_amount': getattr(row, 'total_amount', 0) or 0,
                'dish_measure_unit': getattr(row, 'dish_measure_unit', 'шт.'),
                'total_sum': getattr(row, 'total_sum', 0) or 0,
                'total_discount': getattr(row, 'total_discount', 0) or 0,
                'order_count': order_count,
                'average_check': average_check,
                'profitability': profitability
            }
            
            # Добавляем поля для группировки по дате
            if group_by == 'day':
                report_item['date'] = getattr(row, 'date', None)
            elif group_by == 'month':
                report_item['month_year'] = getattr(row, 'month_year', None)
            
            report_result.append(report_item)
        
        # Получаем общую статистику
        total_sum = totals.total_sum or 0
        discount_sum = totals.total_discount or 0
        total_items = totals.total_items or 0
        unique_items = totals.unique_items or 0
        order_count = totals.order_count or 1
        avg_check = total_sum / order_count if order_count > 0 else 0
        
        # Получаем список складов для фильтра
        stores = session.query(Store).order_by(Store.name).all()
        
        # Если запрошен экспорт в Excel
        if export_format == 'excel':
            return export_to_excel(report_result, group_by, date_from, date_to)
        
        # Рендерим шаблон с данными отчета
        return render_template('sales_report.html',
                             report_data=report_result,
                             total_sum=total_sum,
                             discount_sum=discount_sum,
                             total_items=total_items,
                             unique_items=unique_items,
                             avg_check=avg_check,
                             total_count=len(report_result),
                             date_from=date_from,
                             date_to=date_to,
                             store_id=store_id,
                             group_by=group_by,
                             sort_by=sort_by,
                             stores=stores)
    finally:
        session.close()

def export_to_excel(report_data, group_by, date_from, date_to):
    """
    Экспорт отчета в Excel
    """
    try:
        # Создаем DataFrame из данных отчета
        df = pd.DataFrame(report_data)
        
        # Переименовываем колонки для русского Excel
        column_names = {
            'dish_name': 'Наименование товара',
            'dish_code': 'Код товара',
            'store_name': 'Склад',
            'total_amount': 'Количество',
            'dish_measure_unit': 'Ед. изм.',
            'total_sum': 'Выручка',
            'total_discount': 'Скидки',
            'average_check': 'Средний чек',
            'date': 'Дата',
            'month_year': 'Месяц'
        }
        
        # Применяем только существующие колонки
        rename_dict = {k: v for k, v in column_names.items() if k in df.columns}
        df = df.rename(columns=rename_dict)
        
        # Создаем буфер для записи Excel
        output = io.BytesIO()
        
        # Создаем Excel-writer
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Отчет по продажам', index=False)
            
            # Получаем рабочий лист
            workbook = writer.book
            worksheet = writer.sheets['Отчет по продажам']
            
            # Форматирование для денежных значений
            money_format = workbook.add_format({'num_format': '# ##0.00'})
            
            # Применяем форматирование к столбцам с деньгами
            for i, col in enumerate(df.columns):
                if col in ['Выручка', 'Скидки', 'Средний чек']:
                    worksheet.set_column(i, i, 12, money_format)
                else:
                    worksheet.set_column(i, i, 15)
            
            # Добавляем фильтр к заголовкам
            worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)
        
        # Перемотка буфера на начало
        output.seek(0)
        
        # Формируем имя файла
        period = f"{date_from}_{date_to}"
        filename = f"sales_report_{period}_{group_by}.xlsx"
        
        # Создаем ответ
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
    
    except Exception as e:
        # В случае ошибки возвращаем JSON с ошибкой
        return jsonify({'status': 'error', 'error': str(e)}), 500