"""
Módulo de Machine Learning para análisis de commits
Utiliza Árboles de Decisión con algoritmo CART e índice de Gini
"""
import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, 
    f1_score, confusion_matrix, classification_report
)
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import pickle
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import ML_CONFIG
from utils.credential_detector import credential_detector


class CommitClassifier:
    """
    Clasificador de commits usando Árbol de Decisión CART con Gini
    """
    
    def __init__(self):
        """Inicializa el clasificador"""
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        self.feature_importance = {}
        self.training_history = []
        
        # Configuración del modelo CART
        self.config = ML_CONFIG
    
    def extract_features(self, commits_df):
        """
        Extrae características de commits para el modelo
        
        Args:
            commits_df (pd.DataFrame): DataFrame con información de commits
            
        Returns:
            pd.DataFrame: DataFrame con características extraídas
        """
        features_list = []
        
        for idx, commit in commits_df.iterrows():
            # Características temporales
            commit_date = pd.to_datetime(commit.get('commit_date', datetime.now()))
            commit_hour = commit_date.hour
            commit_day = commit_date.weekday()
            
            # Características del mensaje
            message = str(commit.get('commit_message', ''))
            message_length = len(message)
            has_suspicious_keywords = self._check_suspicious_keywords(message)
            
            # Características de archivos modificados
            files_changed = commit.get('files_changed', 0)
            additions = commit.get('additions', 0)
            deletions = commit.get('deletions', 0)
            total_changes = additions + deletions
            
            # Ratio de cambios
            change_ratio = additions / (deletions + 1)  # +1 para evitar división por cero
            
            # Características binarias
            has_config_files = 0  # Se determinaría analizando nombres de archivos
            has_env_files = 0
            
            # Label (si tiene credenciales)
            has_credentials = int(commit.get('has_credentials', False))
            
            # --- INTEGRACIÓN REGEX + ML ---
            # Realizar detección con regex para obtener características adicionales
            regex_detections = credential_detector.detect_in_text(message)
            regex_count = len(regex_detections)
            
            # Mapear severidad máxima a valor numérico
            severity_map = {'CRITICAL': 3, 'HIGH': 2, 'MEDIUM': 1, 'NONE': 0}
            max_severity = 0
            for det in regex_detections:
                sev_val = severity_map.get(det['severity'], 0)
                if sev_val > max_severity:
                    max_severity = sev_val
            
            # Verificar archivos sensibles
            is_sens_file = 1 if credential_detector.is_sensitive_file(commit.get('file_path', '')) else 0
            
            features = {
                'commit_hour': commit_hour,
                'commit_day_of_week': commit_day,
                'message_length': message_length,
                'has_suspicious_keywords': int(has_suspicious_keywords),
                'regex_detected_count': regex_count,      # Nueva característica
                'max_regex_severity': max_severity,       # Nueva característica
                'is_sensitive_file': is_sens_file,        # Nueva característica
                'files_modified': files_changed,
                'code_additions': additions,
                'code_deletions': deletions,
                'total_changes': total_changes,
                'change_ratio': change_ratio,
                'has_config_files': has_config_files,
                'has_env_files': has_env_files,
                'label': has_credentials
            }
            
            features_list.append(features)
        
        return pd.DataFrame(features_list)
    
    def _check_suspicious_keywords(self, text):
        """
        Verifica si el texto contiene palabras clave sospechosas
        
        Args:
            text (str): Texto a analizar
            
        Returns:
            bool: True si contiene palabras sospechosas
        """
        suspicious_words = [
            'password', 'secret', 'token', 'api_key', 'credential',
            'auth', 'private', 'key', 'config', 'env'
        ]
        
        text_lower = text.lower()
        return any(word in text_lower for word in suspicious_words)
    
    def prepare_data(self, features_df):
        """
        Prepara los datos para entrenamiento
        
        Args:
            features_df (pd.DataFrame): DataFrame con características
            
        Returns:
            tuple: (X_train, X_test, y_train, y_test)
        """
        # Separar características y labels
        X = features_df.drop('label', axis=1)
        y = features_df['label']
        
        # Guardar nombres de características
        self.feature_names = X.columns.tolist()
        
        # Verificar balance de clases
        class_counts = y.value_counts()
        print(f"[INFO] Distribución de clases ORIGINAL: {dict(class_counts)}")
        
        # Ajustar test_size si alguna clase es muy pequeña
        test_size = self.config['test_size']
        min_class_count = class_counts.min()
        
        if min_class_count < 4:
            # Si la clase minoritaria es muy pequeña, reducir test_size
            test_size = min(0.2, 1 - (min_class_count * 0.5) / len(y))
            print(f"[WARNING] Clase minoritaria muy pequeña. Ajustando test_size a {test_size:.2f}")
        
        # Dividir en entrenamiento y prueba
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, 
            test_size=test_size,
            random_state=self.config['random_state'],
            stratify=y
        )
        
        # Aplicar SMOTE solo en datos de entrenamiento
        # (importante: nunca en datos de prueba para evitar data leakage)
        try:
            smote = SMOTE(random_state=self.config['random_state'], k_neighbors=3)
            X_train_smote, y_train_smote = smote.fit_resample(X_train, y_train)
            
            class_counts_after = pd.Series(y_train_smote).value_counts()
            print(f"[INFO] Distribución de clases DESPUÉS de SMOTE: {dict(class_counts_after)}")
            print(f"[INFO] ✓ SMOTE aplicado exitosamente")
            
            X_train = X_train_smote
            y_train = y_train_smote
        except Exception as smote_error:
            print(f"[WARNING] Error al aplicar SMOTE: {smote_error}")
            print(f"[INFO] Continuando sin SMOTE")
        
        # Escalar características
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Convertir de vuelta a DataFrame
        X_train = pd.DataFrame(X_train_scaled, columns=self.feature_names)
        X_test = pd.DataFrame(X_test_scaled, columns=self.feature_names)
        
        return X_train, X_test, y_train, y_test
    
    def train(self, X_train, y_train):
        """
        Entrena el modelo de Árbol de Decisión usando CART con Gini
        
        Args:
            X_train (pd.DataFrame): Características de entrenamiento
            y_train (pd.Series): Labels de entrenamiento
            
        Returns:
            dict: Métricas de entrenamiento
        """
        print("🌳 Entrenando Árbol de Decisión CART con criterio Gini...")
        
        # Crear modelo de Árbol de Decisión con CART
        self.model = DecisionTreeClassifier(
            criterion='gini',  # Usar índice de Gini (CART)
            max_depth=self.config['max_depth'],
            min_samples_split=self.config['min_samples_split'],
            random_state=self.config['random_state'],
            class_weight='balanced'  # Para manejar desbalance de clases
        )
        
        # Entrenar el modelo
        self.model.fit(X_train, y_train)
        
        # Calcular importancia de características usando Gini
        self.feature_importance = dict(zip(
            self.feature_names, 
            self.model.feature_importances_
        ))
        
        # Ordenar por importancia
        self.feature_importance = dict(
            sorted(self.feature_importance.items(), 
                   key=lambda x: x[1], reverse=True)
        )
        
        # Validación cruzada - manejo robusto de datos desbalanceados
        class_counts = y_train.value_counts()
        min_class_count = class_counts.min()
        
        print(f"[INFO] Distribución de clases en entrenamiento: {dict(class_counts)}")
        
        cv_mean_f1 = 0.0
        cv_std_f1 = 0.0
        num_folds = 0
        
        try:
            # Intentar validación cruzada normal
            # El número de folds no puede exceder el tamaño de la clase más pequeña
            if min_class_count >= 3:
                num_folds = min(5, min_class_count)
                print(f"[INFO] Usando {num_folds} folds para validación cruzada")
                
                cv_scores = cross_val_score(
                    self.model, X_train, y_train, 
                    cv=num_folds, scoring='f1', zero_division=0
                )
                cv_mean_f1 = float(cv_scores.mean())
                cv_std_f1 = float(cv_scores.std())
            else:
                # Para datos muy limitados, usar validación manual en el conjunto de entrenamiento
                print(f"[WARNING] Clase minoritaria pequeña ({min_class_count} muestras)")
                print(f"[INFO] Usando validación en conjunto de entrenamiento")
                
                y_pred = self.model.predict(X_train)
                cv_mean_f1 = float(f1_score(y_train, y_pred, zero_division=0))
                cv_std_f1 = 0.0
                num_folds = 1
                
        except Exception as cv_error:
            print(f"[WARNING] Error en validación cruzada: {cv_error}")
            print(f"[INFO] Usando validación en conjunto de entrenamiento")
            
            y_pred = self.model.predict(X_train)
            cv_mean_f1 = float(f1_score(y_train, y_pred, zero_division=0))
            cv_std_f1 = 0.0
            num_folds = 1
        
        metrics = {
            'training_samples': len(X_train),
            'cv_mean_f1': cv_mean_f1,
            'cv_std_f1': cv_std_f1,
            'cv_folds': num_folds,
            'feature_importance': self.feature_importance
        }
        
        print(f"✓ Modelo entrenado con {len(X_train)} muestras")
        print(f"✓ F1-Score: {cv_mean_f1:.4f} (+/- {cv_std_f1:.4f})")
        
        return metrics
    
    def evaluate(self, X_test, y_test):
        """
        Evalúa el modelo
        
        Args:
            X_test (pd.DataFrame): Características de prueba
            y_test (pd.Series): Labels de prueba
            
        Returns:
            dict: Métricas de evaluación
        """
        if self.model is None:
            raise ValueError("El modelo no ha sido entrenado")
        
        # Predicciones
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)
        
        # Calcular métricas
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1': f1_score(y_test, y_pred, zero_division=0),
            'confusion_matrix': confusion_matrix(y_test, y_pred),
            'classification_report': classification_report(y_test, y_pred)
        }
        
        print("\n📊 Métricas de Evaluación:")
        print(f"   Accuracy:  {metrics['accuracy']:.4f}")
        print(f"   Precision: {metrics['precision']:.4f}")
        print(f"   Recall:    {metrics['recall']:.4f}")
        print(f"   F1-Score:  {metrics['f1']:.4f}")
        
        return metrics
    
    def predict(self, features_df):
        """
        Realiza predicciones sobre nuevos datos
        
        Args:
            features_df (pd.DataFrame): Características a predecir
            
        Returns:
            tuple: (predicciones, probabilidades)
        """
        if self.model is None:
            raise ValueError("El modelo no ha sido entrenado")
        
        # Asegurar que tiene las columnas correctas
        X = features_df[self.feature_names]
        
        # Escalar
        X_scaled = self.scaler.transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=self.feature_names)
        
        # Predecir
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)
        
        return predictions, probabilities
    
    def get_gini_impurity_explanation(self):
        """
        Genera explicación sobre cómo funciona el índice de Gini
        
        Returns:
            str: Explicación del índice de Gini
        """
        explanation = """
        🌳 ÍNDICE DE GINI EN ÁRBOL DE DECISIÓN CART
        
        El índice de Gini mide la impureza de un nodo. Se calcula como:
        
        Gini(node) = 1 - Σ(p_i²)
        
        Donde p_i es la proporción de muestras de la clase i en el nodo.
        
        - Gini = 0: Nodo puro (todas las muestras de la misma clase)
        - Gini = 0.5: Máxima impureza (50% de cada clase en clasificación binaria)
        
        El algoritmo CART (Classification and Regression Trees):
        1. Calcula el Gini de cada posible división
        2. Elige la división que minimiza la impureza ponderada
        3. Repite recursivamente hasta alcanzar criterios de parada
        
        Importancia de características basada en Gini:
        - Se calcula como la reducción promedio de Gini que aporta cada característica
        - Características con mayor reducción de Gini son más importantes
        """
        
        if self.feature_importance:
            explanation += "\n\n📈 IMPORTANCIA DE CARACTERÍSTICAS (basada en Gini):\n"
            for feature, importance in list(self.feature_importance.items())[:5]:
                explanation += f"   {feature}: {importance:.4f}\n"
        
        return explanation
    
    def visualize_tree(self, max_depth=3, output_path='decision_tree.png'):
        """
        Visualiza el árbol de decisión
        
        Args:
            max_depth (int): Profundidad máxima a mostrar
            output_path (str): Ruta para guardar la imagen
        """
        if self.model is None:
            raise ValueError("El modelo no ha sido entrenado")
        
        plt.figure(figsize=(20, 10))
        plot_tree(
            self.model,
            max_depth=max_depth,
            feature_names=self.feature_names,
            class_names=['Seguro', 'Riesgoso'],
            filled=True,
            rounded=True,
            fontsize=10
        )
        plt.title('Árbol de Decisión CART (primeros niveles)', fontsize=16)
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Árbol visualizado en: {output_path}")
    
    def get_tree_rules(self):
        """
        Obtiene las reglas del árbol en formato texto
        
        Returns:
            str: Reglas del árbol
        """
        if self.model is None:
            raise ValueError("El modelo no ha sido entrenado")
        
        tree_rules = export_text(
            self.model,
            feature_names=self.feature_names
        )
        
        return tree_rules
    
    def save_model(self, filepath='commit_classifier.pkl'):
        """
        Guarda el modelo entrenado
        
        Args:
            filepath (str): Ruta donde guardar el modelo
        """
        if self.model is None:
            raise ValueError("El modelo no ha sido entrenado")
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'feature_importance': self.feature_importance,
            'config': self.config
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        print(f"✓ Modelo guardado en: {filepath}")
    
    def load_model(self, filepath='commit_classifier.pkl'):
        """
        Carga un modelo previamente entrenado
        
        Args:
            filepath (str): Ruta del modelo a cargar
        """
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.feature_importance = model_data['feature_importance']
        self.config = model_data.get('config', self.config)
        
        print(f"✓ Modelo cargado desde: {filepath}")


# Instancia global del clasificador
commit_classifier = CommitClassifier()