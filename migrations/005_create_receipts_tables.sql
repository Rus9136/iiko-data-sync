-- Migration: Create Receipts Tables
-- Description: Creates tables for sales receipts and receipt items

-- Create enum type for receipt status
CREATE TYPE receipt_status AS ENUM ('COMPLETED', 'CANCELLED', 'PROCESSING');

-- Create receipts table
CREATE TABLE IF NOT EXISTS receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_number VARCHAR(50) NOT NULL UNIQUE,
    external_id VARCHAR(100),
    receipt_date TIMESTAMP NOT NULL,
    sale_date DATE NOT NULL,
    total_amount FLOAT NOT NULL,
    discount_amount FLOAT DEFAULT 0.0,
    tax_amount FLOAT DEFAULT 0.0,
    status receipt_status DEFAULT 'COMPLETED',
    store_id UUID REFERENCES stores(id),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Additional data
    payment_method VARCHAR(50),
    customer_info JSONB,
    metadata JSONB,
    
    -- Constraints
    CONSTRAINT unique_receipt_per_day UNIQUE (receipt_number, sale_date)
);

-- Create receipt_items table
CREATE TABLE IF NOT EXISTS receipt_items (
    id SERIAL PRIMARY KEY,
    receipt_id UUID NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    
    quantity FLOAT NOT NULL,
    unit_price FLOAT NOT NULL,
    total_price FLOAT NOT NULL,
    discount FLOAT DEFAULT 0.0,
    tax_amount FLOAT DEFAULT 0.0,
    
    item_order INTEGER,
    notes TEXT,
    modifiers_data JSONB
);

-- Create indexes for better performance
CREATE INDEX idx_receipt_items_receipt_id ON receipt_items(receipt_id);
CREATE INDEX idx_receipt_items_product_id ON receipt_items(product_id);
CREATE INDEX idx_receipts_sale_date ON receipts(sale_date);
CREATE INDEX idx_receipts_store_id ON receipts(store_id);

-- Add comment to describe table purpose
COMMENT ON TABLE receipts IS 'Stores sales receipts from IIKO POS system';
COMMENT ON TABLE receipt_items IS 'Stores line items for sales receipts';