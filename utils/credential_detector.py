"""
Módulo de detección de credenciales expuestas usando expresiones regulares
"""
import re
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import CREDENTIAL_PATTERNS


class CredentialDetector:
    """Detector de credenciales expuestas en código"""
    
    def __init__(self):
        """Inicializa el detector con patrones regex"""
        self.patterns = CREDENTIAL_PATTERNS
        self.compiled_patterns = {}
        
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
    
    def detect_in_text(self, text, file_path=''):
        """
        Detecta credenciales en un texto
        
        Args:
            text (str): Texto a analizar
            file_path (str): Ruta del archivo analizado
            
        Returns:
            list: Lista de credenciales detectadas
        """
        detections = []
        lines = text.split('\n')
        
        for line_number, line in enumerate(lines, start=1):
            # Verificar cada patrón
            for credential_type, pattern in self.compiled_patterns.items():
                matches = pattern.finditer(line)
                for match in matches:
                    # Evitar falsos positivos comunes
                    if not self._is_false_positive(match.group(), credential_type):
                        detections.append({
                            'type': credential_type,
                            'file_path': file_path,
                            'line_number': line_number,
                            'pattern': match.group()[:50],  # Limitar tamaño
                            'severity': self._determine_severity(credential_type)
                        })
        
        return detections
    
    def detect_in_commit_diff(self, diff_content, file_path=''):
        """
        Detecta credenciales en un diff de commit
        
        Args:
            diff_content (str): Contenido del diff
            file_path (str): Ruta del archivo
            
        Returns:
            list: Lista de credenciales detectadas
        """
        detections = []
        lines = diff_content.split('\n')
        
        for line_number, line in enumerate(lines, start=1):
            # Solo analizar líneas añadidas (+)
            if line.startswith('+') and not line.startswith('+++'):
                clean_line = line[1:].strip()
                
                for credential_type, pattern in self.compiled_patterns.items():
                    matches = pattern.finditer(clean_line)
                    for match in matches:
                        if not self._is_false_positive(match.group(), credential_type):
                            detections.append({
                                'type': credential_type,
                                'file_path': file_path,
                                'line_number': line_number,
                                'pattern': match.group()[:50],
                                'severity': self._determine_severity(credential_type)
                            })
        
        return detections
    
    def has_suspicious_keywords(self, text):
        """
        Verifica si el texto contiene palabras clave sospechosas
        
        Args:
            text (str): Texto a analizar
            
        Returns:
            bool: True si contiene palabras sospechosas
        """
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.suspicious_keywords)
    
    def is_sensitive_file(self, file_path):
        """
        Verifica si un archivo es sensible (puede contener credenciales)
        
        Args:
            file_path (str): Ruta del archivo
            
        Returns:
            bool: True si es un archivo sensible
        """
        file_path_lower = file_path.lower()
        return any(sensitive in file_path_lower for sensitive in self.sensitive_files)
    
    def _is_false_positive(self, match_text, credential_type):
        """
        Determina si una coincidencia es un falso positivo
        
        Args:
            match_text (str): Texto que coincidió
            credential_type (str): Tipo de credencial
            
        Returns:
            bool: True si es falso positivo
        """
        # Patrones de falsos positivos comunes
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
            r'<.*>',  # Placeholders en XML/HTML
            r'\$\{.*\}',  # Variables de entorno
            r'\{\{.*\}\}',  # Plantillas
        ]
        
        match_lower = match_text.lower()
        
        for fp_pattern in false_positive_patterns:
            if re.search(fp_pattern, match_lower):
                return True
        
        # Verificaciones adicionales por tipo
        if credential_type == 'password':
            # Intentar extraer solo el valor de la contraseña (después del separador)
            # Ejemplo: "password": "valor" -> extrae "valor"
            value_match = re.search(r'[:=\s\'"]+([^\s\'"{}[\],;]+)', match_text)
            if value_match:
                value = value_match.group(1).lower()
                # Si el valor en sí es muy corto o es una palabra de ejemplo
                if len(value) < 4 or value in ['password', 'passwd', 'mypassword', 'yourpassword', 'contraseña', 'secret', 'xxxx', '****']:
                    return True
            else:
                # Si no se puede extraer el valor, aplicamos lógica básica sobre el texto completo
                if len(match_text) < 8:
                    return True
        
        return False
    
    def _determine_severity(self, credential_type):
        """
        Determina la severidad de una credencial detectada
        
        Args:
            credential_type (str): Tipo de credencial
            
        Returns:
            str: Nivel de severidad (CRITICAL, HIGH, MEDIUM)
        """
        critical_types = ['aws_access_key', 'aws_secret_key', 'private_key', 'stripe_key']
        high_types = ['github_token', 'github_oauth', 'google_api', 'heroku_api']
        
        if credential_type in critical_types:
            return 'CRITICAL'
        elif credential_type in high_types:
            return 'HIGH'
        else:
            return 'MEDIUM'
    
    def analyze_file_content(self, file_content, file_path):
        """
        Análisis completo de un archivo
        
        Args:
            file_content (str): Contenido del archivo
            file_path (str): Ruta del archivo
            
        Returns:
            dict: Resultado del análisis
        """
        detections = self.detect_in_text(file_content, file_path)
        
        return {
            'has_credentials': len(detections) > 0,
            'credential_count': len(detections),
            'detections': detections,
            'has_suspicious_keywords': self.has_suspicious_keywords(file_content),
            'is_sensitive_file': self.is_sensitive_file(file_path)
        }
    
    def get_statistics(self, detections_list):
        """
        Obtiene estadísticas de detecciones
        
        Args:
            detections_list (list): Lista de todas las detecciones
            
        Returns:
            dict: Estadísticas
        """
        if not detections_list:
            return {
                'total': 0,
                'by_type': {},
                'by_severity': {},
                'unique_files': 0
            }
        
        by_type = {}
        by_severity = {}
        unique_files = set()
        
        for detection in detections_list:
            # Contar por tipo
            cred_type = detection['type']
            by_type[cred_type] = by_type.get(cred_type, 0) + 1
            
            # Contar por severidad
            severity = detection['severity']
            by_severity[severity] = by_severity.get(severity, 0) + 1
            
            # Archivos únicos
            unique_files.add(detection['file_path'])
        
        return {
            'total': len(detections_list),
            'by_type': by_type,
            'by_severity': by_severity,
            'unique_files': len(unique_files)
        }


# Instancia global del detector
credential_detector = CredentialDetector()