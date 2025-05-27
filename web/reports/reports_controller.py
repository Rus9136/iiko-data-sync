from flask import Blueprint, render_template, request, jsonify, abort
from datetime import datetime, timedelta
import json
from sqlalchemy import text
from src.models import Product, Sale, Department, Store, WriteoffDocument, WriteoffItem, Account
from .config.reports_config import REPORTS_CONFIG, FILTERS_CONFIG, REPORT_CATEGORIES, REPORT_COLUMNS, REPORT_CHARTS
import pandas as pd
from io import BytesIO
from flask import send_file

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

class ReportsController:
    
    @staticmethod
    def get_date_range(preset, custom_from=None, custom_to=None):
        """Получение диапазона дат по пресету"""
        today = datetime.now().date()
        
        if preset == 'today':
            return today, today
        elif preset == 'yesterday':
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        elif preset == 'week':
            week_start = today - timedelta(days=today.weekday())
            return week_start, today
        elif preset == 'month':
            month_start = today.replace(day=1)
            return month_start, today
        elif preset == 'quarter':
            quarter_start = today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1)
            return quarter_start, today
        elif preset == 'year':
            year_start = today.replace(month=1, day=1)
            return year_start, today
        elif preset == 'custom' and custom_from and custom_to:
            return datetime.strptime(custom_from, '%Y-%m-%d').date(), datetime.strptime(custom_to, '%Y-%m-%d').date()
        else:
            # По умолчанию - последние 7 дней
            return today - timedelta(days=7), today
    
    @staticmethod
    def get_sales_by_period_data(filters):
        """Получение данных для отчета 'Продажи по периодам'"""
        date_from, date_to = ReportsController.get_date_range(
            filters.get('dateRange', 'week'),
            filters.get('dateFrom'),
            filters.get('dateTo')
        )
        
        # Базовый SQL запрос с правильной группировкой по чекам и связью с таблицей departments
        base_query = """
            WITH cheque_totals AS (
                SELECT 
                    DATE(s.close_time) as date,
                    COALESCE(d.name, 'Не указан') as department,
                    COALESCE(s.store_name, 'Не указана') as store,
                    s.order_num, 
                    s.fiscal_cheque_number, 
                    SUM(s.dish_sum) as cheque_total
                FROM sales s
                LEFT JOIN departments d ON s.department_id = d.id
                WHERE DATE(s.close_time) BETWEEN :date_from AND :date_to
                    AND (s.storned IS NULL OR s.storned = false)
        """
        
        # Добавляем фильтры в CTE
        params = {'date_from': date_from, 'date_to': date_to}
        
        # Фильтр по отделам - теперь используем department_id
        if filters.get('department') and filters.get('department') != 'all':
            departments = filters.get('department') if isinstance(filters.get('department'), list) else [filters.get('department')]
            # Конвертируем строки в UUID, если нужно
            try:
                department_uuids = [d for d in departments if d and d != 'all']
                if department_uuids:
                    # Используем простое IN с приведением к тексту
                    placeholders = ', '.join([f':dept_{i}' for i in range(len(department_uuids))])
                    base_query += f" AND s.department_id::text IN ({placeholders})"
                    # Добавляем параметры
                    for i, dept_id in enumerate(department_uuids):
                        params[f'dept_{i}'] = dept_id
            except Exception as e:
                # Если ошибка конвертации, игнорируем фильтр
                pass
        
        if filters.get('store') and filters.get('store') != 'all':
            stores = filters.get('store') if isinstance(filters.get('store'), list) else [filters.get('store')]
            base_query += f" AND s.store_name IN :stores"
            params['stores'] = tuple(stores)
        
        # Завершаем CTE и основной запрос
        base_query += """
                GROUP BY DATE(s.close_time), d.name, s.store_name, s.order_num, s.fiscal_cheque_number
            )
            SELECT 
                date,
                department,
                store,
                COUNT(*) as orders_count,
                SUM(cheque_total) as total_amount,
                ROUND(AVG(cheque_total), 2) as avg_check
            FROM cheque_totals
            GROUP BY date, department, store
            ORDER BY date DESC, total_amount DESC
        """
        
        try:
            # Получаем сессию базы данных
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from config.config import DATABASE_CONFIG
            
            db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
            engine = create_engine(db_url)
            Session = sessionmaker(bind=engine)
            session = Session()
                
            try:
                result = session.execute(text(base_query), params)
                data = []
                for row in result:
                    data.append({
                        'date': row.date.strftime('%Y-%m-%d') if row.date else '',
                        'department': row.department or 'Не указан',
                        'store': row.store or 'Не указана',
                        'orders_count': int(row.orders_count) if row.orders_count else 0,
                        'total_amount': round(float(row.total_amount), 2) if row.total_amount else 0.0,  # Сумма в тенге
                        'avg_check': round(float(row.avg_check), 2) if row.avg_check else 0.0  # Средний чек в тенге
                    })
                
                return {
                    'success': True,
                    'data': data,
                    'total_records': len(data)
                }
            finally:
                session.close()
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    @staticmethod
    def get_sales_by_hour_data(filters):
        """Получение данных для отчета 'Продажи по часам дня'"""
        date_from, date_to = ReportsController.get_date_range(
            filters.get('dateRange', 'week'),
            filters.get('dateFrom'),
            filters.get('dateTo')
        )
        
        base_query = """
            WITH hourly_sales AS (
                SELECT 
                    EXTRACT(HOUR FROM s.close_time) as hour,
                    COUNT(DISTINCT s.order_num || '-' || s.fiscal_cheque_number) as orders_count,
                    SUM(s.dish_sum) as total_amount,
                    COUNT(*) as items_count
                FROM sales s
                LEFT JOIN departments d ON s.department_id = d.id
                WHERE DATE(s.close_time) BETWEEN :date_from AND :date_to
                    AND (s.storned IS NULL OR s.storned = false)
        """
        
        params = {'date_from': date_from, 'date_to': date_to}
        
        # Фильтр по отделам
        if filters.get('department') and filters.get('department') != 'all':
            departments = filters.get('department') if isinstance(filters.get('department'), list) else [filters.get('department')]
            department_uuids = [d for d in departments if d and d != 'all']
            if department_uuids:
                placeholders = ', '.join([f':dept_{i}' for i in range(len(department_uuids))])
                base_query += f" AND s.department_id::text IN ({placeholders})"
                for i, dept_id in enumerate(department_uuids):
                    params[f'dept_{i}'] = dept_id
        
        base_query += """
                GROUP BY EXTRACT(HOUR FROM s.close_time)
            )
            SELECT 
                hour::integer,
                LPAD(hour::text, 2, '0') || ':00-' || LPAD((hour+1)::text, 2, '0') || ':00' as hour_range,
                orders_count,
                total_amount,
                ROUND(total_amount / NULLIF(orders_count, 0), 2) as avg_check,
                ROUND(items_count::numeric / NULLIF(orders_count, 0), 2) as items_per_check
            FROM hourly_sales
            ORDER BY hour
        """
        
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from config.config import DATABASE_CONFIG
            
            db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
            engine = create_engine(db_url)
            Session = sessionmaker(bind=engine)
            session = Session()
                
            try:
                result = session.execute(text(base_query), params)
                data = []
                for row in result:
                    data.append({
                        'hour': row.hour_range,
                        'orders_count': int(row.orders_count) if row.orders_count else 0,
                        'total_amount': round(float(row.total_amount), 2) if row.total_amount else 0.0,
                        'avg_check': round(float(row.avg_check), 2) if row.avg_check else 0.0,
                        'items_per_check': float(row.items_per_check) if row.items_per_check else 0.0
                    })
                
                return {
                    'success': True,
                    'data': data,
                    'total_records': len(data)
                }
            finally:
                session.close()
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    @staticmethod
    def get_sales_by_weekday_data(filters):
        """Получение данных для отчета 'Продажи по дням недели'"""
        date_from, date_to = ReportsController.get_date_range(
            filters.get('dateRange', 'week'),
            filters.get('dateFrom'),
            filters.get('dateTo')
        )
        
        base_query = """
            WITH weekday_sales AS (
                SELECT 
                    EXTRACT(DOW FROM s.close_time) as weekday_num,
                    COUNT(DISTINCT s.order_num || '-' || s.fiscal_cheque_number) as orders_count,
                    SUM(s.dish_sum) as total_amount
                FROM sales s
                LEFT JOIN departments d ON s.department_id = d.id
                WHERE DATE(s.close_time) BETWEEN :date_from AND :date_to
                    AND (s.storned IS NULL OR s.storned = false)
        """
        
        params = {'date_from': date_from, 'date_to': date_to}
        
        # Фильтр по отделам
        if filters.get('department') and filters.get('department') != 'all':
            departments = filters.get('department') if isinstance(filters.get('department'), list) else [filters.get('department')]
            department_uuids = [d for d in departments if d and d != 'all']
            if department_uuids:
                placeholders = ', '.join([f':dept_{i}' for i in range(len(department_uuids))])
                base_query += f" AND s.department_id::text IN ({placeholders})"
                for i, dept_id in enumerate(department_uuids):
                    params[f'dept_{i}'] = dept_id
        
        base_query += """
                GROUP BY EXTRACT(DOW FROM s.close_time)
            )
            SELECT 
                weekday_num,
                CASE weekday_num
                    WHEN 0 THEN 'Воскресенье'
                    WHEN 1 THEN 'Понедельник'
                    WHEN 2 THEN 'Вторник'
                    WHEN 3 THEN 'Среда'
                    WHEN 4 THEN 'Четверг'
                    WHEN 5 THEN 'Пятница'
                    WHEN 6 THEN 'Суббота'
                END as weekday,
                orders_count,
                total_amount,
                ROUND(total_amount / NULLIF(orders_count, 0), 2) as avg_check
            FROM weekday_sales
            ORDER BY 
                CASE weekday_num
                    WHEN 0 THEN 7
                    ELSE weekday_num
                END
        """
        
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from config.config import DATABASE_CONFIG
            
            db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
            engine = create_engine(db_url)
            Session = sessionmaker(bind=engine)
            session = Session()
                
            try:
                result = session.execute(text(base_query), params)
                data = []
                for row in result:
                    data.append({
                        'weekday': row.weekday,
                        'orders_count': int(row.orders_count) if row.orders_count else 0,
                        'total_amount': round(float(row.total_amount), 2) if row.total_amount else 0.0,
                        'avg_check': round(float(row.avg_check), 2) if row.avg_check else 0.0
                    })
                
                return {
                    'success': True,
                    'data': data,
                    'total_records': len(data)
                }
            finally:
                session.close()
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    @staticmethod
    def get_sales_by_department_data(filters):
        """Получение данных для отчета 'Продажи по торговым точкам'"""
        date_from, date_to = ReportsController.get_date_range(
            filters.get('dateRange', 'week'),
            filters.get('dateFrom'),
            filters.get('dateTo')
        )
        
        base_query = """
            WITH department_sales AS (
                SELECT 
                    COALESCE(d.name, 'Не указан') as department,
                    COUNT(DISTINCT s.order_num || '-' || s.fiscal_cheque_number) as orders_count,
                    SUM(s.dish_sum) as total_amount
                FROM sales s
                LEFT JOIN departments d ON s.department_id = d.id
                WHERE DATE(s.close_time) BETWEEN :date_from AND :date_to
                    AND (s.storned IS NULL OR s.storned = false)
        """
        
        params = {'date_from': date_from, 'date_to': date_to}
        
        # Фильтр по отделам
        if filters.get('department') and filters.get('department') != 'all':
            departments = filters.get('department') if isinstance(filters.get('department'), list) else [filters.get('department')]
            department_uuids = [d for d in departments if d and d != 'all']
            if department_uuids:
                placeholders = ', '.join([f':dept_{i}' for i in range(len(department_uuids))])
                base_query += f" AND s.department_id::text IN ({placeholders})"
                for i, dept_id in enumerate(department_uuids):
                    params[f'dept_{i}'] = dept_id
        
        base_query += """
                GROUP BY d.name
            ),
            total_sales AS (
                SELECT SUM(total_amount) as grand_total FROM department_sales
            )
            SELECT 
                ds.department,
                ds.orders_count,
                ds.total_amount,
                ROUND(ds.total_amount / NULLIF(ds.orders_count, 0), 2) as avg_check,
                ROUND((ds.total_amount / NULLIF(ts.grand_total, 0)) * 100, 2) as percentage
            FROM department_sales ds, total_sales ts
            ORDER BY ds.total_amount DESC
        """
        
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from config.config import DATABASE_CONFIG
            
            db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
            engine = create_engine(db_url)
            Session = sessionmaker(bind=engine)
            session = Session()
                
            try:
                result = session.execute(text(base_query), params)
                data = []
                for row in result:
                    data.append({
                        'department': row.department,
                        'orders_count': int(row.orders_count) if row.orders_count else 0,
                        'total_amount': round(float(row.total_amount), 2) if row.total_amount else 0.0,
                        'avg_check': round(float(row.avg_check), 2) if row.avg_check else 0.0,
                        'percentage': float(row.percentage) if row.percentage else 0.0
                    })
                
                return {
                    'success': True,
                    'data': data,
                    'total_records': len(data)
                }
            finally:
                session.close()
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    @staticmethod
    def get_sales_comparison_data(filters):
        """Получение данных для отчета 'Сравнительный анализ продаж между точками'"""
        date_from, date_to = ReportsController.get_date_range(
            filters.get('dateRange', 'week'),
            filters.get('dateFrom'),
            filters.get('dateTo')
        )
        
        # Определяем предыдущий период
        period_length = (date_to - date_from).days + 1
        prev_date_from = date_from - timedelta(days=period_length)
        prev_date_to = date_from - timedelta(days=1)
        
        base_query = """
            WITH current_period AS (
                SELECT 
                    COALESCE(d.name, 'Не указан') as department,
                    SUM(s.dish_sum) as total_amount
                FROM sales s
                LEFT JOIN departments d ON s.department_id = d.id
                WHERE DATE(s.close_time) BETWEEN :date_from AND :date_to
                    AND (s.storned IS NULL OR s.storned = false)
        """
        
        params = {
            'date_from': date_from, 
            'date_to': date_to,
            'prev_date_from': prev_date_from,
            'prev_date_to': prev_date_to
        }
        
        # Фильтр по отделам
        dept_filter = ""
        if filters.get('department') and filters.get('department') != 'all':
            departments = filters.get('department') if isinstance(filters.get('department'), list) else [filters.get('department')]
            department_uuids = [d for d in departments if d and d != 'all']
            if department_uuids:
                placeholders = ', '.join([f':dept_{i}' for i in range(len(department_uuids))])
                dept_filter = f" AND s.department_id::text IN ({placeholders})"
                for i, dept_id in enumerate(department_uuids):
                    params[f'dept_{i}'] = dept_id
        
        base_query += dept_filter + """
                GROUP BY d.name
            ),
            previous_period AS (
                SELECT 
                    COALESCE(d.name, 'Не указан') as department,
                    SUM(s.dish_sum) as total_amount
                FROM sales s
                LEFT JOIN departments d ON s.department_id = d.id
                WHERE DATE(s.close_time) BETWEEN :prev_date_from AND :prev_date_to
                    AND (s.storned IS NULL OR s.storned = false)
        """ + dept_filter + """
                GROUP BY d.name
            )
            SELECT 
                COALESCE(c.department, p.department) as department,
                COALESCE(c.total_amount, 0) as current_amount,
                COALESCE(p.total_amount, 0) as previous_amount,
                COALESCE(c.total_amount, 0) - COALESCE(p.total_amount, 0) as growth,
                CASE 
                    WHEN COALESCE(p.total_amount, 0) = 0 THEN 0
                    ELSE ROUND(((COALESCE(c.total_amount, 0) - COALESCE(p.total_amount, 0)) / p.total_amount) * 100, 2)
                END as growth_percent
            FROM current_period c
            FULL OUTER JOIN previous_period p ON c.department = p.department
            ORDER BY current_amount DESC
        """
        
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from config.config import DATABASE_CONFIG
            
            db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
            engine = create_engine(db_url)
            Session = sessionmaker(bind=engine)
            session = Session()
                
            try:
                result = session.execute(text(base_query), params)
                data = []
                for row in result:
                    data.append({
                        'department': row.department,
                        'current_amount': round(float(row.current_amount), 2) if row.current_amount else 0.0,
                        'previous_amount': round(float(row.previous_amount), 2) if row.previous_amount else 0.0,
                        'growth': round(float(row.growth), 2) if row.growth else 0.0,
                        'growth_percent': float(row.growth_percent) if row.growth_percent else 0.0
                    })
                
                return {
                    'success': True,
                    'data': data,
                    'total_records': len(data)
                }
            finally:
                session.close()
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    @staticmethod
    def get_top_products_data(filters):
        """Получение данных для отчета 'Топ-продаваемых товаров'"""
        date_from, date_to = ReportsController.get_date_range(
            filters.get('dateRange', 'week'),
            filters.get('dateFrom'),
            filters.get('dateTo')
        )
        
        base_query = """
            WITH product_sales AS (
                SELECT 
                    s.dish_name as product_name,
                    p.product_category_name as category,
                    SUM(s.dish_amount) as quantity,
                    SUM(s.dish_sum) as total_amount,
                    COUNT(DISTINCT s.order_num || '-' || s.fiscal_cheque_number) as orders_count
                FROM sales s
                LEFT JOIN departments d ON s.department_id = d.id
                LEFT JOIN products p ON s.dish_code = p.code
                WHERE DATE(s.close_time) BETWEEN :date_from AND :date_to
                    AND (s.storned IS NULL OR s.storned = false)
        """
        
        params = {'date_from': date_from, 'date_to': date_to}
        
        # Фильтр по отделам
        if filters.get('department') and filters.get('department') != 'all':
            departments = filters.get('department') if isinstance(filters.get('department'), list) else [filters.get('department')]
            department_uuids = [d for d in departments if d and d != 'all']
            if department_uuids:
                placeholders = ', '.join([f':dept_{i}' for i in range(len(department_uuids))])
                base_query += f" AND s.department_id::text IN ({placeholders})"
                for i, dept_id in enumerate(department_uuids):
                    params[f'dept_{i}'] = dept_id
        
        base_query += """
                GROUP BY s.dish_name, p.product_category_name
            ),
            total_sales AS (
                SELECT SUM(total_amount) as grand_total FROM product_sales
            )
            SELECT 
                ROW_NUMBER() OVER (ORDER BY ps.total_amount DESC) as rank,
                ps.product_name,
                COALESCE(ps.category, 'Не указана') as category,
                ps.quantity,
                ps.total_amount,
                ps.orders_count,
                ROUND((ps.total_amount / NULLIF(ts.grand_total, 0)) * 100, 2) as percentage
            FROM product_sales ps, total_sales ts
            ORDER BY ps.total_amount DESC
            LIMIT 50
        """
        
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from config.config import DATABASE_CONFIG
            
            db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
            engine = create_engine(db_url)
            Session = sessionmaker(bind=engine)
            session = Session()
                
            try:
                result = session.execute(text(base_query), params)
                data = []
                for row in result:
                    data.append({
                        'rank': int(row.rank),
                        'product_name': row.product_name,
                        'category': row.category,
                        'quantity': float(row.quantity) if row.quantity else 0.0,
                        'total_amount': round(float(row.total_amount), 2) if row.total_amount else 0.0,
                        'percentage': float(row.percentage) if row.percentage else 0.0
                    })
                
                return {
                    'success': True,
                    'data': data,
                    'total_records': len(data)
                }
            finally:
                session.close()
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    @staticmethod
    def get_bottom_products_data(filters):
        """Получение данных для отчета 'Антитоп - товары с минимальными продажами'"""
        date_from, date_to = ReportsController.get_date_range(
            filters.get('dateRange', 'week'),
            filters.get('dateFrom'),
            filters.get('dateTo')
        )
        
        base_query = """
            WITH product_sales AS (
                SELECT 
                    s.dish_name as product_name,
                    p.product_category_name as category,
                    SUM(s.dish_amount) as quantity,
                    SUM(s.dish_sum) as total_amount,
                    MAX(DATE(s.close_time)) as last_sale_date
                FROM sales s
                LEFT JOIN departments d ON s.department_id = d.id
                LEFT JOIN products p ON s.dish_code = p.code
                WHERE DATE(s.close_time) BETWEEN :date_from AND :date_to
                    AND (s.storned IS NULL OR s.storned = false)
        """
        
        params = {'date_from': date_from, 'date_to': date_to, 'current_date': date_to}
        
        # Фильтр по отделам
        if filters.get('department') and filters.get('department') != 'all':
            departments = filters.get('department') if isinstance(filters.get('department'), list) else [filters.get('department')]
            department_uuids = [d for d in departments if d and d != 'all']
            if department_uuids:
                placeholders = ', '.join([f':dept_{i}' for i in range(len(department_uuids))])
                base_query += f" AND s.department_id::text IN ({placeholders})"
                for i, dept_id in enumerate(department_uuids):
                    params[f'dept_{i}'] = dept_id
        
        base_query += """
                GROUP BY s.dish_name, p.product_category_name
                HAVING SUM(s.dish_sum) > 0
            )
            SELECT 
                ROW_NUMBER() OVER (ORDER BY total_amount ASC) as rank,
                product_name,
                COALESCE(category, 'Не указана') as category,
                quantity,
                total_amount,
                (:current_date - last_sale_date) as days_since_sale
            FROM product_sales
            ORDER BY total_amount ASC
            LIMIT 50
        """
        
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from config.config import DATABASE_CONFIG
            
            db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
            engine = create_engine(db_url)
            Session = sessionmaker(bind=engine)
            session = Session()
                
            try:
                result = session.execute(text(base_query), params)
                data = []
                for row in result:
                    data.append({
                        'rank': int(row.rank),
                        'product_name': row.product_name,
                        'category': row.category,
                        'quantity': float(row.quantity) if row.quantity else 0.0,
                        'total_amount': round(float(row.total_amount), 2) if row.total_amount else 0.0,
                        'days_since_sale': int(row.days_since_sale) if row.days_since_sale else 0
                    })
                
                return {
                    'success': True,
                    'data': data,
                    'total_records': len(data)
                }
            finally:
                session.close()
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    @staticmethod
    def get_avg_check_data(filters):
        """Получение данных для отчета 'Средний чек по периодам и точкам'"""
        date_from, date_to = ReportsController.get_date_range(
            filters.get('dateRange', 'week'),
            filters.get('dateFrom'),
            filters.get('dateTo')
        )
        
        base_query = """
            WITH check_data AS (
                SELECT 
                    DATE(s.close_time) as period,
                    COALESCE(d.name, 'Не указан') as department,
                    s.order_num,
                    s.fiscal_cheque_number,
                    SUM(s.dish_sum) as check_total
                FROM sales s
                LEFT JOIN departments d ON s.department_id = d.id
                WHERE DATE(s.close_time) BETWEEN :date_from AND :date_to
                    AND (s.storned IS NULL OR s.storned = false)
        """
        
        params = {'date_from': date_from, 'date_to': date_to}
        
        # Фильтр по отделам
        if filters.get('department') and filters.get('department') != 'all':
            departments = filters.get('department') if isinstance(filters.get('department'), list) else [filters.get('department')]
            department_uuids = [d for d in departments if d and d != 'all']
            if department_uuids:
                placeholders = ', '.join([f':dept_{i}' for i in range(len(department_uuids))])
                base_query += f" AND s.department_id::text IN ({placeholders})"
                for i, dept_id in enumerate(department_uuids):
                    params[f'dept_{i}'] = dept_id
        
        base_query += """
                GROUP BY DATE(s.close_time), d.name, s.order_num, s.fiscal_cheque_number
            )
            SELECT 
                TO_CHAR(period, 'YYYY-MM-DD') as period,
                department,
                ROUND(AVG(check_total), 2) as avg_check,
                ROUND(MIN(check_total), 2) as min_check,
                ROUND(MAX(check_total), 2) as max_check,
                COUNT(*) as orders_count
            FROM check_data
            GROUP BY period, department
            ORDER BY period DESC, department
        """
        
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from config.config import DATABASE_CONFIG
            
            db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
            engine = create_engine(db_url)
            Session = sessionmaker(bind=engine)
            session = Session()
                
            try:
                result = session.execute(text(base_query), params)
                data = []
                for row in result:
                    data.append({
                        'period': row.period,
                        'department': row.department,
                        'avg_check': round(float(row.avg_check), 2) if row.avg_check else 0.0,
                        'min_check': round(float(row.min_check), 2) if row.min_check else 0.0,
                        'max_check': round(float(row.max_check), 2) if row.max_check else 0.0,
                        'orders_count': int(row.orders_count) if row.orders_count else 0
                    })
                
                return {
                    'success': True,
                    'data': data,
                    'total_records': len(data)
                }
            finally:
                session.close()
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    @staticmethod
    def get_check_statistics_data(filters):
        """Получение данных для отчета 'Количество чеков и позиций в чеке'"""
        date_from, date_to = ReportsController.get_date_range(
            filters.get('dateRange', 'week'),
            filters.get('dateFrom'),
            filters.get('dateTo')
        )
        
        base_query = """
            WITH check_stats AS (
                SELECT 
                    DATE(s.close_time) as period,
                    COALESCE(d.name, 'Не указан') as department,
                    s.order_num,
                    s.fiscal_cheque_number,
                    COUNT(*) as items_in_check,
                    COUNT(DISTINCT s.dish_code) as unique_items
                FROM sales s
                LEFT JOIN departments d ON s.department_id = d.id
                WHERE DATE(s.close_time) BETWEEN :date_from AND :date_to
                    AND (s.storned IS NULL OR s.storned = false)
        """
        
        params = {'date_from': date_from, 'date_to': date_to}
        
        # Фильтр по отделам
        if filters.get('department') and filters.get('department') != 'all':
            departments = filters.get('department') if isinstance(filters.get('department'), list) else [filters.get('department')]
            department_uuids = [d for d in departments if d and d != 'all']
            if department_uuids:
                placeholders = ', '.join([f':dept_{i}' for i in range(len(department_uuids))])
                base_query += f" AND s.department_id::text IN ({placeholders})"
                for i, dept_id in enumerate(department_uuids):
                    params[f'dept_{i}'] = dept_id
        
        base_query += """
                GROUP BY DATE(s.close_time), d.name, s.order_num, s.fiscal_cheque_number
            )
            SELECT 
                TO_CHAR(period, 'YYYY-MM-DD') as period,
                department,
                COUNT(*) as orders_count,
                SUM(items_in_check) as total_items,
                ROUND(AVG(items_in_check), 2) as avg_items_per_check,
                SUM(unique_items) as unique_products
            FROM check_stats
            GROUP BY period, department
            ORDER BY period DESC, department
        """
        
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from config.config import DATABASE_CONFIG
            
            db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
            engine = create_engine(db_url)
            Session = sessionmaker(bind=engine)
            session = Session()
                
            try:
                result = session.execute(text(base_query), params)
                data = []
                for row in result:
                    data.append({
                        'period': row.period,
                        'department': row.department,
                        'orders_count': int(row.orders_count) if row.orders_count else 0,
                        'total_items': int(row.total_items) if row.total_items else 0,
                        'avg_items_per_check': float(row.avg_items_per_check) if row.avg_items_per_check else 0.0,
                        'unique_products': int(row.unique_products) if row.unique_products else 0
                    })
                
                return {
                    'success': True,
                    'data': data,
                    'total_records': len(data)
                }
            finally:
                session.close()
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    @staticmethod
    def get_filter_options(filter_type):
        """Получение опций для фильтров"""
        try:
            # Получаем сессию базы данных
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from config.config import DATABASE_CONFIG
            
            db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
            engine = create_engine(db_url)
            Session = sessionmaker(bind=engine)
            session = Session()
                
            try:
                if filter_type == 'departments':
                    departments = session.query(Department).order_by(Department.name).all()
                    return [{'value': str(d.id), 'text': d.name} for d in departments]
                
                elif filter_type == 'stores':
                    stores = session.query(Store).order_by(Store.name).all()
                    return [{'value': str(s.id), 'text': s.name} for s in stores]
                
                elif filter_type == 'accounts':
                    accounts = session.query(Account).order_by(Account.name).all()
                    return [{'value': str(a.id), 'text': a.name} for a in accounts]
                
                elif filter_type == 'categories':
                    # Получаем уникальные категории товаров
                    categories = session.query(Product.product_category_name).distinct().filter(
                        Product.product_category_name.isnot(None)
                    ).order_by(Product.product_category_name).all()
                    return [{'value': cat[0], 'text': cat[0]} for cat in categories if cat[0]]
                
                elif filter_type == 'products':
                    products = session.query(Product).order_by(Product.name).all()
                    return [{'value': str(p.id), 'text': p.name} for p in products]
                
                return []
            finally:
                session.close()
                
        except Exception as e:
            print(f"Error getting filter options for {filter_type}: {e}")
            return []

