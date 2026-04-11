"""
Módulo de detección de credenciales expuestas usando expresiones regulares.

Mejoras implementadas:
  1. Entropía de Shannon  → descarta placeholders de baja aleatoriedad.
  2. Sistema de Scoring   → cada detección recibe un confidence_score (0.0-1.0).
  3. Filtro de documentación mejorado → maneja bloques de código en .md, .rst, etc.
  4. Umbral configurable  → solo se reportan detecciones con score >= min_confidence_score.
"""

import re
import math
import sys
import os
from collections import Counter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import CREDENTIAL_PATTERNS, DETECTOR_CONFIG


class CredentialDetector:
    """Detector de credenciales expuestas en código"""

    def __init__(self):
        """Inicializa el detector con patrones regex y configuración de scoring"""
        self.patterns = CREDENTIAL_PATTERNS
        self.compiled_patterns = {}

        # Leer configuracion central
        self.min_confidence  = DETECTOR_CONFIG['min_confidence_score']
        self.min_entropy     = DETECTOR_CONFIG['min_entropy_threshold']
        self.doc_extensions  = DETECTOR_CONFIG['documentation_extensions']
        self.sens_extensions = DETECTOR_CONFIG['sensitive_extensions']

        # Compilar todos los patrones regex para mejor rendimiento
        for credential_type, pattern in self.patterns.items():
            try:
                self.compiled_patterns[credential_type] = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                print(f"✗ Error compilando patrón {credential_type}: {e}")

        # Palabras clave sospechosas adicionales
        self.suspicious_keywords = [
            'password', 'passwd', 'pwd', 'secret', 'token', 'api_key',
            'apikey', 'access_key', 'private_key', 'auth', 'credential',
            'database_url', 'db_password', 'oauth', 'jwt'
        ]

        # Archivos sensibles que suelen contener credenciales
        self.sensitive_files = [
            '.env', '.env.local', '.env.production', 'config.json',
            'credentials.json', 'secrets.yml', 'secrets.yaml',
            'settings.py', 'config.py', 'application.properties',
            'docker-compose.yml', 'kubernetes.yml', '.aws/credentials'
        ]

        # Tipos de credenciales de alta severidad (base_score alto)
        self._severity_map = {
            'CRITICAL': ['aws_access_key', 'aws_secret_key', 'private_key', 'stripe_key'],
            'HIGH':     ['github_token', 'github_pat', 'github_oauth', 'google_api', 'heroku_api'],
        }

    # ------------------------------------------------------------------
    # 1. ENTROPÍA DE SHANNON
    # ------------------------------------------------------------------

    def _calculate_entropy(self, text: str) -> float:
        """
        Calcula la entropía de Shannon de una cadena.

        Fórmula: H = -Σ p(c) · log2(p(c))

        Una clave API real (muy aleatoria) tendrá H > 3.5.
        Un placeholder como 'tu_api_key_aqui' tendrá H < 3.0.

        Args:
            text: Cadena a evaluar.

        Returns:
            Valor de entropía (float). Cadena vacía → 0.0.
        """
        if not text:
            return 0.0
        freq = Counter(text)
        length = len(text)
        return -sum((count / length) * math.log2(count / length)
                    for count in freq.values())

    def _extract_value(self, match_text: str) -> str:
        """
        Extrae el valor literal de una coincidencia del tipo 'key = "valor"'.
        Si no puede extraerlo, devuelve el texto completo.
        """
        value_match = re.search(r'[:=\s\'"]+([^\s\'"{}[\],;]{6,})', match_text)
        return value_match.group(1) if value_match else match_text

    # ------------------------------------------------------------------
    # 2. FILTRO DE DOCUMENTACIÓN MEJORADO
    # ------------------------------------------------------------------

    def _is_doc_file(self, file_path: str) -> bool:
        """Devuelve True si el archivo es documentación."""
        lower = file_path.lower()
        return any(lower.endswith(ext) for ext in self.doc_extensions)

    def _is_inside_code_block(self, lines: list, line_index: int) -> bool:
        """
        Determina si una línea dada está dentro de un bloque de código
        Markdown (delimitado por triple backtick ```).

        Cuenta cuántas veces aparece ``` antes de la línea objetivo;
        si es impar, la línea está dentro de un bloque.
        """
        fence_count = 0
        for i in range(line_index):
            stripped = lines[i].strip()
            if stripped.startswith('```'):
                fence_count += 1
        return fence_count % 2 == 1

    def _is_doc_false_positive(self, match_text: str, lines: list, line_index: int) -> bool:
        """
        Filtro extendido para archivos de documentación.
        Devuelve True (= descartar) si:
          - La línea está dentro de un bloque de código Markdown.
          - El texto contiene placeholders obvios.
          - El valor extraído es claramente un ejemplo.
        """
        # Dentro de bloque de código → casi siempre es un ejemplo
        if self._is_inside_code_block(lines, line_index):
            return True

        lower = match_text.lower()

        # Placeholders explícitos
        placeholder_patterns = [
            r'your[_-]?', r'tu[_-]?', r'<[^>]+>', r'\[[^\]]+\]',
            r'example', r'placeholder', r'xxx+', r'\*{3,}',
            r'\$\{', r'\{\{',
        ]
        for pp in placeholder_patterns:
            if re.search(pp, lower):
                return True

        # Valor muy corto tras el separador → casi siempre ejemplo
        value = self._extract_value(match_text)
        if len(value) < 8:
            return True

        return False

    # ------------------------------------------------------------------
    # 3. SISTEMA DE SCORING
    # ------------------------------------------------------------------

    def _base_score(self, credential_type: str) -> float:
        """
        Score base según la severidad del tipo de credencial.
          CRITICAL → 0.8
          HIGH     → 0.65
          MEDIUM   → 0.5
        """
        if credential_type in self._severity_map['CRITICAL']:
            return 0.8
        if credential_type in self._severity_map['HIGH']:
            return 0.65
        return 0.5

    def _calculate_confidence(
        self,
        match_text: str,
        credential_type: str,
        file_path: str,
        context_line: str,
    ) -> float:
        """
        Calcula el confidence_score (0.0 – 1.0) de una detección.

        Factores que SUBEN el score:
          + Archivo sensible (.env, .pem, etc.)
          + Entropía del valor >= umbral configurado
          + Contexto con palabras clave sospechosas cercanas

        Factores que BAJAN el score:
          - Archivo de documentación (.md, .rst, etc.)

        El score final se recorta al rango [0.0, 1.0].
        """
        score = self._base_score(credential_type)

        file_lower = file_path.lower()

        # Bonus: archivo sensible
        if any(s in file_lower for s in self.sens_extensions):
            score += DETECTOR_CONFIG['score_bonus_sensitive_file']

        # Penalización: archivo de documentación
        if self._is_doc_file(file_path):
            score -= DETECTOR_CONFIG['score_penalty_doc_file']

        # Bonus: entropía alta del valor detectado
        value = self._extract_value(match_text)
        entropy = self._calculate_entropy(value)
        if entropy >= self.min_entropy:
            score += DETECTOR_CONFIG['score_bonus_high_entropy']

        # Bonus: palabras clave sospechosas en la misma línea
        context_lower = context_line.lower()
        if any(kw in context_lower for kw in self.suspicious_keywords):
            score += DETECTOR_CONFIG['score_bonus_keyword_context']

        return max(0.0, min(1.0, score))

    # ------------------------------------------------------------------
    # 4. DETECCIÓN PRINCIPAL
    # ------------------------------------------------------------------

    def _is_false_positive(self, match_text: str, credential_type: str, file_path: str = '') -> bool:
        """
        Filtro general de falsos positivos (independiente de entropía/score).
        """
        false_positive_patterns = [
            r'example\.com',
            r'your[_-]?api[_-]?key',
            r'your[_-]?password',
            r'placeholder',
            r'dummy',
            r'test[_-]?key',
            r'fake[_-]?token',
            r'xxxxxxxx',
            r'\*\*\*\*\*',
            r'<.*?>',
            r'\$\{.*?\}',
            r'\{\{.*?\}\}',
            r'db_user',
            r'db_password',
            r'config\.',
            r'os\.environ',
            r'getenv',
            r'YOUR[_-]?[A-Z0-9]+',
            r'<[A-Z0-9_]+>',
            r'\[[A-Z0-9_]+\]',
            r'example[_-]?user',
            r'example[_-]?password',
            r'localhost',
            r'127\.0\.0\.1',
        ]

        match_lower = match_text.lower()
        for fp in false_positive_patterns:
            if re.search(fp, match_lower):
                return True

        # Llamada a función
        if re.search(r'\(.*?\)', match_text):
            return True

        # Contraseña/usuario sin comillas → probablemente variable, no valor
        if credential_type in ('password', 'db_password', 'db_user') and not re.search(r'[\'"]', match_text):
            return True

        # Verificación adicional por tipo password
        if credential_type == 'password':
            value_match = re.search(r'[:=\s\'"]+([^\s\'"{}[\],;]+)', match_text)
            if value_match:
                value = value_match.group(1).lower()
                weak = {'password', 'passwd', 'mypassword', 'yourpassword',
                        'contraseña', 'secret', 'xxxx', '****', 'admin', 'root'}
                if len(value) < 6 or value in weak:
                    return True
            else:
                if len(match_text) < 8:
                    return True

        return False

    def detect_in_text(self, text: str, file_path: str = '') -> list:
        """
        Detecta credenciales en un bloque de texto completo.

        Flujo por línea:
          1. Filtro general de falsos positivos.
          2. Filtro especial para archivos de documentación.
          3. Cálculo de entropía → descarte si < umbral.
          4. Cálculo de confidence_score → descarte si < min_confidence.

        Returns:
            Lista de dicts con las detecciones que superaron todos los filtros.
        """
        detections = []
        lines = text.split('\n')
        is_doc = self._is_doc_file(file_path)

        for line_index, line in enumerate(lines):
            for credential_type, pattern in self.compiled_patterns.items():
                for match in pattern.finditer(line):
                    match_text = match.group()

                    # --- Filtro 1: falsos positivos generales ---
                    if self._is_false_positive(match_text, credential_type, file_path):
                        continue

                    # --- Filtro 2: documentación ---
                    if is_doc and self._is_doc_false_positive(match_text, lines, line_index):
                        continue

                    # --- Filtro 3: entropía mínima ---
                    value = self._extract_value(match_text)
                    entropy = self._calculate_entropy(value)
                    if entropy < self.min_entropy:
                        continue

                    # --- Filtro 4: confidence score ---
                    score = self._calculate_confidence(
                        match_text, credential_type, file_path, line
                    )
                    if score < self.min_confidence:
                        continue

                    detections.append({
                        'type': credential_type,
                        'file_path': file_path,
                        'line_number': line_index + 1,
                        'pattern': match_text[:50],
                        'severity': self._determine_severity(credential_type),
                        'confidence_score': round(score, 3),
                        'entropy': round(entropy, 3),
                    })

        return detections

    def detect_in_commit_diff(self, diff_content: str, file_path: str = '') -> list:
        """
        Detecta credenciales en el diff de un commit.
        Solo analiza líneas añadidas (+), excluyendo encabezados (+++).
        Aplica el mismo pipeline de filtros que detect_in_text.
        """
        detections = []
        lines = diff_content.split('\n')
        is_doc = self._is_doc_file(file_path)

        # Para el filtro de bloques de código en diff, usamos solo las líneas limpias
        clean_lines = [
            (line[1:].strip() if (line.startswith('+') and not line.startswith('+++')) else '')
            for line in lines
        ]

        for line_index, line in enumerate(lines):
            if not (line.startswith('+') and not line.startswith('+++')):
                continue

            clean_line = line[1:].strip()

            for credential_type, pattern in self.compiled_patterns.items():
                for match in pattern.finditer(clean_line):
                    match_text = match.group()

                    if self._is_false_positive(match_text, credential_type, file_path):
                        continue

                    if is_doc and self._is_doc_false_positive(match_text, clean_lines, line_index):
                        continue

                    value = self._extract_value(match_text)
                    entropy = self._calculate_entropy(value)
                    if entropy < self.min_entropy:
                        continue

                    score = self._calculate_confidence(
                        match_text, credential_type, file_path, clean_line
                    )
                    if score < self.min_confidence:
                        continue

                    detections.append({
                        'type': credential_type,
                        'file_path': file_path,
                        'line_number': line_index + 1,
                        'pattern': match_text[:50],
                        'severity': self._determine_severity(credential_type),
                        'confidence_score': round(score, 3),
                        'entropy': round(entropy, 3),
                    })

        return detections

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def has_suspicious_keywords(self, text: str) -> bool:
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.suspicious_keywords)

    def is_sensitive_file(self, file_path: str) -> bool:
        file_path_lower = file_path.lower()
        return any(s in file_path_lower for s in self.sensitive_files)

    def _determine_severity(self, credential_type: str) -> str:
        if credential_type in self._severity_map['CRITICAL']:
            return 'CRITICAL'
        if credential_type in self._severity_map['HIGH']:
            return 'HIGH'
        return 'MEDIUM'

    def analyze_file_content(self, file_content: str, file_path: str) -> dict:
        """Análisis completo de un archivo."""
        detections = self.detect_in_text(file_content, file_path)
        return {
            'has_credentials': len(detections) > 0,
            'credential_count': len(detections),
            'detections': detections,
            'has_suspicious_keywords': self.has_suspicious_keywords(file_content),
            'is_sensitive_file': self.is_sensitive_file(file_path),
        }

    def get_statistics(self, detections_list: list) -> dict:
        """Estadísticas de un conjunto de detecciones."""
        if not detections_list:
            return {'total': 0, 'by_type': {}, 'by_severity': {}, 'unique_files': 0,
                    'avg_confidence': 0.0}

        by_type, by_severity, unique_files = {}, {}, set()
        total_confidence = 0.0

        for d in detections_list:
            by_type[d['type']] = by_type.get(d['type'], 0) + 1
            by_severity[d['severity']] = by_severity.get(d['severity'], 0) + 1
            unique_files.add(d['file_path'])
            total_confidence += d.get('confidence_score', 0.0)

        return {
            'total': len(detections_list),
            'by_type': by_type,
            'by_severity': by_severity,
            'unique_files': len(unique_files),
            'avg_confidence': round(total_confidence / len(detections_list), 3),
        }


# Instancia global del detector
credential_detector = CredentialDetector()
