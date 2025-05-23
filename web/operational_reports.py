from datetime import datetime, timedelta
from sqlalchemy import func, text, and_, or_, case, desc, asc
from sqlalchemy.orm import sessionmaker
import calendar

from src.models import Sale, Product, Store, Department

class OperationalReportsGenerator:
    def __init__(self, Session):
        self.Session = Session
        self.session = Session()
        
    def __del__(self):
        if hasattr(self, 'session'):
            self.session.close()
    
    def generate_report(self, report_type, params):
        """Главный метод для генерации отчетов"""
        method_map = {
            'sales_by_period': self.sales_by_period,
            'sales_by_hour': self.sales_by_hour,
            'sales_by_weekday': self.sales_by_weekday,
            'sales_by_department': self.sales_by_department,
            'departments_comparison': self.departments_comparison,
            'top_products': self.top_products,
            'bottom_products': self.bottom_products,
            'average_check': self.average_check,
            'check_analysis': self.check_analysis
        }
        
        if report_type not in method_map:
            return {'status': 'error', 'message': f'Неизвестный тип отчета: {report_type}'}
        
        try:
            return method_map[report_type](params)
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _get_base_query(self, params):
        """Базовый запрос с фильтрами"""
        query = self.session.query(Sale).filter(
            or_(Sale.storned != True, Sale.storned.is_(None)),  # Исключаем сторнированные чеки
            Sale.close_time.isnot(None),  # Только закрытые чеки
            Sale.dish_sum.isnot(None),  # Только записи с суммой
            Sale.dish_sum > 0  # Только положительные суммы
        )
        
        # Фильтр по датам
        if params.get('date_from'):
            query = query.filter(Sale.close_time >= params['date_from'])
        if params.get('date_to'):
            # Добавляем день к конечной дате для включения всего дня
            end_date = datetime.strptime(params['date_to'], '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Sale.close_time < end_date)
        
        # Фильтр по подразделению
        if params.get('department_id'):
            query = query.filter(Sale.department_id == params['department_id'])
        
        return query
    
    def sales_by_period(self, params):
        """Продажи по периодам с динамикой"""
        period_type = params.get('periodType', 'day')
        show_dynamics = params.get('showDynamics', 'true') == 'true'
        
        query = self._get_base_query(params)
        
        # Определяем группировку
        if period_type == 'day':
            date_func = func.date(Sale.close_time)
            date_label = 'Дата'
        elif period_type == 'week':
            date_func = func.date_trunc('week', Sale.close_time)
            date_label = 'Неделя'
        elif period_type == 'month':
            date_func = func.date_trunc('month', Sale.close_time)
            date_label = 'Месяц'
        else:
            date_func = func.date(Sale.close_time)
            date_label = 'Дата'
        
        # Основные агрегаты
        results = query.with_entities(
            date_func.label('period'),
            func.sum(Sale.dish_sum).label('total_revenue'),
            func.count(func.distinct(Sale.order_num)).label('checks_count'),
            func.sum(Sale.dish_amount).label('items_sold'),
            func.avg(Sale.dish_sum).label('avg_item_price'),
            (func.sum(Sale.dish_sum) / func.count(func.distinct(Sale.order_num))).label('avg_check')
        ).group_by(date_func).order_by(date_func).all()
        
        columns = [
            {'key': 'period', 'title': date_label, 'type': 'date'},
            {'key': 'total_revenue', 'title': 'Выручка', 'type': 'number'},
            {'key': 'checks_count', 'title': 'Количество чеков', 'type': 'number'},
            {'key': 'items_sold', 'title': 'Продано позиций', 'type': 'number'},
            {'key': 'avg_check', 'title': 'Средний чек', 'type': 'number'},
            {'key': 'avg_item_price', 'title': 'Средняя цена позиции', 'type': 'number'}
        ]
        
        data = []
        prev_revenue = None
        
        for row in results:
            record = {
                'period': row.period.strftime('%Y-%m-%d') if hasattr(row.period, 'strftime') else str(row.period),
                'total_revenue': float(row.total_revenue or 0),
                'checks_count': int(row.checks_count or 0),
                'items_sold': int(row.items_sold or 0),
                'avg_check': float(row.avg_check or 0),
                'avg_item_price': float(row.avg_item_price or 0)
            }
            
            # Добавляем динамику
            if show_dynamics and prev_revenue is not None:
                if prev_revenue > 0:
                    dynamics = ((record['total_revenue'] - prev_revenue) / prev_revenue) * 100
                    record['dynamics'] = f"{dynamics:.1f}%"
                    columns.append({'key': 'dynamics', 'title': 'Динамика к пред. периоду', 'type': 'text'})
                else:
                    record['dynamics'] = "N/A"
            
            prev_revenue = record['total_revenue']
            data.append(record)
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data)
        }
    
    def sales_by_hour(self, params):
        """Почасовая аналитика продаж"""
        query = self._get_base_query(params)
        
        results = query.with_entities(
            func.extract('hour', Sale.close_time).label('hour'),
            func.sum(Sale.dish_sum).label('total_revenue'),
            func.count(func.distinct(Sale.order_num)).label('checks_count'),
            func.sum(Sale.dish_amount).label('items_sold'),
            (func.sum(Sale.dish_sum) / func.count(func.distinct(Sale.order_num))).label('avg_check')
        ).group_by(func.extract('hour', Sale.close_time))\
         .order_by(func.extract('hour', Sale.close_time)).all()
        
        columns = [
            {'key': 'hour', 'title': 'Час', 'type': 'text'},
            {'key': 'total_revenue', 'title': 'Выручка', 'type': 'number'},
            {'key': 'checks_count', 'title': 'Количество чеков', 'type': 'number'},
            {'key': 'items_sold', 'title': 'Продано позиций', 'type': 'number'},
            {'key': 'avg_check', 'title': 'Средний чек', 'type': 'number'},
            {'key': 'revenue_share', 'title': 'Доля от общей выручки', 'type': 'text'}
        ]
        
        total_revenue = sum(float(row.total_revenue or 0) for row in results)
        
        data = []
        for row in results:
            revenue = float(row.total_revenue or 0)
            revenue_share = (revenue / total_revenue * 100) if total_revenue > 0 else 0
            
            data.append({
                'hour': f"{int(row.hour):02d}:00-{int(row.hour)+1:02d}:00",
                'total_revenue': revenue,
                'checks_count': int(row.checks_count or 0),
                'items_sold': int(row.items_sold or 0),
                'avg_check': float(row.avg_check or 0),
                'revenue_share': f"{revenue_share:.1f}%"
            })
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data)
        }
    
    def sales_by_weekday(self, params):
        """Продажи по дням недели"""
        query = self._get_base_query(params)
        
        results = query.with_entities(
            func.extract('dow', Sale.close_time).label('weekday'),
            func.sum(Sale.dish_sum).label('total_revenue'),
            func.count(func.distinct(Sale.order_num)).label('checks_count'),
            func.sum(Sale.dish_amount).label('items_sold'),
            (func.sum(Sale.dish_sum) / func.count(func.distinct(Sale.order_num))).label('avg_check')
        ).group_by(func.extract('dow', Sale.close_time))\
         .order_by(func.extract('dow', Sale.close_time)).all()
        
        weekdays = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
        
        columns = [
            {'key': 'weekday', 'title': 'День недели', 'type': 'text'},
            {'key': 'total_revenue', 'title': 'Выручка', 'type': 'number'},
            {'key': 'checks_count', 'title': 'Количество чеков', 'type': 'number'},
            {'key': 'items_sold', 'title': 'Продано позиций', 'type': 'number'},
            {'key': 'avg_check', 'title': 'Средний чек', 'type': 'number'},
            {'key': 'revenue_share', 'title': 'Доля от общей выручки', 'type': 'text'}
        ]
        
        total_revenue = sum(float(row.total_revenue or 0) for row in results)
        
        data = []
        for row in results:
            revenue = float(row.total_revenue or 0)
            revenue_share = (revenue / total_revenue * 100) if total_revenue > 0 else 0
            
            data.append({
                'weekday': weekdays[int(row.weekday)],
                'total_revenue': revenue,
                'checks_count': int(row.checks_count or 0),
                'items_sold': int(row.items_sold or 0),
                'avg_check': float(row.avg_check or 0),
                'revenue_share': f"{revenue_share:.1f}%"
            })
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data)
        }
    
    def sales_by_department(self, params):
        """Продажи по торговым точкам"""
        query = self._get_base_query(params)
        
        results = query.with_entities(
            Sale.department.label('department_name'),
            func.sum(Sale.dish_sum).label('total_revenue'),
            func.count(func.distinct(Sale.order_num)).label('checks_count'),
            func.sum(Sale.dish_amount).label('items_sold'),
            (func.sum(Sale.dish_sum) / func.count(func.distinct(Sale.order_num))).label('avg_check')
        ).filter(Sale.department.isnot(None))\
         .group_by(Sale.department)\
         .order_by(desc(func.sum(Sale.dish_sum))).all()
        
        columns = [
            {'key': 'department_name', 'title': 'Торговая точка', 'type': 'text'},
            {'key': 'total_revenue', 'title': 'Выручка', 'type': 'number'},
            {'key': 'checks_count', 'title': 'Количество чеков', 'type': 'number'},
            {'key': 'items_sold', 'title': 'Продано позиций', 'type': 'number'},
            {'key': 'avg_check', 'title': 'Средний чек', 'type': 'number'},
            {'key': 'revenue_share', 'title': 'Доля от общей выручки', 'type': 'text'}
        ]
        
        total_revenue = sum(float(row.total_revenue or 0) for row in results)
        
        data = []
        for row in results:
            revenue = float(row.total_revenue or 0)
            revenue_share = (revenue / total_revenue * 100) if total_revenue > 0 else 0
            
            data.append({
                'department_name': row.department_name or 'Не указано',
                'total_revenue': revenue,
                'checks_count': int(row.checks_count or 0),
                'items_sold': int(row.items_sold or 0),
                'avg_check': float(row.avg_check or 0),
                'revenue_share': f"{revenue_share:.1f}%"
            })
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data)
        }
    
    def departments_comparison(self, params):
        """Сравнительный анализ продаж между точками"""
        metric = params.get('comparisonMetric', 'revenue')
        
        query = self._get_base_query(params)
        
        # Определяем метрики для сравнения
        if metric == 'revenue':
            main_metric = func.sum(Sale.dish_sum)
            metric_title = 'Выручка'
        elif metric == 'checks_count':
            main_metric = func.count(func.distinct(Sale.order_num))
            metric_title = 'Количество чеков'
        elif metric == 'avg_check':
            main_metric = func.sum(Sale.dish_sum) / func.count(func.distinct(Sale.order_num))
            metric_title = 'Средний чек'
        elif metric == 'items_sold':
            main_metric = func.sum(Sale.dish_amount)
            metric_title = 'Продано позиций'
        else:
            main_metric = func.sum(Sale.dish_sum)
            metric_title = 'Выручка'
        
        results = query.with_entities(
            Sale.department.label('department_name'),
            main_metric.label('main_metric'),
            func.sum(Sale.dish_sum).label('total_revenue'),
            func.count(func.distinct(Sale.order_num)).label('checks_count'),
            func.sum(Sale.dish_amount).label('items_sold'),
            (func.sum(Sale.dish_sum) / func.count(func.distinct(Sale.order_num))).label('avg_check')
        ).filter(Sale.department.isnot(None))\
         .group_by(Sale.department)\
         .order_by(desc(main_metric)).all()
        
        columns = [
            {'key': 'rank', 'title': '№', 'type': 'number'},
            {'key': 'department_name', 'title': 'Торговая точка', 'type': 'text'},
            {'key': 'main_metric', 'title': metric_title, 'type': 'number'},
            {'key': 'total_revenue', 'title': 'Выручка', 'type': 'number'},
            {'key': 'checks_count', 'title': 'Чеки', 'type': 'number'},
            {'key': 'avg_check', 'title': 'Средний чек', 'type': 'number'},
            {'key': 'performance_rating', 'title': 'Рейтинг', 'type': 'text'}
        ]
        
        data = []
        total_metric = sum(float(row.main_metric or 0) for row in results)
        
        for rank, row in enumerate(results, 1):
            main_metric_value = float(row.main_metric or 0)
            performance = (main_metric_value / total_metric * 100) if total_metric > 0 else 0
            
            if performance >= 30:
                rating = "Отлично"
            elif performance >= 20:
                rating = "Хорошо"
            elif performance >= 10:
                rating = "Удовлетворительно"
            else:
                rating = "Требует внимания"
            
            data.append({
                'rank': rank,
                'department_name': row.department_name or 'Не указано',
                'main_metric': main_metric_value,
                'total_revenue': float(row.total_revenue or 0),
                'checks_count': int(row.checks_count or 0),
                'avg_check': float(row.avg_check or 0),
                'performance_rating': f"{rating} ({performance:.1f}%)"
            })
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data)
        }
    
    def top_products(self, params):
        """Топ продаваемых товаров"""
        limit = int(params.get('limitRows', 20))
        sort_by = params.get('sortBy', 'revenue')
        
        query = self._get_base_query(params)
        
        # Определяем сортировку
        if sort_by == 'revenue':
            order_field = desc(func.sum(Sale.dish_sum))
            sort_title = 'по выручке'
        elif sort_by == 'quantity':
            order_field = desc(func.sum(Sale.dish_amount))
            sort_title = 'по количеству'
        elif sort_by == 'checks':
            order_field = desc(func.count(func.distinct(Sale.order_num)))
            sort_title = 'по чекам'
        else:
            order_field = desc(func.sum(Sale.dish_sum))
            sort_title = 'по выручке'
        
        results = query.with_entities(
            Sale.dish_name.label('product_name'),
            Sale.dish_code.label('product_code'),
            func.sum(Sale.dish_sum).label('total_revenue'),
            func.sum(Sale.dish_amount).label('quantity_sold'),
            func.count(func.distinct(Sale.order_num)).label('checks_count'),
            case(
                (func.sum(Sale.dish_amount) > 0, func.sum(Sale.dish_sum) / func.sum(Sale.dish_amount)),
                else_=0
            ).label('avg_price')
        ).filter(
            Sale.dish_name.isnot(None),
            Sale.dish_amount.isnot(None),
            Sale.dish_amount > 0
        ).group_by(Sale.dish_name, Sale.dish_code)\
         .order_by(order_field)\
         .limit(limit).all()
        
        columns = [
            {'key': 'rank', 'title': '№', 'type': 'number'},
            {'key': 'product_name', 'title': 'Наименование товара', 'type': 'text'},
            {'key': 'product_code', 'title': 'Код', 'type': 'text'},
            {'key': 'total_revenue', 'title': 'Выручка', 'type': 'number'},
            {'key': 'quantity_sold', 'title': 'Количество', 'type': 'number'},
            {'key': 'checks_count', 'title': 'В чеках', 'type': 'number'},
            {'key': 'avg_price', 'title': 'Средняя цена', 'type': 'number'}
        ]
        
        data = []
        for rank, row in enumerate(results, 1):
            data.append({
                'rank': rank,
                'product_name': row.product_name or 'Не указано',
                'product_code': row.product_code or '',
                'total_revenue': float(row.total_revenue or 0),
                'quantity_sold': int(row.quantity_sold or 0),
                'checks_count': int(row.checks_count or 0),
                'avg_price': float(row.avg_price or 0)
            })
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data),
            'report_subtitle': f'Топ {limit} товаров {sort_title}'
        }
    
    def bottom_products(self, params):
        """Антитоп - товары с минимальными продажами"""
        limit = int(params.get('limitRows', 20))
        sort_by = params.get('sortBy', 'revenue')
        
        query = self._get_base_query(params)
        
        # Определяем сортировку (для антитопа - по возрастанию)
        if sort_by == 'revenue':
            order_field = asc(func.sum(Sale.dish_sum))
            sort_title = 'по выручке'
        elif sort_by == 'quantity':
            order_field = asc(func.sum(Sale.dish_amount))
            sort_title = 'по количеству'
        elif sort_by == 'checks':
            order_field = asc(func.count(func.distinct(Sale.order_num)))
            sort_title = 'по чекам'
        else:
            order_field = asc(func.sum(Sale.dish_sum))
            sort_title = 'по выручке'
        
        results = query.with_entities(
            Sale.dish_name.label('product_name'),
            Sale.dish_code.label('product_code'),
            func.sum(Sale.dish_sum).label('total_revenue'),
            func.sum(Sale.dish_amount).label('quantity_sold'),
            func.count(func.distinct(Sale.order_num)).label('checks_count'),
            case(
                (func.sum(Sale.dish_amount) > 0, func.sum(Sale.dish_sum) / func.sum(Sale.dish_amount)),
                else_=0
            ).label('avg_price')
        ).filter(
            Sale.dish_name.isnot(None),
            Sale.dish_amount.isnot(None),
            Sale.dish_amount > 0
        ).group_by(Sale.dish_name, Sale.dish_code)\
         .order_by(order_field)\
         .limit(limit).all()
        
        columns = [
            {'key': 'rank', 'title': '№', 'type': 'number'},
            {'key': 'product_name', 'title': 'Наименование товара', 'type': 'text'},
            {'key': 'product_code', 'title': 'Код', 'type': 'text'},
            {'key': 'total_revenue', 'title': 'Выручка', 'type': 'number'},
            {'key': 'quantity_sold', 'title': 'Количество', 'type': 'number'},
            {'key': 'checks_count', 'title': 'В чеках', 'type': 'number'},
            {'key': 'avg_price', 'title': 'Средняя цена', 'type': 'number'},
            {'key': 'recommendation', 'title': 'Рекомендация', 'type': 'text'}
        ]
        
        data = []
        for rank, row in enumerate(results, 1):
            revenue = float(row.total_revenue or 0)
            quantity = int(row.quantity_sold or 0)
            
            # Рекомендации на основе данных
            if revenue < 1000 and quantity < 10:
                recommendation = "Рассмотреть исключение"
            elif revenue < 5000:
                recommendation = "Низкий спрос"
            else:
                recommendation = "Под наблюдением"
            
            data.append({
                'rank': rank,
                'product_name': row.product_name or 'Не указано',
                'product_code': row.product_code or '',
                'total_revenue': revenue,
                'quantity_sold': quantity,
                'checks_count': int(row.checks_count or 0),
                'avg_price': float(row.avg_price or 0),
                'recommendation': recommendation
            })
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data),
            'report_subtitle': f'Антитоп {limit} товаров {sort_title}'
        }
    
    def average_check(self, params):
        """Анализ среднего чека"""
        group_by = params.get('avgCheckGroupBy', 'day')
        
        query = self._get_base_query(params)
        
        if group_by == 'day':
            group_field = func.date(Sale.close_time)
            group_label = 'Дата'
        elif group_by == 'department':
            group_field = Sale.department
            group_label = 'Торговая точка'
        elif group_by == 'hour':
            group_field = func.extract('hour', Sale.close_time)
            group_label = 'Час'
        else:
            group_field = func.date(Sale.close_time)
            group_label = 'Дата'
        
        # Добавляем фильтр для департаментов
        if group_by == 'department':
            query = query.filter(Sale.department.isnot(None))
            
        results = query.with_entities(
            group_field.label('group_field'),
            func.sum(Sale.dish_sum).label('total_revenue'),
            func.count(func.distinct(Sale.order_num)).label('checks_count'),
            func.sum(Sale.dish_amount).label('items_sold'),
            (func.sum(Sale.dish_sum) / func.count(func.distinct(Sale.order_num))).label('avg_check'),
            (func.sum(Sale.dish_amount) / func.count(func.distinct(Sale.order_num))).label('avg_items_per_check')
        ).group_by(group_field)\
         .order_by(group_field).all()
        
        columns = [
            {'key': 'group_field', 'title': group_label, 'type': 'text'},
            {'key': 'checks_count', 'title': 'Количество чеков', 'type': 'number'},
            {'key': 'avg_check', 'title': 'Средний чек', 'type': 'number'},
            {'key': 'total_revenue', 'title': 'Общая выручка', 'type': 'number'},
            {'key': 'avg_items_per_check', 'title': 'Позиций в чеке', 'type': 'number'}
        ]
        
        data = []
        for row in results:
            group_value = row.group_field
            if group_by == 'day' and hasattr(group_value, 'strftime'):
                group_value = group_value.strftime('%Y-%m-%d')
            elif group_by == 'hour':
                group_value = f"{int(group_value):02d}:00"
            
            data.append({
                'group_field': str(group_value) if group_value else 'Не указано',
                'checks_count': int(row.checks_count or 0),
                'avg_check': float(row.avg_check or 0),
                'total_revenue': float(row.total_revenue or 0),
                'avg_items_per_check': float(row.avg_items_per_check or 0)
            })
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data)
        }
    
    def check_analysis(self, params):
        """Анализ структуры чеков"""
        query = self._get_base_query(params)
        
        # Анализ по количеству позиций в чеке
        results = query.with_entities(
            Sale.order_num.label('order_num'),
            func.count(Sale.id).label('items_in_check'),
            func.sum(Sale.dish_sum).label('check_total'),
            func.min(Sale.close_time).label('check_time')
        ).group_by(Sale.order_num).all()
        
        # Группируем по количеству позиций
        items_distribution = {}
        total_checks = len(results)
        
        for row in results:
            items_count = int(row.items_in_check or 0)
            if items_count not in items_distribution:
                items_distribution[items_count] = {'count': 0, 'total_revenue': 0}
            items_distribution[items_count]['count'] += 1
            items_distribution[items_count]['total_revenue'] += float(row.check_total or 0)
        
        columns = [
            {'key': 'items_count', 'title': 'Позиций в чеке', 'type': 'number'},
            {'key': 'checks_count', 'title': 'Количество чеков', 'type': 'number'},
            {'key': 'checks_share', 'title': 'Доля чеков', 'type': 'text'},
            {'key': 'total_revenue', 'title': 'Выручка', 'type': 'number'},
            {'key': 'avg_check_value', 'title': 'Средний чек', 'type': 'number'}
        ]
        
        data = []
        for items_count in sorted(items_distribution.keys()):
            dist = items_distribution[items_count]
            checks_count = dist['count']
            total_revenue = dist['total_revenue']
            avg_check = total_revenue / checks_count if checks_count > 0 else 0
            checks_share = (checks_count / total_checks * 100) if total_checks > 0 else 0
            
            data.append({
                'items_count': items_count,
                'checks_count': checks_count,
                'checks_share': f"{checks_share:.1f}%",
                'total_revenue': total_revenue,
                'avg_check_value': avg_check
            })
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data),
            'summary': {
                'total_checks_analyzed': total_checks,
                'avg_items_per_check': sum(k * v['count'] for k, v in items_distribution.items()) / total_checks if total_checks > 0 else 0
            }
        }