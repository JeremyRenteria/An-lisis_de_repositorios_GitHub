# GitHub Repository Analyzer - Machine Learning Edition

## 📋 Descripción del Proyecto

Herramienta de escritorio desarrollada en Python para analizar repositorios de GitHub, detectar credenciales expuestas y clasificar commits usando Machine Learning con Árboles de Decisión CART.

## 🎯 Características Principales

### 1. Detección de Credenciales
- Utiliza **expresiones regulares (regex)** con la librería `re`
- Detecta múltiples tipos de credenciales:
  - Claves AWS
  - Tokens de GitHub
  - Claves API
  - Contraseñas
  - Claves privadas
  - Y más...

### 2. Análisis de Commits
- Integración con la API de GitHub
- Análisis de diff de commits
- Extracción de características
- Almacenamiento en PostgreSQL

### 3. Machine Learning (4 Modelos)
- **Clasificador de Credenciales**: Random Forest + TF-IDF
- **Clasificador de Commits**: Árbol de Decisión CART (Gini)
- **Detector de Anomalías**: Isolation Forest (Riesgo de commit)
- **Clustering de Repositorios**: K-Means (Nivel de riesgo general)

### 4. Base de Datos
- PostgreSQL para almacenamiento persistente
- Tablas relacionales optimizadas
- Vistas para análisis rápido

### 5. Interfaz Gráfica
- Desarrollada con tkinter
- Tablas interactivas
- Visualización de resultados
- Exportación de datos

## 🏗️ Arquitectura del Proyecto

```
github_analyzer/
│
├── main.py                 # Punto de entrada
├── requirements.txt        # Dependencias
├── README.md              # Este archivo
│
├── config/
│   └── config.py          # Configuración global
│
├── database/
│   ├── schema.sql         # Esquema de BD
│   └── db_manager.py      # Gestor de PostgreSQL
│
├── utils/
│   ├── credential_detector.py  # Detección con regex
│   └── github_api.py          # Integración con GitHub
│
├── models/
│   ├── ml_credential_classifier.py  # Random Forest (Credenciales)
│   ├── ml_classifier.py             # Modelo CART con Gini (Commits)
│   ├── ml_anomaly_detector.py       # Isolation Forest (Anomalías)
│   └── ml_repo_clusterer.py         # K-Means (Clustering)
│
└── gui/
    └── main_gui.py        # Interfaz gráfica
```

## 📊 Diseño de Datos

### Modelo Entidad-Relación

```
repositories (1) ──< (N) commits (1) ──< (N) credentials_detected
                                │
                                └──< (1) commit_features
```

### Tablas Principales

1. **repositories**: Información de repositorios analizados
2. **commits**: Detalles de cada commit
3. **credentials_detected**: Credenciales encontradas
4. **commit_features**: Características para ML
5. **ml_model_results**: Resultados del modelo

## 🚀 Instalación y Configuración

### 1. Requisitos Previos
- Python 3.8+
- PostgreSQL 12+
- Token de GitHub (Personal Access Token)

### 2. Clonar o Crear el Proyecto
```bash
# Si usas git
git clone [url-del-repositorio]
cd github_analyzer

# O crea las carpetas manualmente según la estructura
```

### 3. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar PostgreSQL

#### Crear la base de datos:
```bash
psql -U postgres
```

```sql
-- Ejecutar el contenido de database/schema.sql
\i database/schema.sql
```

#### Configurar credenciales:
Edita `config/config.py`:
```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'github_analyzer',
    'user': 'tu_usuario',
    'password': 'tu_password'
}
```

### 5. Configurar Token de GitHub

1. Crear un Personal Access Token:
   - GitHub → Settings → Developer settings → Personal access tokens
   - Permisos necesarios: `repo`, `read:user`

2. Edita `config/config.py`:
```python
GITHUB_TOKEN = 'ghp_tu_token_aqui'
```

### 6. Ejecutar la Aplicación
```bash
python main.py
```

## 📖 Uso de la Aplicación

### Análisis de Repositorio

1. **Abrir la pestaña "Análisis de Repositorio"**
2. **Ingresar datos**:
   - Propietario: `facebook`
   - Repositorio: `react`
   - Rama: `main`
   - Máx. Commits: `100`
