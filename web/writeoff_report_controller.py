import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from sqlalchemy import func, text, and_, or_, case, desc, asc, extract
from sqlalchemy.orm import sessionmaker
from flask import request, jsonify, render_template, make_response
import pandas as pd
from io import BytesIO
import logging

from src.models import WriteoffDocument, WriteoffItem, Product, Store, Account, IncomingInvoice, IncomingInvoiceItem

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WriteoffReportsGenerator:
    def __init__(self, Session):
        self.Session = Session
        self.session = Session()
        
    def __del__(self):
        if hasattr(self, 'session'):
            self.session.close()
    
    def generate_report(self, report_type, params):
        """Главный метод для генерации отчетов по списаниям"""
        logger.info(f"=== generate_report called ===")
        logger.info(f"Report type: {report_type}")
        logger.info(f"Params: {params}")
        
        method_map = {
            'writeoffs_by_period': self.writeoffs_by_period,
            'writeoffs_by_store': self.writeoffs_by_store,
            'writeoffs_by_reason': self.writeoffs_by_reason,
            'top_writeoff_products': self.top_writeoff_products,
            'writeoff_percentage': self.writeoff_percentage,
            'financial_losses': self.financial_losses,
            'stores_comparison': self.stores_comparison,
            'writeoffs_dynamics': self.writeoffs_dynamics
        }
        
        logger.info(f"Available report types: {list(method_map.keys())}")
        
        if report_type not in method_map:
            logger.error(f"Unknown report type: {report_type}")
            return {'status': 'error', 'message': f'Неизвестный тип отчета: {report_type}'}
        
        try:
            logger.info(f"Calling method: {method_map[report_type].__name__}")
            result = method_map[report_type](params)
            logger.info(f"Method returned successfully. Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            return result
        except Exception as e:
            logger.error(f"=== Error in generate_report ===")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error message: {str(e)}")
            logger.error(f"Traceback:", exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    def _get_base_query(self, params):
        """Базовый запрос для документов списания с фильтрами"""
        query = self.session.query(WriteoffDocument).join(
            WriteoffItem, WriteoffDocument.id == WriteoffItem.document_id
        ).filter(
            WriteoffDocument.status.in_(['NEW', 'PROCESSED'])  # Только активные документы
        )
        
        # Фильтр по датам
        if params.get('date_from'):
            date_from = datetime.strptime(params['date_from'], '%Y-%m-%d')
            query = query.filter(WriteoffDocument.date_incoming >= date_from)
        if params.get('date_to'):
            date_to = datetime.strptime(params['date_to'], '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(WriteoffDocument.date_incoming < date_to)
        
        # Фильтр по складу
        if params.get('store_id'):
            query = query.filter(WriteoffDocument.store_id == params['store_id'])
        
        # Фильтр по счету (причине списания)
        if params.get('account_id'):
            query = query.filter(WriteoffDocument.account_id == params['account_id'])
        
        return query
    
    def writeoffs_by_period(self, params):
        """Списания по периодам с динамикой"""
        logger.info("=== writeoffs_by_period called ===")
        logger.info(f"Params: {params}")
        
        period_type = params.get('periodType', 'day')
        show_dynamics = params.get('showDynamics', 'true') == 'true'
        logger.info(f"Period type: {period_type}, Show dynamics: {show_dynamics}")
        
        # Определяем группировку по периоду
        if period_type == 'day':
            date_func = func.date(WriteoffDocument.date_incoming)
            date_label = 'Дата'
        elif period_type == 'week':
            date_func = func.date_trunc('week', WriteoffDocument.date_incoming)
            date_label = 'Неделя'
        elif period_type == 'month':
            date_func = func.date_trunc('month', WriteoffDocument.date_incoming)
            date_label = 'Месяц'
        else:
            date_func = func.date(WriteoffDocument.date_incoming)
            date_label = 'Дата'
        
        # Получаем агрегированные данные
        query = self._get_base_query(params)
        results = query.with_entities(
            date_func.label('period'),
            func.count(func.distinct(WriteoffDocument.id)).label('docs_count'),
            func.sum(WriteoffItem.amount * WriteoffItem.amount_factor).label('total_quantity'),
            func.sum(WriteoffItem.cost).label('total_cost'),
            func.count(func.distinct(WriteoffItem.product_id)).label('unique_products')
        ).group_by(date_func).order_by(date_func).all()
        
        columns = [
            {'key': 'period', 'title': date_label, 'type': 'date'},
            {'key': 'docs_count', 'title': 'Документов', 'type': 'number'},
            {'key': 'total_quantity', 'title': 'Количество', 'type': 'number'},
            {'key': 'total_cost', 'title': 'Сумма списания', 'type': 'number'},
            {'key': 'unique_products', 'title': 'Уникальных товаров', 'type': 'number'},
            {'key': 'avg_cost_per_item', 'title': 'Средняя стоимость', 'type': 'number'}
        ]
        
        if show_dynamics:
            columns.append({'key': 'dynamics', 'title': 'Динамика', 'type': 'text'})
        
        data = []
        prev_cost = None
        
        for row in results:
            total_cost = float(row.total_cost or 0)
            total_quantity = float(row.total_quantity or 0)
            avg_cost = total_cost / total_quantity if total_quantity > 0 else 0
            
            record = {
                'period': row.period.strftime('%Y-%m-%d') if hasattr(row.period, 'strftime') else str(row.period),
                'docs_count': int(row.docs_count or 0),
                'total_quantity': total_quantity,
                'total_cost': total_cost,
                'unique_products': int(row.unique_products or 0),
                'avg_cost_per_item': avg_cost
            }
            
            # Добавляем динамику
            if show_dynamics and prev_cost is not None:
                if prev_cost > 0:
                    dynamics = ((total_cost - prev_cost) / prev_cost) * 100
                    record['dynamics'] = f"{dynamics:+.1f}%"
                else:
                    record['dynamics'] = "N/A"
            
            prev_cost = total_cost
            data.append(record)
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data)
        }
    
    def writeoffs_by_store(self, params):
        """Списания по складам/точкам"""
        query = self._get_base_query(params)
        
        results = query.join(
            Store, WriteoffDocument.store_id == Store.id
        ).with_entities(
            Store.name.label('store_name'),
            Store.id.label('store_id'),
            func.count(func.distinct(WriteoffDocument.id)).label('docs_count'),
            func.sum(WriteoffItem.amount * WriteoffItem.amount_factor).label('total_quantity'),
            func.sum(WriteoffItem.cost).label('total_cost'),
            func.count(func.distinct(WriteoffItem.product_id)).label('unique_products')
        ).group_by(Store.id, Store.name).order_by(desc(func.sum(WriteoffItem.cost))).all()
        
        columns = [
            {'key': 'store_name', 'title': 'Склад/Точка', 'type': 'text'},
            {'key': 'docs_count', 'title': 'Документов', 'type': 'number'},
            {'key': 'total_quantity', 'title': 'Количество', 'type': 'number'},
            {'key': 'total_cost', 'title': 'Сумма списания', 'type': 'number'},
            {'key': 'unique_products', 'title': 'Уникальных товаров', 'type': 'number'},
            {'key': 'cost_share', 'title': 'Доля от общей суммы', 'type': 'text'}
        ]
        
        total_cost_all = sum(float(row.total_cost or 0) for row in results)
        
        data = []
        for row in results:
            total_cost = float(row.total_cost or 0)
            cost_share = (total_cost / total_cost_all * 100) if total_cost_all > 0 else 0
            
            data.append({
                'store_name': row.store_name or 'Не указан',
                'store_id': str(row.store_id),
                'docs_count': int(row.docs_count or 0),
                'total_quantity': float(row.total_quantity or 0),
                'total_cost': total_cost,
                'unique_products': int(row.unique_products or 0),
                'cost_share': f"{cost_share:.1f}%"
            })
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data)
        }
    
    def writeoffs_by_reason(self, params):
        """Списания по причинам (счетам)"""
        query = self._get_base_query(params)
        
        results = query.join(
            Account, WriteoffDocument.account_id == Account.id, isouter=True
        ).with_entities(
            Account.name.label('account_name'),
            Account.code.label('account_code'),
            func.count(func.distinct(WriteoffDocument.id)).label('docs_count'),
            func.sum(WriteoffItem.amount * WriteoffItem.amount_factor).label('total_quantity'),
            func.sum(WriteoffItem.cost).label('total_cost'),
            func.count(func.distinct(WriteoffItem.product_id)).label('unique_products')
        ).group_by(Account.id, Account.name, Account.code).order_by(desc(func.sum(WriteoffItem.cost))).all()
        
        columns = [
            {'key': 'account_name', 'title': 'Причина списания', 'type': 'text'},
            {'key': 'account_code', 'title': 'Код счета', 'type': 'text'},
            {'key': 'docs_count', 'title': 'Документов', 'type': 'number'},
            {'key': 'total_quantity', 'title': 'Количество', 'type': 'number'},
            {'key': 'total_cost', 'title': 'Сумма списания', 'type': 'number'},
            {'key': 'cost_share', 'title': 'Доля от общей суммы', 'type': 'text'}
        ]
        
        total_cost_all = sum(float(row.total_cost or 0) for row in results)
        
        data = []
        for row in results:
            total_cost = float(row.total_cost or 0)
            cost_share = (total_cost / total_cost_all * 100) if total_cost_all > 0 else 0
            
            data.append({
                'account_name': row.account_name or 'Не указана',
                'account_code': row.account_code or '-',
                'docs_count': int(row.docs_count or 0),
                'total_quantity': float(row.total_quantity or 0),
                'total_cost': total_cost,
                'cost_share': f"{cost_share:.1f}%"
            })
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data)
        }
    
    def top_writeoff_products(self, params):
        """Топ списываемых товаров"""
        limit = int(params.get('limitRows', 20))
        sort_by = params.get('sortBy', 'cost')
        
        query = self._get_base_query(params)
        
        # Определяем сортировку
        if sort_by == 'cost':
            order_field = desc(func.sum(WriteoffItem.cost))
            sort_title = 'по сумме'
        elif sort_by == 'quantity':
            order_field = desc(func.sum(WriteoffItem.amount * WriteoffItem.amount_factor))
            sort_title = 'по количеству'
        elif sort_by == 'frequency':
            order_field = desc(func.count(func.distinct(WriteoffDocument.id)))
            sort_title = 'по частоте'
        else:
            order_field = desc(func.sum(WriteoffItem.cost))
            sort_title = 'по сумме'
        
        results = query.join(
            Product, WriteoffItem.product_id == Product.id
        ).with_entities(
            Product.name.label('product_name'),
            Product.code.label('product_code'),
            func.sum(WriteoffItem.amount * WriteoffItem.amount_factor).label('total_quantity'),
            func.sum(WriteoffItem.cost).label('total_cost'),
            func.count(func.distinct(WriteoffDocument.id)).label('docs_count'),
            case(
                (func.sum(WriteoffItem.amount * WriteoffItem.amount_factor) > 0, 
                 func.sum(WriteoffItem.cost) / func.sum(WriteoffItem.amount * WriteoffItem.amount_factor)),
                else_=0
            ).label('avg_cost')
        ).group_by(Product.id, Product.name, Product.code)\
         .order_by(order_field)\
         .limit(limit).all()
        
        columns = [
            {'key': 'rank', 'title': '№', 'type': 'number'},
            {'key': 'product_name', 'title': 'Наименование товара', 'type': 'text'},
            {'key': 'product_code', 'title': 'Код', 'type': 'text'},
            {'key': 'total_quantity', 'title': 'Количество', 'type': 'number'},
            {'key': 'total_cost', 'title': 'Сумма списания', 'type': 'number'},
            {'key': 'docs_count', 'title': 'В документах', 'type': 'number'},
            {'key': 'avg_cost', 'title': 'Средняя цена', 'type': 'number'}
        ]
        
        data = []
        for rank, row in enumerate(results, 1):
            data.append({
                'rank': rank,
                'product_name': row.product_name or 'Не указано',
                'product_code': row.product_code or '',
                'total_quantity': float(row.total_quantity or 0),
                'total_cost': float(row.total_cost or 0),
                'docs_count': int(row.docs_count or 0),
                'avg_cost': float(row.avg_cost or 0)
            })
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data),
            'report_subtitle': f'Топ {limit} товаров {sort_title}'
        }
    
    def writeoff_percentage(self, params):
        """Процент списаний от поступлений"""
        # Получаем списания
        writeoffs_query = self._get_base_query(params)
        
        # Группировка по периодам
        period_type = params.get('periodType', 'month')
        if period_type == 'day':
            date_func = func.date
        elif period_type == 'week':
            date_func = lambda x: func.date_trunc('week', x)
        else:  # month
            date_func = lambda x: func.date_trunc('month', x)
        
        # Агрегируем списания по периодам и товарам
        writeoffs = writeoffs_query.join(
            Product, WriteoffItem.product_id == Product.id
        ).with_entities(
            date_func(WriteoffDocument.date_incoming).label('period'),
            Product.id.label('product_id'),
            Product.name.label('product_name'),
            Product.code.label('product_code'),
            func.sum(WriteoffItem.amount * WriteoffItem.amount_factor).label('writeoff_quantity'),
            func.sum(WriteoffItem.cost).label('writeoff_cost')
        ).group_by(
            date_func(WriteoffDocument.date_incoming),
            Product.id,
            Product.name,
            Product.code
        ).all()
        
        # Получаем поступления за тот же период
        invoices_query = self.session.query(IncomingInvoice).join(
            IncomingInvoiceItem, IncomingInvoice.id == IncomingInvoiceItem.invoice_id
        ).filter(
            IncomingInvoice.status.in_(['NEW', 'PROCESSED'])
        )
        
        # Применяем фильтры дат
        if params.get('date_from'):
            date_from = datetime.strptime(params['date_from'], '%Y-%m-%d')
            invoices_query = invoices_query.filter(IncomingInvoice.date_incoming >= date_from)
        if params.get('date_to'):
            date_to = datetime.strptime(params['date_to'], '%Y-%m-%d') + timedelta(days=1)
            invoices_query = invoices_query.filter(IncomingInvoice.date_incoming < date_to)
        
        # Агрегируем поступления
        invoices = invoices_query.with_entities(
            date_func(IncomingInvoice.date_incoming).label('period'),
            IncomingInvoiceItem.product_id.label('product_id'),
            func.sum(IncomingInvoiceItem.amount).label('invoice_quantity'),
            func.sum(IncomingInvoiceItem.sum).label('invoice_sum')
        ).group_by(
            date_func(IncomingInvoice.date_incoming),
            IncomingInvoiceItem.product_id
        ).all()
        
        # Объединяем данные
        writeoff_dict = {}
        for w in writeoffs:
            key = (str(w.period), str(w.product_id))
            writeoff_dict[key] = {
                'product_name': w.product_name,
                'product_code': w.product_code,
                'writeoff_quantity': float(w.writeoff_quantity or 0),
                'writeoff_cost': float(w.writeoff_cost or 0)
            }
        
        invoice_dict = {}
        for i in invoices:
            key = (str(i.period), str(i.product_id))
            invoice_dict[key] = {
                'invoice_quantity': float(i.invoice_quantity or 0),
                'invoice_sum': float(i.invoice_sum or 0)
            }
        
        # Собираем результаты
        results = {}
        for key in set(writeoff_dict.keys()) | set(invoice_dict.keys()):
            period, product_id = key
            if period not in results:
                results[period] = {
                    'period': period,
                    'total_writeoff_cost': 0,
                    'total_invoice_sum': 0,
                    'products': []
                }
            
            writeoff = writeoff_dict.get(key, {})
            invoice = invoice_dict.get(key, {})
            
            writeoff_cost = writeoff.get('writeoff_cost', 0)
            invoice_sum = invoice.get('invoice_sum', 0)
            
            results[period]['total_writeoff_cost'] += writeoff_cost
            results[period]['total_invoice_sum'] += invoice_sum
            
            if writeoff_cost > 0 or invoice_sum > 0:
                percentage = (writeoff_cost / invoice_sum * 100) if invoice_sum > 0 else 0
                results[period]['products'].append({
                    'product_name': writeoff.get('product_name', 'Неизвестный товар'),
                    'product_code': writeoff.get('product_code', ''),
                    'writeoff_quantity': writeoff.get('writeoff_quantity', 0),
                    'invoice_quantity': invoice.get('invoice_quantity', 0),
                    'writeoff_cost': writeoff_cost,
                    'invoice_sum': invoice_sum,
                    'percentage': percentage
                })
        
        columns = [
            {'key': 'period', 'title': 'Период', 'type': 'date'},
            {'key': 'total_writeoff_cost', 'title': 'Сумма списаний', 'type': 'number'},
            {'key': 'total_invoice_sum', 'title': 'Сумма поступлений', 'type': 'number'},
            {'key': 'percentage', 'title': '% списаний', 'type': 'text'},
            {'key': 'status', 'title': 'Статус', 'type': 'text'}
        ]
        
        data = []
        for period in sorted(results.keys()):
            result = results[period]
            total_percentage = (result['total_writeoff_cost'] / result['total_invoice_sum'] * 100) \
                if result['total_invoice_sum'] > 0 else 0
            
            # Определяем статус
            if total_percentage > 5:
                status = "Критический"
            elif total_percentage > 3:
                status = "Высокий"
            elif total_percentage > 1:
                status = "Нормальный"
            else:
                status = "Низкий"
            
            data.append({
                'period': period,
                'total_writeoff_cost': result['total_writeoff_cost'],
                'total_invoice_sum': result['total_invoice_sum'],
                'percentage': f"{total_percentage:.2f}%",
                'status': status,
                'products': result['products']  # Детализация по товарам
            })
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data)
        }
    
    def financial_losses(self, params):
        """Финансовые потери от списаний"""
        query = self._get_base_query(params)
        
        # Получаем общие потери
        total_losses = query.with_entities(
            func.sum(WriteoffItem.cost).label('total_cost'),
            func.sum(WriteoffItem.amount * WriteoffItem.amount_factor).label('total_quantity'),
            func.count(func.distinct(WriteoffDocument.id)).label('docs_count')
        ).first()
        
        # Потери по категориям товаров
        category_losses = query.join(
            Product, WriteoffItem.product_id == Product.id
        ).join(
            Store, WriteoffDocument.store_id == Store.id, isouter=True
        ).with_entities(
            Store.name.label('store_name'),
            func.sum(WriteoffItem.cost).label('loss_amount'),
            func.count(func.distinct(WriteoffDocument.id)).label('docs_count')
        ).group_by(Store.id, Store.name).order_by(desc(func.sum(WriteoffItem.cost))).all()
        
        # Потери по месяцам
        monthly_losses = query.with_entities(
            func.date_trunc('month', WriteoffDocument.date_incoming).label('month'),
            func.sum(WriteoffItem.cost).label('loss_amount')
        ).group_by(func.date_trunc('month', WriteoffDocument.date_incoming))\
         .order_by(func.date_trunc('month', WriteoffDocument.date_incoming)).all()
        
        # Средние потери
        avg_loss_per_doc = float(total_losses.total_cost or 0) / int(total_losses.docs_count or 1)
        
        columns = [
            {'key': 'metric', 'title': 'Показатель', 'type': 'text'},
            {'key': 'value', 'title': 'Значение', 'type': 'text'}
        ]
        
        data = [
            {'metric': 'Общая сумма потерь', 'value': f"{float(total_losses.total_cost or 0):,.2f} ₸"},
            {'metric': 'Количество документов', 'value': str(int(total_losses.docs_count or 0))},
            {'metric': 'Общее количество списанного', 'value': f"{float(total_losses.total_quantity or 0):,.3f}"},
            {'metric': 'Средние потери на документ', 'value': f"{avg_loss_per_doc:,.2f} ₸"}
        ]
        
        # Добавляем топ-3 склада по потерям
        for i, store in enumerate(category_losses[:3], 1):
            data.append({
                'metric': f'Топ-{i} склад по потерям',
                'value': f"{store.store_name}: {float(store.loss_amount or 0):,.2f} ₸"
            })
        
        # Добавляем динамику по месяцам
        if monthly_losses:
            prev_month_loss = None
            for month_data in monthly_losses[-3:]:  # Последние 3 месяца
                month_loss = float(month_data.loss_amount or 0)
                month_str = month_data.month.strftime('%B %Y')
                
                if prev_month_loss is not None and prev_month_loss > 0:
                    change = ((month_loss - prev_month_loss) / prev_month_loss) * 100
                    data.append({
                        'metric': f'Потери за {month_str}',
                        'value': f"{month_loss:,.2f} ₸ ({change:+.1f}%)"
                    })
                else:
                    data.append({
                        'metric': f'Потери за {month_str}',
                        'value': f"{month_loss:,.2f} ₸"
                    })
                
                prev_month_loss = month_loss
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data),
            'summary': {
                'total_losses': float(total_losses.total_cost or 0),
                'docs_count': int(total_losses.docs_count or 0),
                'category_breakdown': [
                    {
                        'store': cl.store_name or 'Не указан',
                        'amount': float(cl.loss_amount or 0),
                        'docs': int(cl.docs_count or 0)
                    } for cl in category_losses
                ]
            }
        }
    
    def stores_comparison(self, params):
        """Сравнение списаний между складами"""
        metric = params.get('comparisonMetric', 'cost')
        
        query = self._get_base_query(params)
        
        # Определяем метрику для сравнения
        if metric == 'cost':
            main_metric = func.sum(WriteoffItem.cost)
            metric_title = 'Сумма списаний'
        elif metric == 'quantity':
            main_metric = func.sum(WriteoffItem.amount * WriteoffItem.amount_factor)
            metric_title = 'Количество списаний'
        elif metric == 'docs_count':
            main_metric = func.count(func.distinct(WriteoffDocument.id))
            metric_title = 'Количество документов'
        elif metric == 'avg_cost':
            main_metric = func.sum(WriteoffItem.cost) / func.count(func.distinct(WriteoffDocument.id))
            metric_title = 'Средняя сумма на документ'
        else:
            main_metric = func.sum(WriteoffItem.cost)
            metric_title = 'Сумма списаний'
        
        results = query.join(
            Store, WriteoffDocument.store_id == Store.id
        ).with_entities(
            Store.name.label('store_name'),
            Store.type.label('store_type'),
            main_metric.label('main_metric'),
            func.sum(WriteoffItem.cost).label('total_cost'),
            func.sum(WriteoffItem.amount * WriteoffItem.amount_factor).label('total_quantity'),
            func.count(func.distinct(WriteoffDocument.id)).label('docs_count'),
            func.count(func.distinct(WriteoffItem.product_id)).label('unique_products')
        ).group_by(Store.id, Store.name, Store.type)\
         .order_by(desc(main_metric)).all()
        
        columns = [
            {'key': 'rank', 'title': '№', 'type': 'number'},
            {'key': 'store_name', 'title': 'Склад/Точка', 'type': 'text'},
            {'key': 'store_type', 'title': 'Тип', 'type': 'text'},
            {'key': 'main_metric', 'title': metric_title, 'type': 'number'},
            {'key': 'total_cost', 'title': 'Сумма списаний', 'type': 'number'},
            {'key': 'docs_count', 'title': 'Документов', 'type': 'number'},
            {'key': 'unique_products', 'title': 'Товаров', 'type': 'number'},
            {'key': 'performance_rating', 'title': 'Рейтинг', 'type': 'text'}
        ]
        
        data = []
        total_metric = sum(float(row.main_metric or 0) for row in results)
        
        for rank, row in enumerate(results, 1):
            main_metric_value = float(row.main_metric or 0)
            performance = (main_metric_value / total_metric * 100) if total_metric > 0 else 0
            
            # Определяем рейтинг (обратный для списаний - меньше лучше)
            if performance <= 10:
                rating = "Отлично"
            elif performance <= 20:
                rating = "Хорошо"
            elif performance <= 30:
                rating = "Удовлетворительно"
            else:
                rating = "Требует внимания"
            
            store_type_str = str(row.store_type).split('.')[-1] if row.store_type else 'Не указан'
            
            data.append({
                'rank': rank,
                'store_name': row.store_name or 'Не указан',
                'store_type': store_type_str,
                'main_metric': main_metric_value,
                'total_cost': float(row.total_cost or 0),
                'total_quantity': float(row.total_quantity or 0),
                'docs_count': int(row.docs_count or 0),
                'unique_products': int(row.unique_products or 0),
                'performance_rating': f"{rating} ({performance:.1f}%)"
            })
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data)
        }
    
    def writeoffs_dynamics(self, params):
        """Динамика списаний по периодам"""
        period_type = params.get('periodType', 'month')
        
        # Определяем группировку
        if period_type == 'day':
            date_func = func.date(WriteoffDocument.date_incoming)
            date_label = 'День'
        elif period_type == 'week':
            # Группировка по неделям с началом недели
            date_func = func.date_trunc('week', WriteoffDocument.date_incoming)
            date_label = 'Неделя'
        elif period_type == 'month':
            date_func = func.date_trunc('month', WriteoffDocument.date_incoming)
            date_label = 'Месяц'
        elif period_type == 'quarter':
            date_func = func.date_trunc('quarter', WriteoffDocument.date_incoming)
            date_label = 'Квартал'
        else:
            date_func = func.date_trunc('month', WriteoffDocument.date_incoming)
            date_label = 'Месяц'
        
        query = self._get_base_query(params)
        
        # Получаем данные с группировкой
        results = query.with_entities(
            date_func.label('period'),
            func.count(func.distinct(WriteoffDocument.id)).label('docs_count'),
            func.sum(WriteoffItem.amount * WriteoffItem.amount_factor).label('total_quantity'),
            func.sum(WriteoffItem.cost).label('total_cost'),
            func.count(func.distinct(WriteoffItem.product_id)).label('unique_products'),
            func.avg(WriteoffItem.cost).label('avg_item_cost')
        ).group_by(date_func).order_by(date_func).all()
        
        columns = [
            {'key': 'period', 'title': date_label, 'type': 'date'},
            {'key': 'docs_count', 'title': 'Документов', 'type': 'number'},
            {'key': 'total_cost', 'title': 'Сумма списаний', 'type': 'number'},
            {'key': 'total_quantity', 'title': 'Количество', 'type': 'number'},
            {'key': 'unique_products', 'title': 'Уникальных товаров', 'type': 'number'},
            {'key': 'avg_doc_cost', 'title': 'Средняя сумма документа', 'type': 'number'},
            {'key': 'cost_change', 'title': 'Изменение суммы', 'type': 'text'},
            {'key': 'quantity_change', 'title': 'Изменение количества', 'type': 'text'}
        ]
        
        data = []
        prev_cost = None
        prev_quantity = None
        
        for row in results:
            total_cost = float(row.total_cost or 0)
            total_quantity = float(row.total_quantity or 0)
            docs_count = int(row.docs_count or 0)
            avg_doc_cost = total_cost / docs_count if docs_count > 0 else 0
            
            record = {
                'period': row.period.strftime('%Y-%m-%d') if hasattr(row.period, 'strftime') else str(row.period),
                'docs_count': docs_count,
                'total_cost': total_cost,
                'total_quantity': total_quantity,
                'unique_products': int(row.unique_products or 0),
                'avg_doc_cost': avg_doc_cost
            }
            
            # Рассчитываем изменения
            if prev_cost is not None:
                cost_change = ((total_cost - prev_cost) / prev_cost * 100) if prev_cost > 0 else 0
                record['cost_change'] = f"{cost_change:+.1f}%"
            else:
                record['cost_change'] = '-'
            
            if prev_quantity is not None:
                quantity_change = ((total_quantity - prev_quantity) / prev_quantity * 100) if prev_quantity > 0 else 0
                record['quantity_change'] = f"{quantity_change:+.1f}%"
            else:
                record['quantity_change'] = '-'
            
            prev_cost = total_cost
            prev_quantity = total_quantity
            data.append(record)
        
        # Добавляем итоговую строку
        if data:
            total_cost_sum = sum(d['total_cost'] for d in data)
            total_quantity_sum = sum(d['total_quantity'] for d in data)
            total_docs = sum(d['docs_count'] for d in data)
            
            data.append({
                'period': 'ИТОГО',
                'docs_count': total_docs,
                'total_cost': total_cost_sum,
                'total_quantity': total_quantity_sum,
                'unique_products': '-',
                'avg_doc_cost': total_cost_sum / total_docs if total_docs > 0 else 0,
                'cost_change': '-',
                'quantity_change': '-'
            })
        
        return {
            'status': 'success',
            'data': data,
            'columns': columns,
            'total_records': len(data) - 1 if data else 0  # Не считаем итоговую строку
        }
    
    def export_to_excel(self, report_type, params):
        """Экспорт отчета в Excel"""
        # Получаем данные отчета
        report_data = self.generate_report(report_type, params)
        
        if report_data['status'] != 'success':
            return None
        
        # Создаем DataFrame
        df = pd.DataFrame(report_data['data'])
        
        # Создаем Excel файл в памяти
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Отчет по списаниям', index=False)
            
            # Получаем объекты для форматирования
            workbook = writer.book
            worksheet = writer.sheets['Отчет по списаниям']
            
            # Форматирование заголовков
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#D7E4BD',
                'border': 1
            })
            
            # Применяем форматирование к заголовкам
            for col_num, column in enumerate(report_data['columns']):
                worksheet.write(0, col_num, column['title'], header_format)
                
                # Автоподбор ширины колонок
                column_len = df[column['key']].astype(str).str.len().max() if column['key'] in df.columns else 10
                column_len = max(column_len, len(column['title'])) + 2
                worksheet.set_column(col_num, col_num, column_len)
        
        output.seek(0)
        return output