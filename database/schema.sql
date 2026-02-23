-- Script de creación de base de datos para GitHub Analyzer
-- PostgreSQL

-- Crear base de datos
CREATE DATABASE github_analyzer;

-- Conectar a la base de datos
\c github_analyzer;

-- Tabla de repositorios analizados
CREATE TABLE repositories (
    repo_id SERIAL PRIMARY KEY,
    repo_name VARCHAR(255) NOT NULL,
    repo_owner VARCHAR(255) NOT NULL,
    repo_url TEXT NOT NULL,
    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_commits INTEGER DEFAULT 0,
    total_credentials_found INTEGER DEFAULT 0,
    risk_level VARCHAR(50),
    UNIQUE(repo_owner, repo_name)
);

-- Tabla de commits analizados
CREATE TABLE commits (
    commit_id SERIAL PRIMARY KEY,
    repo_id INTEGER REFERENCES repositories(repo_id) ON DELETE CASCADE,
    commit_sha VARCHAR(40) NOT NULL,
    commit_message TEXT,
    author_name VARCHAR(255),
    author_email VARCHAR(255),
    commit_date TIMESTAMP,
    files_changed INTEGER DEFAULT 0,
    additions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0,
    has_credentials BOOLEAN DEFAULT FALSE,
    risk_score FLOAT,
    UNIQUE(commit_sha)
);

-- Tabla de credenciales detectadas
CREATE TABLE credentials_detected (
    credential_id SERIAL PRIMARY KEY,
    commit_id INTEGER REFERENCES commits(commit_id) ON DELETE CASCADE,
    credential_type VARCHAR(100) NOT NULL,
    file_path TEXT,
    line_number INTEGER,
    matched_pattern TEXT,
    detection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    severity VARCHAR(20) DEFAULT 'HIGH'
);

-- Tabla de características de commits para ML
CREATE TABLE commit_features (
    feature_id SERIAL PRIMARY KEY,
    commit_id INTEGER REFERENCES commits(commit_id) ON DELETE CASCADE,
    has_suspicious_keywords BOOLEAN DEFAULT FALSE,
    commit_hour INTEGER,
    commit_day_of_week INTEGER,
    message_length INTEGER,
    files_modified INTEGER,
    code_additions INTEGER,
    code_deletions INTEGER,
    has_config_files BOOLEAN DEFAULT FALSE,
    has_env_files BOOLEAN DEFAULT FALSE,
    regex_detected_count INTEGER DEFAULT 0,
    max_regex_severity INTEGER DEFAULT 0,
    is_sensitive_file BOOLEAN DEFAULT FALSE,
    prediction_label INTEGER,  -- 0: seguro, 1: riesgoso
    prediction_confidence FLOAT
);

-- Tabla de resultados del modelo ML
CREATE TABLE ml_model_results (
    model_id SERIAL PRIMARY KEY,
    training_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_accuracy FLOAT,
    precision_score FLOAT,
    recall_score FLOAT,
    f1_score FLOAT,
    gini_importance TEXT,  -- JSON con importancia de características
    total_samples INTEGER,
    total_features INTEGER
);

-- Índices para mejorar el rendimiento
CREATE INDEX idx_repo_name ON repositories(repo_name);
CREATE INDEX idx_commit_sha ON commits(commit_sha);
CREATE INDEX idx_commit_repo ON commits(repo_id);
CREATE INDEX idx_credential_commit ON credentials_detected(commit_id);
CREATE INDEX idx_features_commit ON commit_features(commit_id);

-- Vista para análisis rápido
CREATE VIEW v_repository_summary AS
SELECT 
    r.repo_id,
    r.repo_name,
    r.repo_owner,
    r.analysis_date,
    r.total_commits,
    r.total_credentials_found,
    r.risk_level,
    COUNT(DISTINCT c.commit_id) as commits_analyzed,
    COUNT(DISTINCT cd.credential_id) as credentials_count,
    AVG(c.risk_score) as avg_risk_score
FROM repositories r
LEFT JOIN commits c ON r.repo_id = c.repo_id
LEFT JOIN credentials_detected cd ON c.commit_id = cd.commit_id
GROUP BY r.repo_id, r.repo_name, r.repo_owner, r.analysis_date, 
         r.total_commits, r.total_credentials_found, r.risk_level;

-- Vista para commits con credenciales
CREATE VIEW v_commits_with_credentials AS
SELECT 
    c.commit_sha,
    c.commit_message,
    c.author_name,
    c.commit_date,
    r.repo_name,
    r.repo_owner,
    cd.credential_type,
    cd.file_path,
    cd.severity,
    c.risk_score
FROM commits c
INNER JOIN repositories r ON c.repo_id = r.repo_id
INNER JOIN credentials_detected cd ON c.commit_id = cd.commit_id
ORDER BY c.commit_date DESC;

-- Comentarios en las tablas
COMMENT ON TABLE repositories IS 'Almacena información de repositorios analizados';
COMMENT ON TABLE commits IS 'Almacena información detallada de commits';
COMMENT ON TABLE credentials_detected IS 'Almacena credenciales expuestas detectadas';
COMMENT ON TABLE commit_features IS 'Características extraídas de commits para ML';
COMMENT ON TABLE ml_model_results IS 'Resultados y métricas del modelo de machine learning';