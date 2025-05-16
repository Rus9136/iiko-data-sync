from sqlalchemy import create_engine, Column, String, Boolean, DateTime, ForeignKey, Integer, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import uuid

Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    deleted = Column(Boolean, default=False, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
    num = Column(String(50), nullable=True)
    code = Column(String(50), unique=True, nullable=True)
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

class SyncLog(Base):
    __tablename__ = 'sync_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_date = Column(DateTime, default=datetime.utcnow)
    entity_type = Column(String(50))
    records_count = Column(Integer)
    status = Column(String(20))
    error_message = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
