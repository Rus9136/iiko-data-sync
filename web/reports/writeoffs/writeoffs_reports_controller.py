from flask import Blueprint, render_template, request, jsonify, send_file, abort
from datetime import datetime, timedelta
import pandas as pd
import io
import logging
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker
from src.models import Base, Department, Store, Account
from config.config import DATABASE_CONFIG
from web.reports.config.reports_config import REPORTS_CONFIG, FILTERS_CONFIG

logger = logging.getLogger(__name__)

# Подключение к базе данных
db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

# Создаем Blueprint для отчетов по списаниям
writeoffs_reports_bp = Blueprint('writeoffs_reports', __name__)

def get_date_range(preset):
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
    else:
        # По умолчанию - последний месяц
        month_start = today.replace(day=1)
        return month_start, today

def get_filter_options(source):
    """Получение опций для фильтров"""
    session = Session()
    try:
        if source == 'departments':
            departments = session.query(Department).order_by(Department.name).all()
            return [{'value': str(d.id), 'text': d.name} for d in departments]
        elif source == 'stores':
            stores = session.query(Store).order_by(Store.name).all()
            return [{'value': str(s.id), 'text': s.name} for s in stores]
        elif source == 'accounts':
            accounts = session.query(Account).order_by(Account.code, Account.name).all()
            return [{'value': str(a.id), 'text': f"{a.code or ''} {a.name}".strip()} for a in accounts]
        else:
            return []
    finally:
        session.close()

@writeoffs_reports_bp.route('/writeoffs-by-period')
def writeoffs_report():
    """Главная страница отчетов по списаниям"""
    report_id = 'writeoffs-by-period'
    
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
                filters_config[filter_name]['options'] = get_filter_options(
                    filters_config[filter_name]['source']
                )
    
    return render_template('reports/report_view.html',
                         report_config=report_config,
                         filters_config=filters_config)

def get_writeoffs_data_internal(filters):
    """Внутренняя функция для получения данных отчетов по списаниям"""
    try:
        # Получаем параметры
        report_type = filters.get('writeoffReportType', 'writeoffs_by_period')
        date_from = filters.get('dateFrom')
        date_to = filters.get('dateTo')
        store_ids = filters.get('store', [])
        if not isinstance(store_ids, list):
            store_ids = [store_ids] if store_ids != 'all' else []
        account_ids = filters.get('account', [])
        if not isinstance(account_ids, list):
            account_ids = [account_ids] if account_ids != 'all' else []
        
        # Если даты не указаны, используем диапазон по умолчанию
        if not date_from or not date_to:
            date_range = filters.get('dateRange', 'month')
            date_from, date_to = get_date_range(date_range)
            
        # Базовые условия фильтрации
        conditions = ["wd.status IN ('NEW', 'PROCESSED')"]
        params = {}
        
        # Фильтр по датам
        if date_from and date_to:
            conditions.append("wd.date_incoming BETWEEN :date_from AND :date_to")
            params['date_from'] = date_from
            params['date_to'] = date_to
        
        # Фильтр по точкам продаж
        if store_ids and 'all' not in store_ids:
            # Используем IN с приведением к тексту
            placeholders = ', '.join([f':store_{i}' for i in range(len(store_ids))])
            conditions.append(f"wd.store_id::text IN ({placeholders})")
            for i, store_id in enumerate(store_ids):
                params[f'store_{i}'] = str(store_id)
        
        # Фильтр по счетам (причинам списания)
        if account_ids and 'all' not in account_ids:
            # Используем IN с приведением к тексту
            placeholders = ', '.join([f':account_{i}' for i in range(len(account_ids))])
            conditions.append(f"wd.account_id::text IN ({placeholders})")
            for i, account_id in enumerate(account_ids):
                params[f'account_{i}'] = str(account_id)
        
        where_clause = " AND ".join(conditions)
        
        # Выполняем запрос в зависимости от типа отчета
        if report_type == 'writeoffs_by_period':
            data = get_writeoffs_by_period(where_clause, params)
        elif report_type == 'writeoffs_by_reason':
            data = get_writeoffs_by_reason(where_clause, params)
        elif report_type == 'writeoffs_by_product':
            data = get_writeoffs_by_product(where_clause, params)
        else:
            raise ValueError(f"Unknown report type: {report_type}")
        
        # Добавляем информацию о колонках и типе графика
        from web.reports.config.reports_config import REPORT_COLUMNS, REPORT_CHARTS
        
        return {
            'success': True,
            'data': data,
            'reportType': report_type,
            'columns': REPORT_COLUMNS.get(report_type, []),
            'chart_type': REPORT_CHARTS.get(report_type, 'line')
        }
        
    except Exception as e:
        logger.error(f"Error getting writeoffs data: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'data': []
        }

