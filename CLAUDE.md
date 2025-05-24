# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IIKO Data Sync is a comprehensive system for synchronizing data from IIKO API to a local PostgreSQL database with a feature-rich web interface for management. The project consists of:
- Console sync tool (`main.py`) with support for multiple entity types
- Web interface (`run_web.py`) with dashboard, reports, and CRUD operations
- IIKO API client with authentication and pagination support
- PostgreSQL data models for all IIKO entities
- Excel export functionality for reports
- AJAX-powered UI with sidebar navigation

## Common Commands

### Setup and Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Create database
createdb iiko_data

# Apply migrations (in order)
psql -U rus -d iiko_data -f migrations/001_create_tables.sql
psql -U rus -d iiko_data -f migrations/002_fixed_create_products_table.sql
psql -U rus -d iiko_data -f migrations/003_fix_unique_code_constraint.sql
psql -U rus -d iiko_data -f migrations/004_add_storned_field.sql
psql -U rus -d iiko_data -f migrations/005_update_sales_unique_constraint.sql
psql -U rus -d iiko_data -f migrations/006_create_accounts_table.sql
psql -U rus -d iiko_data -f migrations/007_fix_accounts_code_constraint.sql
psql -U rus -d iiko_data -f migrations/008_create_writeoff_tables.sql
psql -U rus -d iiko_data -f migrations/009_create_departments_table.sql
psql -U rus -d iiko_data -f migrations/010_create_prices_table.sql
psql -U rus -d iiko_data -f migrations/011_create_suppliers_table.sql
psql -U rus -d iiko_data -f migrations/012_create_incoming_invoices_table.sql
```

### Development Commands
```bash
# Run web interface (with auto-browser opening)
python run_web.py

# Run console sync
python main.py

# Sync only products
python main.py --entity products

# Sync sales data for specific date range
python main.py --entity sales --date-from "2025-05-19 00:00:00" --date-to "2025-05-19 23:59:59"

# Sync writeoff documents for specific date range
python main.py --entity writeoffs --date-from "2025-05-19 00:00:00" --date-to "2025-05-19 23:59:59"

# Sync suppliers
python main.py --entity suppliers

# Sync incoming invoices for specific date range
python main.py --entity incoming_invoices --date-from "2025-05-19 00:00:00" --date-to "2025-05-19 23:59:59"

# Sync departments
python main.py --entity departments

# Sync prices
python main.py --entity prices

# Analyze API structure only
python main.py --analyze

# Test API connection
python test_api.py

# Test database connection
python test_db.py
```

### Debugging Commands
```bash
# Check logs
tail -f logs/sync_*.log

# Check if port is in use
lsof -i :8080

