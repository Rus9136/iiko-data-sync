from flask import Blueprint, render_template, request, jsonify, abort
from datetime import datetime, timedelta
import json
from sqlalchemy import text
from src.models import Product, Sale, Department, Store, WriteoffDocument, WriteoffItem, Account
from .config.reports_config import REPORTS_CONFIG, FILTERS_CONFIG, REPORT_CATEGORIES
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
        result = ReportsController.get_sales_by_period_data(filters)
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
        result = ReportsController.get_sales_by_period_data(filters)
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