@writeoffs_reports_bp.route('/writeoffs-by-period/data', methods=['GET'])
def get_writeoffs_data():
    """Получение данных для отчетов по списаниям через API"""
    try:
        # Получаем параметры
        filters = {}
        for key, value in request.args.items():
            if key.endswith('[]'):  # Множественные значения
                key = key[:-2]
                filters[key] = request.args.getlist(f'{key}[]')
            else:
                filters[key] = value
        
        # Вызываем внутреннюю функцию
        result = get_writeoffs_data_internal(filters)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting writeoffs data: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def get_writeoffs_by_period(where_clause, params):
    """Отчет: Списания по периодам"""
    query = f"""
    WITH writeoff_data AS (
        SELECT 
            DATE(wd.date_incoming) as date,
            s.name as store,
            SUM(wi.amount * wi.cost) as total_cost,
            SUM(wi.amount) as total_amount,
            COUNT(DISTINCT wd.id) as documents_count,
            COUNT(wi.id) as items_count
        FROM writeoff_documents wd
        JOIN writeoff_items wi ON wd.id = wi.document_id
        JOIN stores s ON wd.store_id = s.id
        WHERE {where_clause}
        GROUP BY DATE(wd.date_incoming), s.name
        ORDER BY date DESC, store
    )
    SELECT 
        date,
        store,
        total_cost,
        total_amount,
        documents_count,
        items_count
    FROM writeoff_data
    """
    
    session = Session()
    try:
        result = session.execute(text(query), params)
        
        data = []
        for row in result:
            data.append({
                'date': row.date.strftime('%Y-%m-%d') if row.date else '',
                'store': row.store,
                'total_cost': float(row.total_cost) if row.total_cost else 0,
                'total_amount': float(row.total_amount) if row.total_amount else 0,
                'documents_count': row.documents_count,
                'items_count': row.items_count
            })
        
        return data
    finally:
        session.close()

def get_writeoffs_by_reason(where_clause, params):
    """Отчет: Списания по причинам (счетам)"""
    query = f"""
    WITH writeoff_data AS (
        SELECT 
            a.code as account_code,
            a.name as account_name,
            SUM(wi.amount * wi.cost) as total_cost,
            SUM(wi.amount) as total_amount,
            COUNT(DISTINCT wd.id) as documents_count
        FROM writeoff_documents wd
        JOIN writeoff_items wi ON wd.id = wi.document_id
        JOIN accounts a ON wd.account_id = a.id
        WHERE {where_clause}
        GROUP BY a.code, a.name
    ),
    total_sum AS (
        SELECT SUM(total_cost) as grand_total
        FROM writeoff_data
    )
    SELECT 
        wd.account_code,
        wd.account_name,
        wd.total_cost,
        wd.total_amount,
        wd.documents_count,
        CASE 
            WHEN ts.grand_total > 0 THEN (wd.total_cost / ts.grand_total * 100)
            ELSE 0
        END as percentage
    FROM writeoff_data wd
    CROSS JOIN total_sum ts
    ORDER BY wd.total_cost DESC
    """
    
    session = Session()
    try:
        result = session.execute(text(query), params)
        
        data = []
        for row in result:
            data.append({
                'account_code': row.account_code,
                'account_name': row.account_name,
                'total_cost': float(row.total_cost) if row.total_cost else 0,
                'total_amount': float(row.total_amount) if row.total_amount else 0,
                'documents_count': row.documents_count,
                'percentage': float(row.percentage) if row.percentage else 0
            })
        
        return data
    finally:
        session.close()

