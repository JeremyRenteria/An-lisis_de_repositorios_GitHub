"""
Módulo de Machine Learning para agrupación de repositorios.
Utiliza K-Means para agrupar repositorios por perfiles de riesgo basado en sus métricas.
"""

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import CLUSTERING_CONFIG


class RepositoryClusterer:
    """Agrupación de repositorios por perfil de riesgo usando K-Means"""

    def __init__(self):
        self.config = CLUSTERING_CONFIG
        self.k = self.config['n_clusters']  # 4 clusters (LOW, MEDIUM, HIGH, CRITICAL)
        
        self.model = KMeans(
            n_clusters=self.k,
            random_state=self.config['random_state'],
            n_init=self.config['n_init']
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        
        # Mapeo de clusters a niveles de riesgo
        self.cluster_to_risk = {}
        
        self.feature_cols = [
            'total_commits',
            'commits_analyzed',
            'credentials_count',
            'avg_risk_score',
            'avg_confidence_score'
        ]

    def train_and_predict(self, df: pd.DataFrame) -> dict:
        """
        Entrena el K-Means y devuelve un diccionario {repo_id: risk_level}
        Se asume que iterará sobre v_repository_summary.
        """
        if df.empty or len(df) < self.k:
            return {}

        # 1. Preparar datos
        # Agregar columnas si la VISTA de la DB está desactualizada
        for col in self.feature_cols:
            if col not in df.columns:
                df[col] = 0.0

        # Llenar NaNs y extraer features
        X_df = df[self.feature_cols].copy().fillna(0)
        
        # Escalar datos (K-Means es sensible a escalas)
        X_scaled = self.scaler.fit_transform(X_df)
        
        # 2. Entrenar y predecir
        clusters = self.model.fit_predict(X_scaled)
        
        # 3. Mapear clusters a etiquetas (LOW, MEDIUM, HIGH, CRITICAL)
        # Ordenamos los centros de cluster por "riesgo"
        # Un centroide con más credenciales y mayor avg_risk_score es más riesgoso
        centers = self.model.cluster_centers_
        
        # Invertimos la transformación para interpretar los centros
        centers_original = self.scaler.inverse_transform(centers)
        
        # Calculamos un "score" para cada cluster basado en credenciales y avg_risk
        # Índice 2: credentials_count, Índice 3: avg_risk_score
        cluster_scores = [(i, centers_original[i][2] * 10 + centers_original[i][3]) 
                          for i in range(self.k)]
        
        # Ordenar clusters de menor a mayor riesgo
        cluster_scores.sort(key=lambda x: x[1])
        
        labels = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        self.cluster_to_risk = {
            cluster_id: labels[idx] for idx, (cluster_id, _) in enumerate(cluster_scores)
        }
        
        self.is_trained = True
        
        # 4. Construir resultado: {repo_id: risk_level}
        result = {}
        for idx, repo_id in enumerate(df['repo_id']):
            cluster_id = clusters[idx]
            result[repo_id] = self.cluster_to_risk[cluster_id]
            
        return result

    def get_risk_level(self, repo_stats: dict) -> str:
        """Determina el nivel de riesgo en base a métricas manuales o predice el cluster"""
        total_commits = repo_stats.get('total_commits', 0)
        credentials_count = repo_stats.get('credentials_count', 0)
        
        # Fallback heurístico si no está entrenado u otros problemas
        if not self.is_trained:
            if credentials_count == 0:
                return 'LOW'
            ratio = credentials_count / max(total_commits, 1)
            if ratio > 0.1:   return 'CRITICAL'
            if ratio > 0.05:  return 'HIGH'
            if ratio > 0.01:  return 'MEDIUM'
            return 'LOW'
            
        # Si está entrenado, predecimos
        X = [
            repo_stats.get('total_commits', 0),
            repo_stats.get('commits_analyzed', 0),
            repo_stats.get('credentials_count', 0),
            repo_stats.get('avg_risk_score', 0.0),
            repo_stats.get('avg_confidence_score', 0.0)
        ]
        
        X_scaled = self.scaler.transform([X])
        cluster_id = self.model.predict(X_scaled)[0]
        
        return self.cluster_to_risk.get(cluster_id, 'UNKNOWN')


# Instancia global
ml_repo_clusterer = RepositoryClusterer()