3. **Clic en "Iniciar Análisis"**
4. **Esperar resultados en el log**

### Ver Resultados

1. **Pestaña "Resultados"**: Tabla con credenciales detectadas
2. **Pestaña "Estadísticas"**: Resumen general
3. **Exportar**: Botón para guardar en CSV

### Entrenar Modelo ML

1. **Analizar varios repositorios primero** (mínimo 10 commits)
2. **Pestaña "Modelo ML"**
3. **Clic en "Entrenar Modelo"**
4. **Ver métricas**: Accuracy, Precision, Recall, F1-Score

## 🤖 Machine Learning - Detalles Técnicos

### 1. Clasificador de Commits (Árbol de Decisión CART)

**CART** (Classification and Regression Trees) es un algoritmo que construye árboles de decisión binarios para evaluar commits como seguros o riesgosos.

### 2. Clasificador de Credenciales (Random Forest + TF-IDF)

**Random Forest** evalúa los candidatos encontrados por regex extrajo características (entropía, contexto TF-IDF) para filtrar falsos positivos de credenciales.

### 3. Detector de Anomalías (Isolation Forest)

Calcula el el `risk_score` de cada commit detectando patrones anómalos de manera no supervisada en bas a los cambios de código.

### 4. Clustering de Riesgo (K-Means)

Segmenta los repositorios en niveles (LOW, MEDIUM, HIGH, CRITICAL) mediante aprendizaje no supervisado.

#### Índice de Gini (Modelo CART)

La **impureza de Gini** mide qué tan "mezcladas" están las clases en un nodo:

```
Gini(node) = 1 - Σ(p_i²)
```

Donde `p_i` es la proporción de muestras de la clase `i`.

**Interpretación**:
- `Gini = 0`: Nodo puro (todas las muestras de la misma clase)
- `Gini = 0.5`: Máxima impureza (50%-50% en clasificación binaria)

#### Proceso de Construcción

1. **Selección de división**: 
   - Para cada característica, evaluar todas las divisiones posibles
   - Calcular la ganancia de Gini de cada división
   - Elegir la división que minimiza la impureza

2. **División recursiva**:
   - Aplicar el mismo proceso a cada nodo hijo
   - Continuar hasta alcanzar criterios de parada

3. **Criterios de parada**:
   - Profundidad máxima (`max_depth`)
   - Mínimo de muestras para dividir (`min_samples_split`)
   - Nodo puro

#### Características Utilizadas

1. **Temporales**:
   - Hora del commit
   - Día de la semana

2. **Mensaje**:
   - Longitud
   - Palabras clave sospechosas

3. **Código**:
   - Archivos modificados
   - Líneas añadidas/eliminadas
   - Ratio de cambios

4. **Archivos**:
   - Presencia de archivos de configuración
   - Presencia de archivos .env

### Importancia de Características

La importancia se calcula como la **reducción total de Gini** que aporta cada característica:

```python
importance(feature) = Σ (reducción_gini_en_divisiones_que_usan_feature)
```

## 🔍 Detección de Credenciales

### Patrones Regex

La aplicación utiliza expresiones regulares compiladas para detectar:

```python
CREDENTIAL_PATTERNS = {
    'aws_access_key': r'AKIA[0-9A-Z]{16}',
    'github_token': r'gh[pousr]_[0-9a-zA-Z]{36}',
    'private_key': r'-----BEGIN (RSA|DSA|EC) PRIVATE KEY-----',
    # ... más patrones
}
```

### Proceso de Detección

1. **Compilación de patrones** (al inicio)
2. **Análisis de diff** (líneas añadidas en commits)
3. **Filtrado de falsos positivos**
4. **Clasificación por severidad**:
   - CRITICAL: AWS keys, private keys
   - HIGH: GitHub tokens, API keys
   - MEDIUM: Otros tipos

## 📈 Visualización de Datos

### Tablas en GUI

La interfaz muestra:
- ID de credencial
- Tipo detectado
- Archivo y línea
- Severidad (con código de color)
- Commit SHA
- Autor y fecha

### Exportación

Todos los resultados se pueden exportar a CSV para análisis externo.

## 🎓 Capítulo de Diseño de Datos (Proyecto de Grado)

### 3.1 Modelo de Datos