def get_writeoffs_by_product(where_clause, params):
    """Отчет: Топ списываемых товаров"""
    query = f"""
    WITH writeoff_data AS (
        SELECT 
            p.code as product_code,
            p.name as product_name,
            c.name as category,
            SUM(wi.amount) as total_amount,
            SUM(wi.amount * wi.cost) as total_cost
        FROM writeoff_documents wd
        JOIN writeoff_items wi ON wd.id = wi.document_id
        JOIN products p ON wi.product_id = p.id
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE {where_clause}
        GROUP BY p.code, p.name, c.name
    ),
    total_sum AS (
        SELECT SUM(total_cost) as grand_total
        FROM writeoff_data
    )
    SELECT 
        ROW_NUMBER() OVER (ORDER BY wd.total_cost DESC) as rank,
        wd.product_code,
        wd.product_name,
        wd.category,
        wd.total_amount,
        wd.total_cost,
        CASE 
            WHEN ts.grand_total > 0 THEN (wd.total_cost / ts.grand_total * 100)
            ELSE 0
        END as percentage
    FROM writeoff_data wd
    CROSS JOIN total_sum ts
    ORDER BY wd.total_cost DESC
    LIMIT 50
    """
    
    session = Session()
    try:
        result = session.execute(text(query), params)
        
        data = []
        for row in result:
            data.append({
                'rank': row.rank,
                'product_code': row.product_code,
                'product_name': row.product_name,
                'category': row.category or 'Без категории',
                'total_amount': float(row.total_amount) if row.total_amount else 0,
                'total_cost': float(row.total_cost) if row.total_cost else 0,
                'percentage': float(row.percentage) if row.percentage else 0
            })
        
        return data
    finally:
        session.close()

def export_writeoffs_report_internal(args):
    """Внутренняя функция для экспорта отчета по списаниям в Excel"""
    try:
        # Получаем параметры
        filters = {}
        for key, value in args.items():
            filters[key] = value
        
        # Получаем данные отчета
        result = get_writeoffs_data_internal(filters)
        
        if not result['success']:
            raise Exception(result.get('error', 'Unknown error'))
        
        report_type = result['reportType']
        report_data = result['data']
        
        # Создаем DataFrame
        df = pd.DataFrame(report_data)
        
        # Форматируем колонки в зависимости от типа отчета
        if report_type == 'writeoffs_by_period':
            df = df[['date', 'store', 'total_cost', 'total_amount', 'documents_count', 'items_count']]
            df.columns = ['Дата', 'Точка продаж', 'Сумма списаний (₸)', 'Количество', 'Документов', 'Позиций']
        elif report_type == 'writeoffs_by_reason':
            df = df[['account_code', 'account_name', 'total_cost', 'total_amount', 'documents_count', 'percentage']]
            df.columns = ['Код счета', 'Причина списания', 'Сумма списаний (₸)', 'Количество', 'Документов', 'Доля %']
        elif report_type == 'writeoffs_by_product':
            df = df[['rank', 'product_code', 'product_name', 'category', 'total_amount', 'total_cost', 'percentage']]
            df.columns = ['№', 'Код товара', 'Товар', 'Категория', 'Количество', 'Сумма списаний (₸)', 'Доля %']
        
        # Создаем Excel файл
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Отчет', index=False)
            
            # Форматирование
            workbook = writer.book
            worksheet = writer.sheets['Отчет']
            
            # Форматы
            money_format = workbook.add_format({'num_format': '#,##0.00 ₸'})
            percent_format = workbook.add_format({'num_format': '0.00%'})
            number_format = workbook.add_format({'num_format': '#,##0.000'})
            
            # Применяем форматы к колонкам
            for i, col in enumerate(df.columns):
                if 'Сумма' in col or 'чек' in col:
                    worksheet.set_column(i, i, 15, money_format)
                elif 'Доля' in col or '%' in col:
                    worksheet.set_column(i, i, 10, percent_format)
                elif 'Количество' in col:
                    worksheet.set_column(i, i, 12, number_format)
                else:
                    worksheet.set_column(i, i, 20)
        
        output.seek(0)
        
        # Генерируем имя файла
        report_names = {
            'writeoffs_by_period': 'Списания_по_периодам',
            'writeoffs_by_reason': 'Списания_по_причинам',
            'writeoffs_by_product': 'Списания_по_товарам'
        }
        filename = f"{report_names.get(report_type, 'Отчет')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Error exporting writeoffs report: {str(e)}")
        return jsonify({'error': str(e)}), 500

