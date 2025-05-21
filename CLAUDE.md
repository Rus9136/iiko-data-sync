# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IIKO Data Sync is a system for synchronizing data from IIKO API to a local PostgreSQL database with a web interface for management. The project consists of:
- Console sync tool (`main.py`)
- Web interface (`run_web.py`)
- IIKO API client
- PostgreSQL data models

## Common Commands

### Setup and Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Create database
createdb iiko_data

# Apply migrations (use the latest version)
psql -U rus -d iiko_data -f migrations/002_fixed_create_products_table.sql
psql -U rus -d iiko_data -f migrations/003_fix_unique_code_constraint.sql
psql -U rus -d iiko_data -f migrations/004_add_storned_field.sql
psql -U rus -d iiko_data -f migrations/005_update_sales_unique_constraint.sql
```

### Development Commands
```bash
# Run web interface (with auto-browser opening)
python run_web.py

# Run console sync
python main.py

# Sync only products
python main.py --entity products

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
│   └── synchronizer.py    # Sync logic
├── web/
│   ├── app.py            # Flask application
│   ├── static/           # CSS files
│   └── templates/        # HTML templates
├── .env                  # Environment variables
├── main.py              # Console entry point
└── run_web.py           # Web interface entry point
```

### Key Components

#### API Client (`src/api_client.py`)
- Handles IIKO API authentication (hash-based)
- Fetches products with pagination
- Supports departments, stores, and sales data
- Implements OLAP API for sales data retrieval
- Token management with auto-refresh
- Filters data correctly (storned, deleted, returns)

#### Database Models (`src/models.py`)
- Product model with UUID primary keys
- Category model for different category types
- ProductModifier for many-to-many relationships
- Store model for physical store locations
- Sale model for sales data with compound keys
- SyncLog for tracking sync operations

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
- Supports date range filtering
- Properly handles store references

#### Web Interface (`web/app.py`)
- Flask application with Bootstrap UI
- CORS enabled for cross-origin requests
- Endpoints: `/`, `/products`, `/product/<id>`, `/sync`, `/upload`, `/logs`, `/sales`, `/sales/sync`, `/sales/report`
- Must run on `127.0.0.1` for macOS compatibility

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
- Requires `Cookie: key={token}` header

### macOS-Specific Issues

The web interface must be configured to run on `127.0.0.1` instead of `0.0.0.0` due to macOS security restrictions. The `run_web.py` script handles this automatically.

### Database Schema

Key tables:
- `products`: Main product table with UUID id, code (unique), name, etc.
- `categories`: Stores all category types (tax, product, accounting)
- `product_modifiers`: Many-to-many relationship table
- `stores`: Physical store locations
- `sales`: Sales data with compound keys (order_num, fiscal_cheque_number, dish_code, cash_register_number)
- `sync_log`: Tracks all sync operations

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

### Testing

Test files are available for:
- API connection (`test_api.py`)
- Database connection (`test_db.py`)
- Web interface (`test_web.py`)
- Sales data accuracy (`test_report_accuracy.py`)

### Common Issues

1. Port conflicts: Change port in `run_web.py` if 8080 is busy
2. CORS errors: Ensure `flask-cors` is installed and CORS is enabled
3. Database duplicates: Check the unique constraint on product code and sales compound key
4. macOS connection refused: Use `127.0.0.1` instead of `localhost`
5. NULL values in filtering: Always handle NULL values in database filters with `or_` conditions
6. Missing dependencies: Ensure pandas and xlsxwriter are installed for report export
7. Date format issues: Use clear date formatting in filters and parameters