# Test web server connection
curl -v http://127.0.0.1:8080
```

## Architecture

### Directory Structure
```
iiko-data-sync/
├── config/
│   └── config.py          # API and DB configuration
├── migrations/            # PostgreSQL migration files
├── src/
│   ├── api_client.py      # IIKO API client implementation
│   ├── models.py          # SQLAlchemy models
│   ├── synchronizer.py    # Product sync logic
│   ├── store_synchronizer.py     # Store sync logic
│   ├── sales_synchronizer.py     # Sales sync logic
│   ├── department_synchronizer.py # Department sync logic
│   ├── price_synchronizer.py     # Price sync logic
│   ├── supplier_synchronizer.py  # Supplier sync logic
│   └── incoming_invoice_synchronizer.py # Incoming invoice sync logic
├── web/
│   ├── app.py            # Flask application
│   ├── report_controller.py # Report generation
│   ├── static/           # CSS files
│   └── templates/        # HTML templates with AJAX support
├── .env                  # Environment variables
├── main.py              # Console entry point
└── run_web.py           # Web interface entry point
```

### Key Components

#### API Client (`src/api_client.py`)
- Handles IIKO API authentication (hash-based)
- Fetches products with pagination
- Supports departments, stores, sales, suppliers, incoming invoices
- Implements OLAP API for sales and operational reports
- Token management with auto-refresh
- Filters data correctly (storned, deleted, returns)
- Supports price lists fetching
- Handles incoming document operations

#### Database Models (`src/models.py`)
- Product model with UUID primary keys
- Category model for different category types (tax, product, accounting)
- ProductModifier for many-to-many relationships
- Store model for physical store locations
- Sale model for sales data with compound keys
- Account model for financial accounts
- WriteoffDocument and WriteoffItem for writeoff operations
- Department model for organizational structure
- Price model for product pricing with date ranges
- Supplier model for supplier management
- IncomingInvoice and IncomingInvoiceItem for incoming documents
- SyncLog for tracking all sync operations

#### Synchronizers
##### Product Synchronizer (`src/synchronizer.py`)
- Manages database connections
- Implements upsert logic for products
- Handles duplicate prevention (by code)
- Tracks sync statistics

##### Store Synchronizer (`src/store_synchronizer.py`)
- Syncs store data from IIKO API
- Maintains store hierarchy

##### Sales Synchronizer (`src/sales_synchronizer.py`) 
- Syncs sales data using OLAP API
- Handles compound unique keys for sale items
- Supports date range filtering with proper format handling
- Properly handles store references
- Clears existing data option for full refresh

##### Department Synchronizer (`src/department_synchronizer.py`)
- Syncs department hierarchy
- Handles parent-child relationships
- Maintains department codes and taxpayer IDs

##### Price Synchronizer (`src/price_synchronizer.py`)
- Syncs product prices across departments
- Handles date-based price ranges
- Supports different price types
- Manages tax categories and schedules

##### Supplier Synchronizer (`src/supplier_synchronizer.py`)
- Syncs supplier/contractor data
- Filters by is_supplier flag
- Handles multiple roles (supplier, employee, client)
- Manages taxpayer IDs and card numbers

##### Incoming Invoice Synchronizer (`src/incoming_invoice_synchronizer.py`)
- Syncs incoming invoices with items
- Supports date range filtering
- Handles document statuses
- Links to suppliers and stores
- Manages VAT calculations

#### Web Interface (`web/app.py`)
- Flask application with Bootstrap UI and sidebar navigation
- CORS enabled for cross-origin requests
- AJAX support for seamless page updates
- Dashboard with real-time statistics
- Organized sidebar sections:
  - **Справочники** (References): Products, Stores, Suppliers, Departments, Accounts
  - **Документы** (Documents): Sales, Writeoffs, Incoming Invoices
  - **Сервис** (Service): Upload, Sync History, Operational Summary
- Key endpoints:
  - `/` - Dashboard with statistics
  - `/products`, `/product/<id>` - Product management
  - `/stores`, `/store/<id>` - Store management
  - `/suppliers/list` - Supplier list
  - `/departments`, `/department/<id>` - Department management
  - `/accounts`, `/account/<id>` - Account management
  - `/sales`, `/sale/<id>` - Sales with receipt grouping
  - `/sales/sync` - Sales synchronization interface
  - `/sales/report` - Sales reports with Excel export
  - `/writeoffs`, `/writeoff/<id>` - Writeoff documents
  - `/writeoffs/sync` - Writeoff synchronization
  - `/incoming_invoices`, `/incoming_invoice/<id>` - Incoming invoices
  - `/incoming_invoices/sync` - Invoice synchronization
  - `/operational-summary` - Operational reports
  - `/upload` - Multi-entity synchronization page
  - `/logs` - Sync history and logs
- Must run on `127.0.0.1` for macOS compatibility
- **Sales Interface Redesign (2025-05)**: 
  - Sales list shows receipt headers only (grouped by order_num and fiscal_cheque_number)
  - Receipt detail page shows structured layout with header info and tabular positions
  - Uses raw PostgreSQL SQL for proper aggregation with BOOL_OR and type casting
- **Product Detail Enhancement**: Fixed full-screen mode navigation issues
- **Report Generation**: Excel export with pandas and xlsxwriter

### Important Configuration

#### Environment Variables (.env)
```
IIKO_API_LOGIN=Tanat
IIKO_API_PASSWORD=[hash]
DB_HOST=localhost
DB_PORT=5432
DB_NAME=iiko_data
DB_USER=rus
DB_PASSWORD=[password]
```

#### IIKO API Details
- Base URL: `https://madlen-group-so.iiko.it/resto/api`
- Auth endpoint: `/auth?login={login}&pass={password}`
- Products endpoint: `/v2/entities/products/list?includeDeleted=false`
- OLAP endpoint for sales: `/v2/reports/olap`
- Store endpoint: `/corporation/stores`
- Departments endpoint: `/corporation/departments`
- Suppliers endpoint: `/suppliers`
- Incoming documents endpoint: `/documents/import/incomingInvoice`
- Price lists endpoint: `/v2/documents/priceList`
- Requires `Cookie: key={token}` header