@writeoffs_reports_bp.route('/writeoffs-by-period/export', methods=['GET'])
def export_writeoffs_report():
    """Экспорт отчета по списаниям в Excel через API"""
    try:
        # Получаем данные отчета
        response = get_writeoffs_data()
        data = response.get_json()
        
        if not data['success']:
            raise Exception(data.get('error', 'Unknown error'))
        
        report_type = data['reportType']
        report_data = data['data']
        
        # Создаем DataFrame
        df = pd.DataFrame(report_data)
        
        # Форматируем колонки в зависимости от типа отчета
        if report_type == 'writeoffs_by_period':
            df = df[['date', 'store', 'total_cost', 'total_amount', 'documents_count', 'items_count']]
            df.columns = ['Дата', 'Точка продаж', 'Сумма списаний (₸)', 'Количество', 'Документов', 'Позиций']
        elif report_type == 'writeoffs_by_reason':
            df = df[['account_code', 'account_name', 'total_cost', 'total_amount', 'documents_count', 'percentage']]
            df.columns = ['Код счета', 'Причина списания', 'Сумма списаний (₸)', 'Количество', 'Документов', 'Доля %']
        elif report_type == 'writeoffs_by_product':
            df = df[['rank', 'product_code', 'product_name', 'category', 'total_amount', 'total_cost', 'percentage']]
            df.columns = ['№', 'Код товара', 'Товар', 'Категория', 'Количество', 'Сумма списаний (₸)', 'Доля %']
        
        # Создаем Excel файл
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Отчет', index=False)
            
            # Форматирование
            workbook = writer.book
            worksheet = writer.sheets['Отчет']
            
            # Форматы
            money_format = workbook.add_format({'num_format': '#,##0.00 ₸'})
            percent_format = workbook.add_format({'num_format': '0.00%'})
            number_format = workbook.add_format({'num_format': '#,##0.000'})
            
            # Применяем форматы к колонкам
            for i, col in enumerate(df.columns):
                if 'Сумма' in col or 'чек' in col:
                    worksheet.set_column(i, i, 15, money_format)
                elif 'Доля' in col or '%' in col:
                    worksheet.set_column(i, i, 10, percent_format)
                elif 'Количество' in col:
                    worksheet.set_column(i, i, 12, number_format)
                else:
                    worksheet.set_column(i, i, 20)
        
        output.seek(0)
        
        # Генерируем имя файла
        report_names = {
            'writeoffs_by_period': 'Списания_по_периодам',
            'writeoffs_by_reason': 'Списания_по_причинам',
            'writeoffs_by_product': 'Списания_по_товарам'
        }
        filename = f"{report_names.get(report_type, 'Отчет')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Error exporting writeoffs report: {str(e)}")
        return jsonify({'error': str(e)}), 500