# Роуты для отчетов
@reports_bp.route('/')
def reports_index():
    """Главная страница отчетов"""
    return render_template('reports/reports_index.html', 
                         reports_config=REPORTS_CONFIG,
                         report_categories=REPORT_CATEGORIES)

@reports_bp.route('/<report_id>')
def report_view(report_id):
    """Страница конкретного отчета"""
    if report_id not in REPORTS_CONFIG:
        abort(404)
    
    report_config = REPORTS_CONFIG[report_id]
    
    # Получаем конфигурации фильтров для данного отчета
    filters_config = {}
    for filter_name in report_config['filters']:
        if filter_name in FILTERS_CONFIG:
            filters_config[filter_name] = FILTERS_CONFIG[filter_name].copy()
            
            # Загружаем опции для select фильтров
            if filters_config[filter_name]['type'] == 'select' and 'source' in filters_config[filter_name]:
                filters_config[filter_name]['options'] = ReportsController.get_filter_options(
                    filters_config[filter_name]['source']
                )
    
    return render_template('reports/report_view.html',
                         report_config=report_config,
                         filters_config=filters_config)

@reports_bp.route('/api/<report_id>/data')
def get_report_data(report_id):
    """API для получения данных отчета"""
    if report_id not in REPORTS_CONFIG:
        return jsonify({'success': False, 'error': 'Report not found'}), 404
    
    # Получаем фильтры из параметров запроса
    filters = {}
    for key, value in request.args.items():
        if key.endswith('[]'):  # Множественные значения
            key = key[:-2]
            filters[key] = request.args.getlist(f'{key}[]')
        else:
            filters[key] = value
    
    # Обрабатываем множественные значения для select полей
    for key in list(filters.keys()):
        if key in ['department', 'store'] and not isinstance(filters[key], list):
            # Если значение не список, но нужно обработать как множественное
            value = filters[key]
            if ',' in value:  # Проверяем, есть ли разделители
                filters[key] = [v.strip() for v in value.split(',')]
            elif value != 'all':  # Если не 'all', оборачиваем в список
                filters[key] = [value]
    
    # Отладочный вывод
    print(f"Report {report_id} filters: {filters}")
    
    # Вызываем соответствующий метод получения данных
    if report_id == 'sales-by-period':
        # Получаем тип отчета
        report_type = filters.get('reportType', 'sales_by_period')
        
        # Вызываем соответствующий метод
        if report_type == 'sales_by_period':
            result = ReportsController.get_sales_by_period_data(filters)
        elif report_type == 'sales_by_hour':
            result = ReportsController.get_sales_by_hour_data(filters)
        elif report_type == 'sales_by_weekday':
            result = ReportsController.get_sales_by_weekday_data(filters)
        elif report_type == 'sales_by_department':
            result = ReportsController.get_sales_by_department_data(filters)
        elif report_type == 'sales_comparison':
            result = ReportsController.get_sales_comparison_data(filters)
        elif report_type == 'top_products':
            result = ReportsController.get_top_products_data(filters)
        elif report_type == 'bottom_products':
            result = ReportsController.get_bottom_products_data(filters)
        elif report_type == 'avg_check':
            result = ReportsController.get_avg_check_data(filters)
        elif report_type == 'check_statistics':
            result = ReportsController.get_check_statistics_data(filters)
        else:
            result = {'success': False, 'error': 'Unknown report type', 'data': []}
        
        # Добавляем информацию о колонках и типе графика
        if result['success']:
            result['columns'] = REPORT_COLUMNS.get(report_type, [])
            result['chart_type'] = REPORT_CHARTS.get(report_type, 'line')
    else:
        result = {'success': False, 'error': 'Report not implemented yet', 'data': []}
    
    return jsonify(result)

