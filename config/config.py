import os
from dotenv import load_dotenv

load_dotenv()

# IIKO API Configuration
IIKO_API_BASE_URL = "https://madlen-group-so.iiko.it/resto/api"
IIKO_API_LOGIN = os.getenv("IIKO_API_LOGIN", "Tanat")
IIKO_API_PASSWORD = os.getenv("IIKO_API_PASSWORD", "7c4a8d09ca3762af61e59520943dc26494f8941b")

# Database Configuration
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'iiko_data'),
    'user': os.getenv('DB_USER', 'rus'),
    'password': os.getenv('DB_PASSWORD', '')
}
