# -*- coding: utf-8 -*-
"""Verificacion final de conexion a la BD"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import DB_CONFIG
import psycopg2

print("=== VERIFICACION DE CONEXION A BASE DE DATOS ===\n")
print(f"Host: {DB_CONFIG['host']}")
print(f"Puerto: {DB_CONFIG['port']}")
print(f"Base de datos: {DB_CONFIG['database']}")
print(f"Usuario: {DB_CONFIG['user']}")
print(f"Password: {'*' * len(DB_CONFIG['password'])}")

try:
    dsn = f"host={DB_CONFIG['host']} port={DB_CONFIG['port']} dbname={DB_CONFIG['database']} user={DB_CONFIG['user']} password={DB_CONFIG['password']}"
    conn = psycopg2.connect(dsn)
    print("\n[OK] Conexion exitosa a PostgreSQL!")
    
    cur = conn.cursor()
    
    # Listar tablas
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
    tables = [r[0] for r in cur.fetchall()]
    print(f"\n[INFO] Tablas encontradas ({len(tables)}):")
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        count = cur.fetchone()[0]
        print(f"  - {t} ({count} registros)")
    
    # Verificar columnas de credentials_detected
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'credentials_detected' 
        ORDER BY ordinal_position
    """)
    cols = cur.fetchall()
    print(f"\n[INFO] Columnas de credentials_detected:")
    for col_name, col_type in cols:
        print(f"  - {col_name} ({col_type})")
    
    cur.close()
    conn.close()
    print("\n[OK] BASE DE DATOS LISTA Y FUNCIONAL!")
    
except Exception as e:
    print(f"\n[ERROR] {type(e).__name__}: {e}")
    sys.exit(1)