@reports_bp.route('/api/filters/<filter_type>')
def get_filter_data(filter_type):
    """API для получения данных фильтров"""
    options = ReportsController.get_filter_options(filter_type)
    return jsonify({'success': True, 'options': options})

@reports_bp.route('/api/<report_id>/export')
def export_report(report_id):
    """Экспорт отчета в Excel"""
    if report_id not in REPORTS_CONFIG:
        return jsonify({'success': False, 'error': 'Report not found'}), 404
    
    # Получаем фильтры из параметров запроса
    filters = {}
    for key, value in request.args.items():
        if key.endswith('[]'):
            key = key[:-2]
            filters[key] = request.args.getlist(f'{key}[]')
        else:
            filters[key] = value
    
    # Получаем данные отчета
    if report_id == 'sales-by-period':
        # Получаем тип отчета
        report_type = filters.get('reportType', 'sales_by_period')
        
        # Вызываем соответствующий метод
        if report_type == 'sales_by_period':
            result = ReportsController.get_sales_by_period_data(filters)
        elif report_type == 'sales_by_hour':
            result = ReportsController.get_sales_by_hour_data(filters)
        elif report_type == 'sales_by_weekday':
            result = ReportsController.get_sales_by_weekday_data(filters)
        elif report_type == 'sales_by_department':
            result = ReportsController.get_sales_by_department_data(filters)
        elif report_type == 'sales_comparison':
            result = ReportsController.get_sales_comparison_data(filters)
        elif report_type == 'top_products':
            result = ReportsController.get_top_products_data(filters)
        elif report_type == 'bottom_products':
            result = ReportsController.get_bottom_products_data(filters)
        elif report_type == 'avg_check':
            result = ReportsController.get_avg_check_data(filters)
        elif report_type == 'check_statistics':
            result = ReportsController.get_check_statistics_data(filters)
        else:
            return jsonify({'success': False, 'error': 'Unknown report type'}), 400
    else:
        return jsonify({'success': False, 'error': 'Export not implemented for this report'}), 400
    
    if not result['success']:
        return jsonify(result), 400
    
    # Создаем DataFrame
    df = pd.DataFrame(result['data'])
    
    if df.empty:
        return jsonify({'success': False, 'error': 'No data to export'}), 400
    
    # Конфигурация колонок
    report_config = REPORTS_CONFIG[report_id]
    if report_id == 'sales-by-period':
        # Для отчета по продажам берем колонки в зависимости от типа
        report_type = filters.get('reportType', 'sales_by_period')
        columns = REPORT_COLUMNS.get(report_type, [])
        column_mapping = {col['key']: col['name'] for col in columns}
    else:
        column_mapping = {col['key']: col['name'] for col in report_config['columns']}
    
    # Переименовываем колонки
    df = df.rename(columns=column_mapping)
    
    # Создаем Excel файл в памяти
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name=report_config['name'], index=False)
        
        # Настраиваем форматирование
        workbook = writer.book
        worksheet = writer.sheets[report_config['name']]
        
        # Формат для денежных сумм
        money_format = workbook.add_format({'num_format': '#,##0.00'})
        
        # Формат для заголовков
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D7E4BC',
            'border': 1
        })
        
        # Применяем форматирование заголовков
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Форматируем денежные колонки
        for col in report_config['columns']:
            if col['type'] == 'money' and col['name'] in df.columns:
                col_idx = df.columns.get_loc(col['name'])
                worksheet.set_column(col_idx, col_idx, None, money_format)
    
    output.seek(0)
    
    filename = f"{report_config['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )