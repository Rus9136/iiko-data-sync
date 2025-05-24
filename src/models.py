from sqlalchemy import create_engine, Column, String, Boolean, DateTime, ForeignKey, Integer, JSON, UniqueConstraint, Enum, Float, Date, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import uuid
import enum

Base = declarative_base()

class StoreType(enum.Enum):
    STORE = "STORE"  # Склад
    PRODUCTION = "PRODUCTION"  # Производство
    OTHER = "OTHER"  # Другое

class ReceiptStatus(enum.Enum):
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    PROCESSING = "PROCESSING"

class SaleStatus(enum.Enum):
    NOT_DELETED = "NOT_DELETED"
    DELETED = "DELETED"

class WriteoffDocumentStatus(enum.Enum):
    NEW = "NEW"
    PROCESSED = "PROCESSED"
    CANCELLED = "CANCELLED"

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    deleted = Column(Boolean, default=False, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
    num = Column(String(50), nullable=True)
    code = Column(String(50), nullable=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey('products.id'), nullable=True)
    tax_category_id = Column(UUID(as_uuid=True), ForeignKey('categories.id'), nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey('categories.id'), nullable=True)
    accounting_category_id = Column(UUID(as_uuid=True), ForeignKey('categories.id'), nullable=True)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = Column(DateTime, default=datetime.utcnow)
    
    # Отношения
    parent = relationship("Product", remote_side=[id], backref="children")
    modifiers = relationship("ProductModifier", foreign_keys="ProductModifier.product_id", back_populates="product")
    used_as_modifier = relationship("ProductModifier", foreign_keys="ProductModifier.modifier_id", back_populates="modifier")
    
    tax_category = relationship("Category", foreign_keys=[tax_category_id])
    category = relationship("Category", foreign_keys=[category_id])
    accounting_category = relationship("Category", foreign_keys=[accounting_category_id])
    receipt_items = relationship("ReceiptItem", back_populates="product")

class ProductModifier(Base):
    __tablename__ = 'product_modifiers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey('products.id'), nullable=False)
    modifier_id = Column(UUID(as_uuid=True), ForeignKey('products.id'), nullable=False)
    position = Column(Integer, nullable=True)
    
    # Отношения
    product = relationship("Product", foreign_keys=[product_id], back_populates="modifiers")
    modifier = relationship("Product", foreign_keys=[modifier_id], back_populates="used_as_modifier")
    
    # Уникальное ограничение
    __table_args__ = (
        UniqueConstraint('product_id', 'modifier_id', name='unique_product_modifier'),
    )

class Category(Base):
    __tablename__ = 'categories'
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    name = Column(String(255), nullable=True)
    deleted = Column(Boolean, default=False)
    category_type = Column(String(50), nullable=True)  # 'tax', 'product', 'accounting'
    parent_id = Column(UUID(as_uuid=True), ForeignKey('categories.id'), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    parent = relationship("Category", remote_side=[id], backref="children")
    
    # Продукты, связанные с категорией
    products_in_category = relationship("Product", foreign_keys="Product.category_id", back_populates="category")
    products_in_tax_category = relationship("Product", foreign_keys="Product.tax_category_id", back_populates="tax_category")
    products_in_accounting_category = relationship("Product", foreign_keys="Product.accounting_category_id", back_populates="accounting_category")

class Store(Base):
    __tablename__ = 'stores'
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey('stores.id'), nullable=True)
    code = Column(String(50), nullable=True)
    name = Column(String(255), nullable=False)
    type = Column(Enum(StoreType), default=StoreType.STORE)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = Column(DateTime, default=datetime.utcnow)
    
    # Отношения
    parent = relationship("Store", remote_side=[id], backref="children")
    receipts = relationship("Receipt", back_populates="store")

class Receipt(Base):
    __tablename__ = 'receipts'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    receipt_number = Column(String(50), nullable=False, unique=True)
    external_id = Column(String(100), nullable=True)
    receipt_date = Column(DateTime, nullable=False)
    sale_date = Column(Date, nullable=False)
    total_amount = Column(Float, nullable=False)
    discount_amount = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    status = Column(Enum(ReceiptStatus), default=ReceiptStatus.COMPLETED)
    store_id = Column(UUID(as_uuid=True), ForeignKey('stores.id'), nullable=True)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = Column(DateTime, default=datetime.utcnow)
    
    # Дополнительные данные
    payment_method = Column(String(50), nullable=True)
    customer_info = Column(JSON, nullable=True)
    additional_data = Column(JSON, nullable=True)  # Переименовано из metadata из-за конфликта с SQLAlchemy
    
    # Отношения
    items = relationship("ReceiptItem", back_populates="receipt", cascade="all, delete-orphan")
    store = relationship("Store", back_populates="receipts")
    
    __table_args__ = (
        UniqueConstraint('receipt_number', 'sale_date', name='unique_receipt_per_day'),
    )

class ReceiptItem(Base):
    __tablename__ = 'receipt_items'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(UUID(as_uuid=True), ForeignKey('receipts.id'), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey('products.id'), nullable=False)
    
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    discount = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    
    item_order = Column(Integer, nullable=True)
    notes = Column(String, nullable=True)
    modifiers_data = Column(JSON, nullable=True)
    
    # Отношения
    receipt = relationship("Receipt", back_populates="items")
    product = relationship("Product", back_populates="receipt_items")

class Sale(Base):
    __tablename__ = 'sales'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_num = Column(Integer, nullable=False)
    fiscal_cheque_number = Column(String(50), nullable=True)
    cash_register_name = Column(String(255), nullable=True)
    cash_register_serial_number = Column(String(100), nullable=True)
    cash_register_number = Column(Integer, nullable=True)
    close_time = Column(DateTime, nullable=True)
    precheque_time = Column(DateTime, nullable=True)
    deleted_with_writeoff = Column(String(50), nullable=True)
    department = Column(String(255), nullable=True)
    department_id = Column(UUID(as_uuid=True), nullable=True)
    dish_amount = Column(Integer, nullable=True)
    dish_code = Column(String(50), nullable=True)
    dish_discount_sum = Column(Integer, nullable=True)
    dish_measure_unit = Column(String(20), nullable=True)
    dish_name = Column(String(255), nullable=True)
    dish_return_sum = Column(Integer, nullable=True)
    dish_sum = Column(Integer, nullable=True)
    increase_sum = Column(Integer, nullable=True)
    order_increase_type = Column(String(100), nullable=True)
    order_items = Column(Integer, nullable=True)
    order_type = Column(String(100), nullable=True)
    pay_types = Column(String(255), nullable=True)
    store_name = Column(String(255), nullable=True)
    store_id = Column(UUID(as_uuid=True), ForeignKey('stores.id'), nullable=True)
    storned = Column(Boolean, default=False, nullable=True)  # Флаг отмены чека
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = Column(DateTime, nullable=True)
    
    # Отношения
    store = relationship("Store")
    
    __table_args__ = (
        UniqueConstraint('order_num', 'fiscal_cheque_number', 'dish_code', 'cash_register_number', name='unique_sale_item'),
    )

class Account(Base):
    __tablename__ = 'accounts'
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    deleted = Column(Boolean, default=False, nullable=False)
    code = Column(String(50), nullable=True, unique=True)
    name = Column(String(255), nullable=False)
    account_parent_id = Column(UUID(as_uuid=True), ForeignKey('accounts.id'), nullable=True)
    parent_corporate_id = Column(UUID(as_uuid=True), nullable=True)
    type = Column(String(100), nullable=True)
    system = Column(Boolean, default=False, nullable=False)
    custom_transactions_allowed = Column(Boolean, default=True, nullable=False)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = Column(DateTime, default=datetime.utcnow)
    
    # Отношения
    parent = relationship("Account", remote_side=[id], backref="children")

class Department(Base):
    __tablename__ = 'departments'
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey('departments.id'), nullable=True)
    code = Column(String(50), nullable=True)
    name = Column(String(255), nullable=False)
    type = Column(String(50), default='DEPARTMENT')
    taxpayer_id_number = Column(String(50), nullable=True)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = Column(DateTime, default=datetime.utcnow)
    
    # Отношения
    parent = relationship("Department", remote_side=[id], backref="children")

class SyncLog(Base):
    __tablename__ = 'sync_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_date = Column(DateTime, default=datetime.utcnow)
    entity_type = Column(String(50))
    records_count = Column(Integer)
    status = Column(String(20))
    error_message = Column(String, nullable=True)
    details = Column(JSON, nullable=True)

class WriteoffDocument(Base):
    __tablename__ = 'writeoff_documents'
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    date_incoming = Column(DateTime, nullable=False)
    document_number = Column(String(50), nullable=False)
    status = Column(Enum(WriteoffDocumentStatus), nullable=False)
    conception_id = Column(UUID(as_uuid=True), nullable=True)
    comment = Column(String, nullable=True)
    store_id = Column(UUID(as_uuid=True), ForeignKey('stores.id'), nullable=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey('accounts.id'), nullable=True)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = Column(DateTime, default=datetime.utcnow)
    
    # Отношения
    store = relationship("Store", foreign_keys=[store_id])
    account = relationship("Account", foreign_keys=[account_id])
    items = relationship("WriteoffItem", back_populates="document", cascade="all, delete-orphan")

class WriteoffItem(Base):
    __tablename__ = 'writeoff_items'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey('writeoff_documents.id'), nullable=False)
    num = Column(Integer, nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey('products.id'), nullable=False)
    product_size_id = Column(UUID(as_uuid=True), nullable=True)
    amount_factor = Column(Numeric(10, 3), nullable=False, default=1)
    amount = Column(Numeric(10, 3), nullable=False)
    measure_unit_id = Column(UUID(as_uuid=True), nullable=True)
    container_id = Column(UUID(as_uuid=True), nullable=True)
    cost = Column(Numeric(10, 2), nullable=True)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    document = relationship("WriteoffDocument", back_populates="items")
    product = relationship("Product", foreign_keys=[product_id])
    
    # Уникальное ограничение для предотвращения дублирования строк в документе
    __table_args__ = (
        UniqueConstraint('document_id', 'num', name='unique_writeoff_item_num'),
    )

