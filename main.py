"""
GitHub Analyzer - Aplicación Principal
Punto de entrada de la aplicación
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gui.main_gui import main

if __name__ == '__main__':
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║                                                            ║
    ║        GitHub Repository Analyzer - ML Edition             ║
    ║                                                            ║
    ║  Herramienta de análisis de repositorios con ML            ║
    ║  - Detección de credenciales expuestas                     ║
    ║  - Análisis de commits con Machine Learning                ║
    ║  - Clasificación con Árboles de Decisión CART              ║
    ║  - Índice de Gini para pureza de nodos                     ║
    ║                                                            ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    print("🚀 Iniciando aplicación...")
    main()