#### 3.1.1 Diagrama Entidad-Relación

El modelo de datos se diseñó siguiendo los principios de normalización hasta la 3FN, garantizando la integridad referencial y minimizando la redundancia.

**Entidades principales**:

1. **REPOSITORY**: Representa un repositorio de GitHub
   - Atributos: repo_id, repo_name, repo_owner, repo_url, analysis_date
   - Clave primaria: repo_id
   - Restricción UNIQUE en (repo_owner, repo_name)

2. **COMMIT**: Representa un commit dentro de un repositorio
   - Atributos: commit_id, repo_id, commit_sha, commit_message, author_name, commit_date
   - Clave primaria: commit_id
   - Clave foránea: repo_id → repositories(repo_id)

3. **CREDENTIAL**: Credencial expuesta detectada
   - Atributos: credential_id, commit_id, credential_type, file_path, severity
   - Clave primaria: credential_id
   - Clave foránea: commit_id → commits(commit_id)

#### 3.1.2 Justificación del Diseño

**PostgreSQL** fue elegido por:
- Soporte robusto para transacciones ACID
- Capacidad de manejar grandes volúmenes de datos
- Excelente rendimiento en consultas complejas
- Soporte nativo para JSON (útil para almacenar importancia de características)

**Normalización**:
- Evita redundancia de información de repositorios
- Permite análisis histórico de commits
- Facilita consultas agregadas por repositorio

#### 3.1.3 Índices

Se crearon índices en:
- `commit_sha`: Búsquedas rápidas de commits específicos
- `repo_id` en tabla commits: Join eficiente con repositories
- `commit_id` en credentials: Join eficiente

### 3.2 Diccionario de Datos

[Incluir tablas detalladas con cada campo, tipo de dato, restricciones]

### 3.3 Vistas del Sistema

**v_repository_summary**:
- Propósito: Análisis rápido de estadísticas por repositorio
- Campos: repo_id, total_commits, total_credentials, avg_risk_score

**v_commits_with_credentials**:
- Propósito: Listar todos los commits que contienen credenciales
- Incluye: información de commit, tipo de credencial, severidad

## 🔧 Configuración Avanzada

### Ajustar Parámetros del Modelo

En `config/config.py`:

```python
ML_CONFIG = {
    'test_size': 0.3,          # 30% para prueba
    'random_state': 42,        # Reproducibilidad
    'max_depth': 10,           # Profundidad máxima del árbol
    'min_samples_split': 5,    # Mínimo para dividir nodo
    'criterion': 'gini'        # Usar Gini (CART)
}
```

### Agregar Nuevos Patrones de Credenciales

En `config/config.py`:

```python
CREDENTIAL_PATTERNS = {
    # Agregar tu patrón
    'mi_api_key': r'mi_patron_regex_aqui',
    # ...
}
```

## 🐛 Solución de Problemas

### Error de Conexión a PostgreSQL
```
✗ Error al crear pool de conexiones
```
**Solución**: Verificar que PostgreSQL esté corriendo y las credenciales sean correctas.

### Error de Token de GitHub
```
⚠ Token de GitHub no configurado o inválido
```
**Solución**: Verificar que el token tenga los permisos correctos.

### No hay datos para entrenar ML
```
No hay suficientes datos para entrenar
```
**Solución**: Analizar al menos 10-20 commits antes de entrenar el modelo.

## 📚 Librerías Utilizadas

- **psycopg2**: Conexión con PostgreSQL
- **requests**: Llamadas a GitHub API
- **scikit-learn**: Machine Learning (CART)
- **pandas**: Manipulación de datos
- **numpy**: Operaciones numéricas
- **matplotlib/seaborn**: Visualización
- **re**: Expresiones regulares
- **tkinter**: Interfaz gráfica

## 🤝 Contribuciones

Este es un proyecto de grado. Para sugerencias o mejoras, contactar al autor.

## 📄 Licencia

Proyecto académico - Todos los derechos reservados

## ✍️ Autor

Proyecto de Grado - 2024
Análisis de Repositorios GitHub con Machine Learning

---

**Nota**: Esta aplicación está diseñada con fines educativos y de investigación. El análisis de repositorios debe hacerse respetando los términos de servicio de GitHub y con los permisos apropiados.