class Supplier(Base):
    __tablename__ = 'suppliers'
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    code = Column(String(50), nullable=True)
    name = Column(String(255), nullable=False)
    login = Column(String(100), nullable=True)
    card_number = Column(String(50), nullable=True)
    taxpayer_id_number = Column(String(50), nullable=True)
    snils = Column(String(50), nullable=True)
    deleted = Column(Boolean, default=False)
    is_supplier = Column(Boolean, default=True)
    is_employee = Column(Boolean, default=False)
    is_client = Column(Boolean, default=False)
    represents_store = Column(Boolean, default=False)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = Column(DateTime, default=datetime.utcnow)

class Price(Base):
    __tablename__ = 'prices'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey('departments.id'), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey('products.id'), nullable=False)
    product_size_id = Column(UUID(as_uuid=True), nullable=True)
    price_type = Column(String(50), default='BASE')
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    tax_category_id = Column(UUID(as_uuid=True), nullable=True)
    tax_category_enabled = Column(Boolean, default=False)
    included = Column(Boolean, default=True)
    dish_of_day = Column(Boolean, default=False)
    flyer_program = Column(Boolean, default=False)
    document_id = Column(UUID(as_uuid=True), nullable=True)
    schedule = Column(String, nullable=True)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = Column(DateTime, default=datetime.utcnow)
    
    # Отношения
    department = relationship("Department", foreign_keys=[department_id])
    product = relationship("Product", foreign_keys=[product_id])
    
    # Уникальное ограничение
    __table_args__ = (
        UniqueConstraint('department_id', 'product_id', 'product_size_id', 'price_type', 'date_from', 'date_to', 
                        name='unique_price_entry'),
    )


class IncomingInvoice(Base):
    __tablename__ = 'incoming_invoices'
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    transport_invoice_number = Column(String(100))
    incoming_document_number = Column(String(100))
    incoming_date = Column(Date)
    use_default_document_time = Column(Boolean, default=False)
    due_date = Column(Date, nullable=True)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey('suppliers.id'))
    default_store_id = Column(UUID(as_uuid=True), ForeignKey('stores.id'))
    invoice = Column(String(255))
    date_incoming = Column(DateTime)
    document_number = Column(String(100), nullable=False)
    comment = Column(Text)
    conception = Column(UUID(as_uuid=True))
    conception_code = Column(String(50))
    status = Column(String(50))
    distribution_algorithm = Column(String(100))
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    supplier = relationship('Supplier', backref='incoming_invoices')
    store = relationship('Store', backref='incoming_invoices')
    items = relationship('IncomingInvoiceItem', back_populates='invoice', cascade='all, delete-orphan')


class IncomingInvoiceItem(Base):
    __tablename__ = 'incoming_invoice_items'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey('incoming_invoices.id', ondelete='CASCADE'), nullable=False)
    is_additional_expense = Column(Boolean, default=False)
    actual_amount = Column(Numeric(15, 9))
    store_id = Column(UUID(as_uuid=True), ForeignKey('stores.id'))
    code = Column(String(50))
    price = Column(Numeric(15, 9))
    price_without_vat = Column(Numeric(15, 9))
    sum = Column(Numeric(15, 9))
    vat_percent = Column(Numeric(15, 9))
    vat_sum = Column(Numeric(15, 9))
    discount_sum = Column(Numeric(15, 9))
    amount_unit = Column(UUID(as_uuid=True))
    num = Column(Integer)
    product_id = Column(UUID(as_uuid=True), ForeignKey('products.id'))
    product_article = Column(String(50))
    amount = Column(Numeric(15, 9))
    supplier_id = Column(UUID(as_uuid=True), ForeignKey('suppliers.id'))
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    invoice = relationship('IncomingInvoice', back_populates='items')
    product = relationship('Product', backref='incoming_invoice_items')
    store = relationship('Store', backref='incoming_invoice_items')
    supplier = relationship('Supplier', backref='incoming_invoice_items')