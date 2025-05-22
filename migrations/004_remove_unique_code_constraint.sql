-- Migration: Remove unique constraint from products.code field
-- This allows products with duplicate codes to be stored

-- Remove the unique constraint on code field
ALTER TABLE products DROP CONSTRAINT IF EXISTS products_code_key;

-- Create index for performance (non-unique)
CREATE INDEX IF NOT EXISTS idx_products_code ON products(code);