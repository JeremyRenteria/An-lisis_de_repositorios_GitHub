"""
Módulo de Machine Learning para clasificar credenciales.
Utiliza Random Forest y TF-IDF para discriminar credenciales reales de falsos positivos.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import pickle
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import ML_CREDENTIAL_CONFIG
import math
from collections import Counter


class CredentialClassifier:
    """Clasificador de credenciales (Real vs Falso Positivo)"""

    def __init__(self):
        """Inicializa el clasificador y su pipeline"""
        self.config = ML_CREDENTIAL_CONFIG
        self.pipeline = None
        self.is_trained = False
        
        # Estas features deben coincidir con extract_features
        self.numeric_features = ['entropy', 'length', 'is_doc_file', 'is_sensitive_file', 'line_length', 'has_suspicious_context']
        self.text_feature = 'context'

    def _build_pipeline(self):
        """Construye el pipeline TF-IDF + Random Forest"""
        # Procesador de texto (TF-IDF)
        text_processor = TfidfVectorizer(
            max_features=self.config['tfidf_max_features'],
            stop_words='english',
            lowercase=True
        )
        
        # Preprocesamiento mixto
        preprocessor = ColumnTransformer(
            transformers=[
                ('text', text_processor, self.text_feature),
                ('num', 'passthrough', self.numeric_features)
            ])
            
        # Pipeline completo
        self.pipeline = Pipeline([
            ('preprocessor', preprocessor),
            ('classifier', RandomForestClassifier(
                n_estimators=self.config['n_estimators'],
                max_depth=self.config['max_depth'],
                min_samples_split=self.config['min_samples_split'],
                max_features=self.config['max_features'],
                random_state=self.config['random_state'],
                class_weight='balanced'
            ))
        ])

    def calculate_entropy(self, text: str) -> float:
        """Calcula la entropía de Shannon de una cadena"""
        if not text: return 0.0
        freq = Counter(text)
        length = len(text)
        return -sum((count / length) * math.log2(count / length) for count in freq.values())

    def extract_features(self, match_text: str, context_line: str, file_path: str) -> dict:
        """Extrae las características para el modelo (texto y numéricas)"""
        # Calcular entropía solo del valor (intentar aislarlo)
        import re
        value_match = re.search(r'[:=\s\'"]+([^\s\'"{}[\],;]{6,})', match_text)
        value = value_match.group(1) if value_match else match_text
        
        file_lower = file_path.lower()
        doc_exts = ['.md', '.rst', '.txt', '.adoc']
        sens_exts = ['.env', '.pem', '.key', '.p12', '.pfx', '.cfg', '.conf']
        suspicious = ['password', 'secret', 'token', 'key', 'auth', 'credential']
        
        return {
            'context': context_line,
            'entropy': self.calculate_entropy(value),
            'length': len(value),
            'is_doc_file': int(any(file_lower.endswith(e) for e in doc_exts)),
            'is_sensitive_file': int(any(e in file_lower for e in sens_exts)),
            'line_length': len(context_line),
            'has_suspicious_context': int(any(s in context_line.lower() for s in suspicious))
        }

    def train(self, df: pd.DataFrame) -> dict:
        """
        Entrena el modelo con un DataFrame que debe contener:
        context, entropy, length, is_doc_file, is_sensitive_file, line_length, has_suspicious_context, label
        """
        if df.empty or len(df) < 10:
            raise ValueError("Datos insuficientes para entrenar")

        self._build_pipeline()
        
        X = df[self.numeric_features + [self.text_feature]]
        y = df['label']

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=self.config['test_size'], 
            random_state=self.config['random_state'], stratify=y
        )

        # Entrenamiento
        self.pipeline.fit(X_train, y_train)
        self.is_trained = True

        # Validación cruzada
        try:
            skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=self.config['random_state'])
            cv_scores = cross_val_score(self.pipeline, X_train, y_train, cv=skf, scoring='f1')
            cv_mean = cv_scores.mean()
        except:
            cv_mean = 0.0

        # Evaluación
        y_pred = self.pipeline.predict(X_test)
        
        return {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1': f1_score(y_test, y_pred, zero_division=0),
            'cv_mean_f1': cv_mean,
            'samples': len(df)
        }

    def predict_single(self, match_text: str, context_line: str, file_path: str) -> dict:
        """Predice si una detección única es real (1) o falso positivo (0)"""
        if not self.is_trained:
            # Si no está entrenado, caemos a un comportamiento seguro basado en entropía
            feats = self.extract_features(match_text, context_line, file_path)
            # Heurística temporal (similar al comportamiento anterior pero encapsulado)
            score = 0.5
            if feats['entropy'] > 3.5: score += 0.3
            if feats['is_doc_file']: score -= 0.4
            if feats['is_sensitive_file']: score += 0.2
            
            is_valid = score >= 0.5
            return {
                'is_credential': is_valid,
                'confidence': max(0.0, min(1.0, score)),
                'entropy': feats['entropy']
            }

        # Extracción de características
        features = self.extract_features(match_text, context_line, file_path)
        df = pd.DataFrame([features])
        
        # Predicción
        pred = self.pipeline.predict(df)[0]
        prob = self.pipeline.predict_proba(df)[0]
        
        # Prob[1] es la probabilidad de ser clase 1 (credencial real)
        confidence = prob[1] if len(prob) > 1 else (1.0 if pred == 1 else 0.0)
        
        return {
            'is_credential': bool(pred == 1),
            'confidence': float(confidence),
            'entropy': features['entropy']
        }
        
    def generate_synthetic_data(self):
        """Genera un dataset sintético inicial para que el modelo funcione desde cero"""
        import random
        import string
        
        data = []
        # Credenciales reales
        for _ in range(100):
            real_key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            context = f"export API_KEY='{real_key}'"
            feats = self.extract_features(real_key, context, "config.py")
            feats['label'] = 1
            data.append(feats)
            
        # Falsos positivos
        for _ in range(100):
            fake_key = "your_api_key_here"
            context = f"API_KEY = '{fake_key}' # Change this"
            feats = self.extract_features(fake_key, context, "README.md")
            feats['label'] = 0
            data.append(feats)
            
        return pd.DataFrame(data)

# Instancia global
ml_credential_classifier = CredentialClassifier()

# Autotraining inicial (para que funcione out-of-the-box sin fallar)
try:
    df_synthetic = ml_credential_classifier.generate_synthetic_data()
    ml_credential_classifier.train(df_synthetic)
    print("[OK] Clasificador de Credenciales (Random Forest) pre-entrenado con datos sintéticos")
except Exception as e:
    print(f"[ERROR] Error entrenando RF sintético: {e}")
