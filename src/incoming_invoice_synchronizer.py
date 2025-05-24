import logging
from datetime import datetime
from typing import Dict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from src.models import IncomingInvoice, IncomingInvoiceItem, SyncLog
from src.api_client import IikoApiClient
import uuid

logger = logging.getLogger(__name__)


class IncomingInvoiceSynchronizer:
    def __init__(self, api_client: IikoApiClient, connection_string: str):
        self.api_client = api_client
        self.engine = create_engine(connection_string)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.counters = {
            'invoices_created': 0,
            'invoices_updated': 0,
            'items_created': 0,
            'items_updated': 0,
            'errors': 0
        }
    
    def sync_incoming_invoices(self, from_date: str, to_date: str, supplier_id: str) -> Dict[str, any]:
        """Синхронизация приходных накладных из IIKO API
        
        Args:
            from_date: Дата начала в формате YYYY-MM-DD
            to_date: Дата окончания в формате YYYY-MM-DD
            supplier_id: ID поставщика
            
        Returns:
            Dict: Статистика синхронизации
        """
        logger.info(f"Начало синхронизации приходных накладных за период {from_date} - {to_date} для поставщика {supplier_id}")
        
        try:
            # Получаем данные из API
            invoices_data = self.api_client.get_incoming_invoices(from_date, to_date, supplier_id)
            
            # Обрабатываем каждую накладную
            for invoice_data in invoices_data:
                try:
                    self._process_invoice(invoice_data)
                except Exception as e:
                    logger.error(f"Ошибка при обработке накладной {invoice_data.get('document_number', 'без номера')}: {e}")
                    self.counters['errors'] += 1
                    continue
            
            # Сохраняем изменения
            self.session.commit()
            
            # Записываем лог синхронизации
            sync_log = SyncLog(
                entity_type='incoming_invoices',
                status='success',
                sync_date=datetime.utcnow(),
                details={
                    'from_date': from_date,
                    'to_date': to_date,
                    'supplier_id': supplier_id,
                    'invoices_created': self.counters['invoices_created'],
                    'invoices_updated': self.counters['invoices_updated'],
                    'items_created': self.counters['items_created'],
                    'items_updated': self.counters['items_updated'],
                    'errors': self.counters['errors']
                }
            )
            self.session.add(sync_log)
            self.session.commit()
            
            logger.info(f"Синхронизация завершена. Создано накладных: {self.counters['invoices_created']}, "
                       f"обновлено: {self.counters['invoices_updated']}, "
                       f"создано позиций: {self.counters['items_created']}, "
                       f"ошибок: {self.counters['errors']}")
            
            return {
                'total': len(invoices_data),
                'invoices_created': self.counters['invoices_created'],
                'invoices_updated': self.counters['invoices_updated'],
                'items_created': self.counters['items_created'],
                'items_updated': self.counters['items_updated'],
                'errors': self.counters['errors']
            }
            
        except Exception as e:
            logger.error(f"Критическая ошибка при синхронизации: {e}")
            self.session.rollback()
            
            # Записываем лог ошибки
            sync_log = SyncLog(
                entity_type='incoming_invoices',
                status='error',
                sync_date=datetime.utcnow(),
                details={
                    'error': str(e),
                    'from_date': from_date,
                    'to_date': to_date,
                    'supplier_id': supplier_id
                }
            )
            self.session.add(sync_log)
            self.session.commit()
            
            raise
        finally:
            self.session.close()
    
    def _process_invoice(self, invoice_data: dict):
        """Обработка одной приходной накладной"""
        invoice_id = uuid.UUID(invoice_data['id'])
        
        # Проверяем существование накладной
        existing_invoice = self.session.query(IncomingInvoice).filter_by(id=invoice_id).first()
        
        if existing_invoice:
            logger.debug(f"Обновление накладной {invoice_data['document_number']}")
            self._update_invoice(existing_invoice, invoice_data)
            self.counters['invoices_updated'] += 1
        else:
            logger.debug(f"Создание новой накладной {invoice_data['document_number']}")
            self._create_invoice(invoice_data)
            self.counters['invoices_created'] += 1
    
    def _create_invoice(self, invoice_data: dict):
        """Создание новой приходной накладной"""
        # Преобразуем строковые даты в объекты datetime/date
        incoming_date = None
        if invoice_data.get('incoming_date'):
            incoming_date = datetime.strptime(invoice_data['incoming_date'], '%Y-%m-%d').date()
        
        due_date = None
        if invoice_data.get('due_date'):
            due_date = datetime.strptime(invoice_data['due_date'], '%Y-%m-%d').date()
        
        date_incoming = None
        if invoice_data.get('date_incoming'):
            # Форматы: 2025-03-19T09:00:00 или 2025-03-19 09:00:00
            date_str = invoice_data['date_incoming'].replace('T', ' ')
            if len(date_str) == 10:  # Только дата
                date_incoming = datetime.strptime(date_str, '%Y-%m-%d')
            else:
                date_incoming = datetime.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')
        
        # Создаем накладную
        invoice = IncomingInvoice(
            id=uuid.UUID(invoice_data['id']),
            transport_invoice_number=invoice_data.get('transport_invoice_number'),
            incoming_document_number=invoice_data.get('incoming_document_number'),
            incoming_date=incoming_date,
            use_default_document_time=invoice_data.get('use_default_document_time', False),
            due_date=due_date,
            supplier_id=uuid.UUID(invoice_data['supplier_id']) if invoice_data.get('supplier_id') else None,
            default_store_id=uuid.UUID(invoice_data['default_store_id']) if invoice_data.get('default_store_id') else None,
            invoice=invoice_data.get('invoice'),
            date_incoming=date_incoming,
            document_number=invoice_data['document_number'],
            comment=invoice_data.get('comment'),
            conception=uuid.UUID(invoice_data['conception']) if invoice_data.get('conception') else None,
            conception_code=invoice_data.get('conception_code'),
            status=invoice_data.get('status'),
            distribution_algorithm=invoice_data.get('distribution_algorithm'),
            synced_at=datetime.utcnow()
        )
        
        self.session.add(invoice)
        
        # Создаем позиции
        for item_data in invoice_data.get('items', []):
            self._create_invoice_item(invoice.id, item_data)
    
    def _update_invoice(self, invoice: IncomingInvoice, invoice_data: dict):
        """Обновление существующей накладной"""
        # Обновляем поля накладной
        invoice.transport_invoice_number = invoice_data.get('transport_invoice_number')
        invoice.incoming_document_number = invoice_data.get('incoming_document_number')
        
        if invoice_data.get('incoming_date'):
            invoice.incoming_date = datetime.strptime(invoice_data['incoming_date'], '%Y-%m-%d').date()
        
        invoice.use_default_document_time = invoice_data.get('use_default_document_time', False)
        
        if invoice_data.get('due_date'):
            invoice.due_date = datetime.strptime(invoice_data['due_date'], '%Y-%m-%d').date()
        else:
            invoice.due_date = None
        
        if invoice_data.get('date_incoming'):
            date_str = invoice_data['date_incoming'].replace('T', ' ')
            if len(date_str) == 10:
                invoice.date_incoming = datetime.strptime(date_str, '%Y-%m-%d')
            else:
                invoice.date_incoming = datetime.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')
        
        invoice.document_number = invoice_data['document_number']
        invoice.comment = invoice_data.get('comment')
        invoice.status = invoice_data.get('status')
        invoice.distribution_algorithm = invoice_data.get('distribution_algorithm')
        invoice.synced_at = datetime.utcnow()
        
        # Удаляем старые позиции
        self.session.query(IncomingInvoiceItem).filter_by(invoice_id=invoice.id).delete()
        
        # Создаем новые позиции
        for item_data in invoice_data.get('items', []):
            self._create_invoice_item(invoice.id, item_data)
    
    def _create_invoice_item(self, invoice_id: uuid.UUID, item_data: dict):
        """Создание позиции накладной"""
        item = IncomingInvoiceItem(
            invoice_id=invoice_id,
            is_additional_expense=item_data.get('is_additional_expense', False),
            actual_amount=item_data.get('actual_amount', 0),
            store_id=uuid.UUID(item_data['store_id']) if item_data.get('store_id') else None,
            code=item_data.get('code'),
            price=item_data.get('price', 0),
            price_without_vat=item_data.get('price_without_vat', 0),
            sum=item_data.get('sum', 0),
            vat_percent=item_data.get('vat_percent', 0),
            vat_sum=item_data.get('vat_sum', 0),
            discount_sum=item_data.get('discount_sum', 0),
            amount_unit=uuid.UUID(item_data['amount_unit']) if item_data.get('amount_unit') else None,
            num=item_data.get('num', 0),
            product_id=uuid.UUID(item_data['product_id']) if item_data.get('product_id') else None,
            product_article=item_data.get('product_article'),
            amount=item_data.get('amount', 0),
            supplier_id=uuid.UUID(item_data['supplier_id']) if item_data.get('supplier_id') else None
        )
        
        self.session.add(item)
        self.counters['items_created'] += 1