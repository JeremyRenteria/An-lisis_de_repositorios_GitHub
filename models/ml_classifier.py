"""
Módulo de Machine Learning para análisis de commits.
Utiliza Árboles de Decisión con algoritmo CART e índice de Gini.

Correcciones aplicadas:
  1. Se eliminó StandardScaler (innecesario para árboles de decisión).
  2. Se agregaron confidence_score y entropy como features del detector.
  3. is_sensitive_file ahora se calcula correctamente desde los archivos del commit.
  4. cross_val_score ya no pasa zero_division (parámetro incorrecto para esa función).
  5. imbalanced-learn ahora está en requirements.txt como dependencia explícita.
"""

import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, confusion_matrix, classification_report
)
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
    Clasificador de commits usando Árbol de Decisión CART con Gini.
    """

    def __init__(self):
        """Inicializa el clasificador"""
        self.model = None
        # StandardScaler eliminado: los árboles de decisión son invariantes al escalado.
        # Usarlo generaba complejidad innecesaria y problemas al cargar modelos desde disco.
        self.feature_names = []
        self.feature_importance = {}
        self.training_history = []
        self.config = ML_CONFIG

    # ------------------------------------------------------------------
    # EXTRACCIÓN DE FEATURES
    # ------------------------------------------------------------------

    def extract_features(self, commits_df: pd.DataFrame) -> pd.DataFrame:
        """
        Extrae características de commits para el modelo.

        Novedades respecto a la versión anterior:
          - avg_confidence_score: promedio del confidence_score de las detecciones del detector.
          - max_entropy: entropía máxima entre las detecciones (indica cuán "real" es la cadena).
          - is_sensitive_file: ahora usa la columna 'file_paths' (lista de archivos del commit)
            en lugar de 'file_path' (campo inexistente en commits).

        Args:
            commits_df: DataFrame con información de commits.

        Returns:
            DataFrame con características extraídas, incluyendo columna 'label'.
        """
        features_list = []

        for _, commit in commits_df.iterrows():
            # --- Temporales ---
            commit_date = pd.to_datetime(commit.get('commit_date', datetime.now()))
            commit_hour = commit_date.hour
            commit_day  = commit_date.weekday()

            # --- Mensaje ---
            message = str(commit.get('commit_message', ''))
            message_length          = len(message)
            has_suspicious_keywords = self._check_suspicious_keywords(message)

            # --- Código ---
            files_changed  = commit.get('files_changed', 0)
            additions      = commit.get('additions', 0)
            deletions      = commit.get('deletions', 0)
            total_changes  = additions + deletions
            change_ratio   = additions / (deletions + 1)

            # --- Archivos sensibles ---
            # CORRECCIÓN: los commits NO tienen 'file_path' (campo de credenciales).
            # En su lugar usamos 'file_paths', una lista de archivos del commit,
            # que debe ser provista por quien llama a este método.
            file_paths_raw = commit.get('file_paths', [])
            if isinstance(file_paths_raw, str):
                # Si viene serializado como string separado por comas
                file_paths_raw = [p.strip() for p in file_paths_raw.split(',') if p.strip()]

            has_config_files = any(
                credential_detector.is_sensitive_file(fp) for fp in file_paths_raw
            )
            has_env_files = any('.env' in fp.lower() for fp in file_paths_raw)
            is_sens_file  = has_config_files

            # --- Detección regex en mensaje ---
            regex_detections = credential_detector.detect_in_text(message)
            regex_count = len(regex_detections)

            severity_map = {'CRITICAL': 3, 'HIGH': 2, 'MEDIUM': 1, 'NONE': 0}
            max_severity = max(
                (severity_map.get(d['severity'], 0) for d in regex_detections),
                default=0
            )

            # --- NUEVAS FEATURES: confidence_score y entropy del detector ---
            # Estas características aprovechan el nuevo pipeline de scoring del
            # credential_detector mejorado. Si no hay detecciones, ambas valen 0.
            avg_confidence = (
                sum(d.get('confidence_score', 0.0) for d in regex_detections) / len(regex_detections)
                if regex_detections else 0.0
            )
            max_entropy = max(
                (d.get('entropy', 0.0) for d in regex_detections),
                default=0.0
            )

            # --- Label ---
            has_credentials = int(commit.get('has_credentials', False))

            features_list.append({
                'commit_hour':              commit_hour,
                'commit_day_of_week':       commit_day,
                'message_length':           message_length,
                'has_suspicious_keywords':  int(has_suspicious_keywords),
                'regex_detected_count':     regex_count,
                'max_regex_severity':       max_severity,
                'avg_confidence_score':     round(avg_confidence, 4),   # NUEVO
                'max_entropy':              round(max_entropy, 4),       # NUEVO
                'is_sensitive_file':        int(is_sens_file),
                'files_modified':           files_changed,
                'code_additions':           additions,
                'code_deletions':           deletions,
                'total_changes':            total_changes,
                'change_ratio':             round(change_ratio, 4),
                'has_config_files':         int(has_config_files),
                'has_env_files':            int(has_env_files),
                'label':                    has_credentials,
            })

        return pd.DataFrame(features_list)

    def _check_suspicious_keywords(self, text: str) -> bool:
        """Verifica si el texto contiene palabras clave sospechosas."""
        suspicious_words = [
            'password', 'secret', 'token', 'api_key', 'credential',
            'auth', 'private', 'key', 'config', 'env'
        ]
        text_lower = text.lower()
        return any(word in text_lower for word in suspicious_words)

    # ------------------------------------------------------------------
    # PREPARACIÓN DE DATOS
    # ------------------------------------------------------------------

    def prepare_data(self, features_df: pd.DataFrame):
        """
        Prepara los datos para entrenamiento.

        - Separa X e y.
        - Ajusta test_size si la clase minoritaria es muy pequeña.
        - Aplica SMOTE solo en datos de entrenamiento (evita data leakage).
        - NO aplica StandardScaler (innecesario para árboles de decisión).

        Returns:
            tuple: (X_train, X_test, y_train, y_test)
        """
        X = features_df.drop('label', axis=1)
        y = features_df['label']

        self.feature_names = X.columns.tolist()

        class_counts   = y.value_counts()
        min_class_count = class_counts.min()
        print(f"[INFO] Distribución de clases ORIGINAL: {dict(class_counts)}")

        # Ajustar test_size si la clase minoritaria es muy pequeña
        test_size = self.config['test_size']
        if min_class_count < 4:
            test_size = min(0.2, 1 - (min_class_count * 0.5) / len(y))
            print(f"[WARNING] Clase minoritaria pequeña. Ajustando test_size → {test_size:.2f}")

        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=test_size,
            random_state=self.config['random_state'],
            stratify=y
        )

        # SMOTE solo en entrenamiento
        try:
            smote = SMOTE(random_state=self.config['random_state'], k_neighbors=3)
            X_train, y_train = smote.fit_resample(X_train, y_train)
            print(f"[INFO] Distribución DESPUÉS de SMOTE: {dict(pd.Series(y_train).value_counts())}")
            print(f"[INFO] ✓ SMOTE aplicado exitosamente")
        except Exception as smote_error:
            print(f"[WARNING] SMOTE no aplicado: {smote_error}")

        # Sin escalado — los árboles de decisión no lo necesitan
        return X_train, X_test, y_train, y_test

    # ------------------------------------------------------------------
    # ENTRENAMIENTO
    # ------------------------------------------------------------------

    def train(self, X_train, y_train) -> dict:
        """
        Entrena el modelo de Árbol de Decisión CART con criterio Gini.

        Returns:
            dict: Métricas de entrenamiento (cv_mean_f1, feature_importance, etc.)
        """
        print("🌳 Entrenando Árbol de Decisión CART con criterio Gini...")

        self.model = DecisionTreeClassifier(
            criterion='gini',
            max_depth=self.config['max_depth'],
            min_samples_split=self.config['min_samples_split'],
            random_state=self.config['random_state'],
            class_weight='balanced'
        )
        self.model.fit(X_train, y_train)

        # Importancia de características (basada en reducción de Gini)
        self.feature_importance = dict(
            sorted(
                zip(self.feature_names, self.model.feature_importances_),
                key=lambda x: x[1],
                reverse=True
            )
        )

        # --- Validación cruzada ---
        # CORRECCIÓN: cross_val_score no acepta zero_division. Usamos StratifiedKFold
        # para manejar correctamente el desbalance de clases.
        class_counts    = pd.Series(y_train).value_counts()
        min_class_count = class_counts.min()
        cv_mean_f1 = 0.0
        cv_std_f1  = 0.0
        num_folds  = 0

        try:
            if min_class_count >= 3:
                num_folds = min(5, int(min_class_count))
                print(f"[INFO] Usando {num_folds} folds para validación cruzada")

                skf = StratifiedKFold(n_splits=num_folds, shuffle=True,
                                      random_state=self.config['random_state'])
                cv_scores = cross_val_score(
                    self.model, X_train, y_train,
                    cv=skf, scoring='f1'          # sin zero_division aquí
                )
                cv_mean_f1 = float(cv_scores.mean())
                cv_std_f1  = float(cv_scores.std())
            else:
                print(f"[WARNING] Clase minoritaria muy pequeña ({min_class_count} muestras)")
                print(f"[INFO] Usando validación en conjunto de entrenamiento")
                y_pred     = self.model.predict(X_train)
                cv_mean_f1 = float(f1_score(y_train, y_pred, zero_division=0))
                num_folds  = 1

        except Exception as cv_error:
            print(f"[WARNING] Error en validación cruzada: {cv_error}")
            y_pred     = self.model.predict(X_train)
            cv_mean_f1 = float(f1_score(y_train, y_pred, zero_division=0))
            num_folds  = 1

        metrics = {
            'training_samples':   len(X_train),
            'cv_mean_f1':         cv_mean_f1,
            'cv_std_f1':          cv_std_f1,
            'cv_folds':           num_folds,
            'feature_importance': self.feature_importance
        }

        print(f"✓ Modelo entrenado con {len(X_train)} muestras")
        print(f"✓ F1-Score CV: {cv_mean_f1:.4f} (+/- {cv_std_f1:.4f})")

        return metrics

    # ------------------------------------------------------------------
    # EVALUACIÓN Y PREDICCIÓN
    # ------------------------------------------------------------------

    def evaluate(self, X_test, y_test) -> dict:
        """Evalúa el modelo en el conjunto de prueba."""
        if self.model is None:
            raise ValueError("El modelo no ha sido entrenado")

        y_pred = self.model.predict(X_test)

        metrics = {
            'accuracy':               accuracy_score(y_test, y_pred),
            'precision':              precision_score(y_test, y_pred, zero_division=0),
            'recall':                 recall_score(y_test, y_pred, zero_division=0),
            'f1':                     f1_score(y_test, y_pred, zero_division=0),
            'confusion_matrix':       confusion_matrix(y_test, y_pred),
            'classification_report':  classification_report(y_test, y_pred)
        }

        print("\n📊 Métricas de Evaluación:")
        print(f"   Accuracy:  {metrics['accuracy']:.4f}")
        print(f"   Precision: {metrics['precision']:.4f}")
        print(f"   Recall:    {metrics['recall']:.4f}")
        print(f"   F1-Score:  {metrics['f1']:.4f}")

        return metrics

    def predict(self, features_df: pd.DataFrame):
        """
        Realiza predicciones sobre nuevos datos.

        Returns:
            tuple: (predicciones, probabilidades)
        """
        if self.model is None:
            raise ValueError("El modelo no ha sido entrenado")

        X = features_df[self.feature_names]
        # Sin escalado
        predictions   = self.model.predict(X)
        probabilities = self.model.predict_proba(X)

        return predictions, probabilities

    # ------------------------------------------------------------------
    # UTILIDADES
    # ------------------------------------------------------------------

    def get_gini_impurity_explanation(self) -> str:
        """Genera explicación sobre el índice de Gini."""
        explanation = """
        🌳 ÍNDICE DE GINI EN ÁRBOL DE DECISIÓN CART

        El índice de Gini mide la impureza de un nodo. Se calcula como:

        Gini(node) = 1 - Σ(p_i²)

        Donde p_i es la proporción de muestras de la clase i en el nodo.

        - Gini = 0:   Nodo puro (todas las muestras de la misma clase)
        - Gini = 0.5: Máxima impureza (50% de cada clase)

        El algoritmo CART (Classification and Regression Trees):
        1. Calcula el Gini de cada posible división
        2. Elige la división que minimiza la impureza ponderada
        3. Repite recursivamente hasta alcanzar criterios de parada

        Importancia de características basada en Gini:
        - Reducción promedio de Gini que aporta cada característica
        - Características con mayor reducción son más importantes
        """

        if self.feature_importance:
            explanation += "\n\n📈 TOP CARACTERÍSTICAS (basadas en Gini):\n"
            for feature, importance in list(self.feature_importance.items())[:7]:
                bar = '█' * int(importance * 40)
                explanation += f"   {feature:30s}: {importance:.4f}  {bar}\n"

        return explanation

    def visualize_tree(self, max_depth=3, output_path='decision_tree.png'):
        """Visualiza el árbol de decisión y lo guarda como imagen."""
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

    def get_tree_rules(self) -> str:
        """Obtiene las reglas del árbol en formato texto."""
        if self.model is None:
            raise ValueError("El modelo no ha sido entrenado")
        return export_text(self.model, feature_names=self.feature_names)

    def save_model(self, filepath='commit_classifier.pkl'):
        """Guarda el modelo entrenado en disco."""
        if self.model is None:
            raise ValueError("El modelo no ha sido entrenado")

        model_data = {
            'model':              self.model,
            'feature_names':      self.feature_names,
            'feature_importance': self.feature_importance,
            'config':             self.config
        }
        # Nota: StandardScaler ya no se guarda (fue eliminado)
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        print(f"✓ Modelo guardado en: {filepath}")

    def load_model(self, filepath='commit_classifier.pkl'):
        """Carga un modelo previamente entrenado desde disco."""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        self.model              = model_data['model']
        self.feature_names      = model_data['feature_names']
        self.feature_importance = model_data['feature_importance']
        self.config             = model_data.get('config', self.config)
        print(f"✓ Modelo cargado desde: {filepath}")


# Instancia global del clasificador
commit_classifier = CommitClassifier()
