import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()

# Configuracion de Base de Datos PostgreSQL
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'github_analyzer'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '')
}

# Configuracion de GitHub API
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')

# Configuracion de Machine Learning
ML_CONFIG = {
    'test_size': 0.3,
    'random_state': 42,
    'max_depth': 10,
    'min_samples_split': 5,
    'criterion': 'gini'
}

# Patrones regex para deteccion de credenciales
CREDENTIAL_PATTERNS = {
    'aws_access_key': r'AKIA[0-9A-Z]{16}',
    'aws_secret_key': r'aws(.{0,20})?[\'"][0-9a-zA-Z\/+]{40}[\'"]',
    'github_token': r'gh[pousr]_[0-9a-zA-Z]{36}',
    'github_pat': r'github_pat_[0-9a-zA-Z_]{82}',
    'github_oauth': r'gho_[0-9a-zA-Z]{36}',
    'db_password': r'(?:password|passwd|pwd|db_pass|db_password)[\'"\s:=]+[^\s\'"]{6,}',
    'password': r'password[\'"\s:=]+[^\s\'"]{6,}',
    'db_user': r'(?:user|username|db_user)[\'"\s:=]+[^\s\'"]{4,}',
    'connection_string': r'(?:mongodb|mysql|postgresql|sqlserver|postgres|mssql|oracle|sqlite):\/\/[^\s\'"]+',
    'generic_api_key': r'api[_-]?key[\'"\s:=]+[0-9a-zA-Z]{12,}',
    'generic_secret': r'secret[\'"\s:=]+[0-9a-zA-Z]{12,}',
    'private_key': r'-----BEGIN (RSA|DSA|EC|OPENSSH) PRIVATE KEY-----',
    'slack_token': r'xox[baprs]-[0-9a-zA-Z]{10,48}',
    'stripe_key': r'sk_live_[0-9a-zA-Z]{24}',
    'google_api': r'AIza[0-9A-Za-z\\-_]{35}',
    'heroku_api': r'[h|H][e|E][r|R][o|O][k|K][u|U].{0,30}[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}',
    'mailgun_api': r'key-[0-9a-zA-Z]{32}',
    'jwt_token': r'eyJ[0-9a-zA-Z_-]*\.eyJ[0-9a-zA-Z_-]*\.[0-9a-zA-Z_-]*',
    'bearer_token': r'Bearer\s+[0-9a-zA-Z\-._~+\/]+=*'
}

# Configuracion de GUI
GUI_CONFIG = {
    'window_title': 'GitHub Repository Analyzer - ML',
    'window_size': '1400x800',
    'theme': 'clam'
}