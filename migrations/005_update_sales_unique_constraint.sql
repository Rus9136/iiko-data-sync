-- Удаление старого ограничения
ALTER TABLE sales DROP CONSTRAINT IF EXISTS unique_order_fiscal_number;

-- Добавление нового ограничения с учетом товара и кассы
ALTER TABLE sales ADD CONSTRAINT unique_sale_item UNIQUE (order_num, fiscal_cheque_number, dish_code, cash_register_number);