### macOS-Specific Issues

The web interface must be configured to run on `127.0.0.1` instead of `0.0.0.0` due to macOS security restrictions. The `run_web.py` script handles this automatically.

### Database Schema

Key tables:
- `products`: Main product table with UUID id, code, name, categories
- `categories`: Stores all category types (tax, product, accounting)
- `product_modifiers`: Many-to-many relationship table
- `stores`: Physical store locations with hierarchy
- `departments`: Organizational departments with hierarchy
- `sales`: Sales data with compound keys (order_num, fiscal_cheque_number, dish_code, cash_register_number)
- `receipts`: Receipt headers (currently unused, sales are grouped in views)
- `receipt_items`: Receipt line items (currently unused)
- `writeoff_documents`: Writeoff document headers with UUID id, document number, status
- `writeoff_items`: Individual writeoff items with 3-decimal precision amounts
- `accounts`: Account information for writeoffs filtering with hierarchy
- `suppliers`: Supplier/contractor information with multiple role flags
- `prices`: Product prices by department with date ranges
- `incoming_invoices`: Incoming invoice headers with supplier and store references
- `incoming_invoice_items`: Invoice line items with VAT calculations
- `sync_log`: Tracks all sync operations with detailed statistics

### Development Notes

When modifying the codebase:
1. Always use absolute paths in imports
2. Check for existing products by code (unique constraint)
3. Check for existing sales by compound key (order_num, fiscal_cheque_number, dish_code, cash_register_number)
4. Log all operations to both file and console
5. Handle IIKO API errors gracefully
6. Use pagination for large datasets (4000 items per page)
7. Handle NULL values in database queries properly
8. Include storned flag when filtering sales data
9. **PostgreSQL Aggregation**: Use raw SQL with proper PostgreSQL functions (BOOL_OR, type casting) when SQLAlchemy ORM has limitations
10. **Writeoff Precision**: Display writeoff quantities with 3 decimal places (%.3f format)
11. **Status Filtering**: Filter writeoff documents by NEW and PROCESSED statuses only
12. **Date Format Handling**: Use proper datetime parsing for API requests (ISO format with timezone)
13. **AJAX Navigation**: Implement proper AJAX handlers for seamless page transitions
14. **Excel Export**: Use pandas DataFrame with xlsxwriter engine for report generation
15. **Supplier Filtering**: Filter suppliers by is_supplier=true for proper lists
16. **Invoice Item Aggregation**: Handle high-precision numeric fields (15,9) for amounts and prices

### Testing

Test files are available for:
- API connection (`test_api.py`)
- Database connection (`test_db.py`)
- Web interface (`test_web.py`)
- Sales data accuracy (`test_report_accuracy.py`)
- Product count verification (`test_products_count.py`)
- Writeoff count verification (`test_writeoff_count.py`)
- Sales synchronization (`test_sales_load.py`)
- API product testing (`test_api_products.py`)

### Common Issues

1. Port conflicts: Change port in `run_web.py` if 8080 is busy
2. CORS errors: Ensure `flask-cors` is installed and CORS is enabled
3. Database duplicates: Check the unique constraint on product code and sales compound key
4. macOS connection refused: Use `127.0.0.1` instead of `localhost`
5. NULL values in filtering: Always handle NULL values in database filters with `or_` conditions
6. Missing dependencies: Ensure pandas and xlsxwriter are installed for report export
7. Date format issues: Use ISO format with proper timezone handling
8. Decimal precision: Use Numeric type for financial calculations
9. AJAX errors: Check X-Requested-With header for AJAX detection
10. Sidebar navigation: Ensure proper active state management
11. Full-screen modals: Handle navigation properly with Bootstrap modals