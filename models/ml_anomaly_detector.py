"""
Módulo de Machine Learning para detección de anomalías.
Utiliza Isolation Forest para identificar commits inusuales que representan alto riesgo.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import ANOMALY_CONFIG


class AnomalyDetector:
    """Detector de anomalías en commits para calcular el risk_score de forma inteligente"""

    def __init__(self):
        self.config = ANOMALY_CONFIG
        self.model = IsolationForest(
            contamination=self.config['contamination'],
            random_state=self.config['random_state'],
            n_estimators=self.config['n_estimators']
        )
        self.is_trained = False
        self.feature_cols = [
            'additions', 'deletions', 'files_changed',
            'has_credentials'
        ]

    def _extract_features(self, commit_data: dict) -> list:
        """Extrae características numéricas de un commit para el modelo"""
        return [
            commit_data.get('additions', 0),
            commit_data.get('deletions', 0),
            commit_data.get('files_changed', 0),
            int(commit_data.get('has_credentials', False))
        ]

    def train(self, df: pd.DataFrame):
        """Entrena el Isolation Forest con un DataFrame histórico"""
        if df.empty or len(df) < 10:
            return False

        X = df[self.feature_cols].fillna(0)
        self.model.fit(X)
        self.is_trained = True
        return True

    def calculate_risk_score(self, commit_data: dict) -> float:
        """
        Calcula el score de riesgo basado en si es una anomalía.
        Devuelve un score entre 0.0 y 1.0.
        """
        # Si no hay modelo entrenado, calculamos heurísticamente (fallback)
        if not self.is_trained:
            score = 0.0
            if commit_data.get('has_credentials'):
                score += 0.5 + (commit_data.get('num_credentials', 0) * 0.1)
            if commit_data.get('additions', 0) > 100:
                score += 0.1
            if commit_data.get('files_changed', 0) > 10:
                score += 0.1
            return min(score, 1.0)

        # Si el modelo está entrenado, predecimos la anomalía
        features = [self._extract_features(commit_data)]
        
        # predict() devuelve 1 para inliers (normal) y -1 para outliers (anómalos)
        # decision_function() devuelve puntajes de anomalía (menor = más anómalo)
        anomaly_score_raw = self.model.decision_function(features)[0]
        
        # Mapear a rango 0-1 (donde 1 = alto riesgo / anómalo, 0 = bajo riesgo / normal)
        # Los scores del decision_function suelen estar en [-0.5, 0.5] aprox
        risk_score = 0.5 - anomaly_score_raw  # Invertir para que outliers sean > 0.5
        
        # Clipping seguro
        risk_score = max(0.0, min(1.0, risk_score))
        
        # Ponderación adicional crítica: si hay credenciales, multiplicar factor
        if commit_data.get('has_credentials'):
            risk_score = min(1.0, risk_score + 0.3)
            
        return float(risk_score)


# Instancia global
ml_anomaly_detector = AnomalyDetector()
