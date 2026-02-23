import sys
import os
import psycopg2
from psycopg2 import sql

# Agregar el directorio raiz al path para poder importar config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config.config import DB_CONFIG

def init_database():
    """Inicializa la base de datos y crea el schema"""
    
    # Leer el schema.sql
    with open('database/schema.sql', 'r', encoding='utf-8') as f:
        schema_content = f.read()
    
    try:
        # Primero conectar al servidor para crear la DB si no existe
        print("Conectando a PostgreSQL...")
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database='postgres' # Nos conectamos a postgres para poder crear la otra DB
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Verificar si la BD existe
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'github_analyzer'")
        exists = cursor.fetchone()
        
        if not exists:
            print('[INFO] Creando base de datos github_analyzer...')
            cursor.execute(sql.SQL('CREATE DATABASE github_analyzer;'))
            print('[OK] Base de datos creada exitosamente')
        else:
            print('[INFO] Base de datos github_analyzer ya existe')
        
        cursor.close()
        conn.close()
        
        # Ahora conectar a la BD y ejecutar el schema
        print("Conectando a la base de datos github_analyzer...")
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Dividir el script en comandos individuales y ejecutar
        commands = schema_content.split(';')
        command_count = 0
        
        for command in commands:
            command = command.strip()
            if command and not command.startswith('--'):
                if not command.startswith('\\c'):  # Skip connection commands
                    try:
                        print(f'[{command_count+1}] Ejecutando: {command[:60]}...')
                        cursor.execute(command)
                        command_count += 1
                    except psycopg2.Error as e:
                        error_msg = str(e)
                        # Ignorar errores de tablas/indices/vistas que ya existen
                        if any(x in error_msg for x in ['ya existe', 'already exists', 'duplicate key']):
                            print(f'    [SKIP] Recurso ya existe')
                        else:
                            print(f'    [ERROR] {error_msg}')
        
        cursor.close()
        conn.close()
        
        print(f'\n[OK] Schema inicializado exitosamente ({command_count} comandos ejecutados)')
        return True
        
    except psycopg2.Error as e:
        print(f'[ERROR] Problema de conexion a PostreSQL: {e}')
        return False
    except Exception as e:
        print(f'[ERROR] {e}')
        return False

if __name__ == '__main__':
    import sys
    success = init_database()
    sys.exit(0 if success else 1)
