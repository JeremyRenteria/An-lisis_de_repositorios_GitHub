"""
Módulo de integración con la API de GitHub
"""
import requests
from datetime import datetime
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import GITHUB_TOKEN


class GitHubAnalyzer:
    """Analizador de repositorios de GitHub"""
    
    def __init__(self, token=None):
        """
        Inicializa el analizador
        
        Args:
            token (str): Token de autenticación de GitHub
        """
        self.token = token or GITHUB_TOKEN
        self.base_url = 'https://api.github.com'
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def _make_request(self, url, params=None):
        """
        Realiza una petición a la API de GitHub
        
        Args:
            url (str): URL de la API
            params (dict): Parámetros de la petición
            
        Returns:
            dict o list: Respuesta de la API
        """
        try:
            response = self.session.get(url, params=params)
            
            # Manejar rate limit
            if response.status_code == 403:
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                if reset_time:
                    wait_time = reset_time - time.time()
                    if wait_time > 0:
                        print(f"⏳ Rate limit alcanzado. Esperando {wait_time:.0f} segundos...")
                        time.sleep(wait_time + 1)
                        return self._make_request(url, params)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Error en petición a GitHub API: {e}")
            return None
    
    def get_repository_info(self, owner, repo):
        """
        Obtiene información de un repositorio
        
        Args:
            owner (str): Propietario del repositorio
            repo (str): Nombre del repositorio
            
        Returns:
            dict: Información del repositorio
        """
        url = f"{self.base_url}/repos/{owner}/{repo}"
        data = self._make_request(url)
        
        if data:
            return {
                'name': data.get('name'),
                'full_name': data.get('full_name'),
                'owner': owner,
                'url': data.get('html_url'),
                'description': data.get('description'),
                'created_at': data.get('created_at'),
                'updated_at': data.get('updated_at'),
                'language': data.get('language'),
                'stars': data.get('stargazers_count'),
                'forks': data.get('forks_count'),
                'open_issues': data.get('open_issues_count'),
                'default_branch': data.get('default_branch', 'main')
            }
        return None
    
    def get_commits(self, owner, repo, branch='main', max_commits=100):
        """
        Obtiene commits de un repositorio
        
        Args:
            owner (str): Propietario del repositorio
            repo (str): Nombre del repositorio
            branch (str): Rama a analizar
            max_commits (int): Número máximo de commits
            
        Returns:
            list: Lista de commits
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/commits"
        commits = []
        page = 1
        per_page = min(100, max_commits)
        
        while len(commits) < max_commits:
            params = {
                'sha': branch,
                'per_page': per_page,
                'page': page
            }
            
            data = self._make_request(url, params)
            
            if not data:
                break
            
            if not isinstance(data, list) or len(data) == 0:
                break
            
            commits.extend(data)
            
            if len(data) < per_page:
                break
            
            page += 1
        
        # Procesar commits
        processed_commits = []
        for commit in commits[:max_commits]:
            try:
                commit_info = {
                    'sha': commit['sha'],
                    'message': commit['commit']['message'],
                    'author_name': commit['commit']['author']['name'],
                    'author_email': commit['commit']['author']['email'],
                    'date': datetime.strptime(
                        commit['commit']['author']['date'], 
                        '%Y-%m-%dT%H:%M:%SZ'
                    ),
                    'url': commit.get('html_url', '')
                }
                processed_commits.append(commit_info)
            except (KeyError, ValueError) as e:
                print(f"⚠ Error procesando commit {commit.get('sha', 'unknown')}: {e}")
                continue
        
        return processed_commits
    
    def get_commit_details(self, owner, repo, commit_sha):
        """
        Obtiene detalles de un commit específico
        
        Args:
            owner (str): Propietario del repositorio
            repo (str): Nombre del repositorio
            commit_sha (str): SHA del commit
            
        Returns:
            dict: Detalles del commit
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/commits/{commit_sha}"
        data = self._make_request(url)
        
        if data:
            stats = data.get('stats', {})
            files = data.get('files', [])
            
            return {
                'sha': data['sha'],
                'message': data['commit']['message'],
                'author_name': data['commit']['author']['name'],
                'author_email': data['commit']['author']['email'],
                'date': datetime.strptime(
                    data['commit']['author']['date'], 
                    '%Y-%m-%dT%H:%M:%SZ'
                ),
                'files_changed': len(files),
                'additions': stats.get('additions', 0),
                'deletions': stats.get('deletions', 0),
                'total_changes': stats.get('total', 0),
                'files': files
            }
        return None
    
    def get_commit_diff(self, owner, repo, commit_sha):
        """
        Obtiene el diff de un commit
        
        Args:
            owner (str): Propietario del repositorio
            repo (str): Nombre del repositorio
            commit_sha (str): SHA del commit
            
        Returns:
            dict: Diff por archivo
        """
        details = self.get_commit_details(owner, repo, commit_sha)
        
        if not details:
            return {}
        
        file_diffs = {}
        for file_data in details.get('files', []):
            file_diffs[file_data['filename']] = {
                'status': file_data.get('status'),
                'additions': file_data.get('additions', 0),
                'deletions': file_data.get('deletions', 0),
                'changes': file_data.get('changes', 0),
                'patch': file_data.get('patch', '')
            }
        
        return file_diffs
    
    def get_file_content(self, owner, repo, file_path, branch='main'):
        """
        Obtiene el contenido de un archivo
        
        Args:
            owner (str): Propietario del repositorio
            repo (str): Nombre del repositorio
            file_path (str): Ruta del archivo
            branch (str): Rama
            
        Returns:
            str: Contenido del archivo
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{file_path}"
        params = {'ref': branch}
        data = self._make_request(url, params)
        
        if data and 'content' in data:
            import base64
            try:
                content = base64.b64decode(data['content']).decode('utf-8')
                return content
            except Exception as e:
                print(f"✗ Error decodificando archivo {file_path}: {e}")
                return None
        return None
    
    def search_repositories(self, query, max_results=10):
        """
        Busca repositorios en GitHub
        
        Args:
            query (str): Consulta de búsqueda
            max_results (int): Número máximo de resultados
            
        Returns:
            list: Lista de repositorios encontrados
        """
        url = f"{self.base_url}/search/repositories"
        params = {
            'q': query,
            'per_page': min(100, max_results),
            'sort': 'stars',
            'order': 'desc'
        }
        
        data = self._make_request(url, params)
        
        if data and 'items' in data:
            repos = []
            for item in data['items'][:max_results]:
                repos.append({
                    'name': item['name'],
                    'owner': item['owner']['login'],
                    'full_name': item['full_name'],
                    'url': item['html_url'],
                    'description': item.get('description', ''),
                    'stars': item.get('stargazers_count', 0),
                    'language': item.get('language', 'Unknown')
                })
            return repos
        return []
    
    def validate_token(self):
        """
        Valida el token de GitHub
        
        Returns:
            bool: True si el token es válido
        """
        url = f"{self.base_url}/user"
        data = self._make_request(url)
        return data is not None
    
    def get_rate_limit(self):
        """
        Obtiene información del rate limit
        
        Returns:
            dict: Información del rate limit
        """
        url = f"{self.base_url}/rate_limit"
        data = self._make_request(url)
        
        if data:
            core = data.get('resources', {}).get('core', {})
            return {
                'limit': core.get('limit', 0),
                'remaining': core.get('remaining', 0),
                'reset': datetime.fromtimestamp(core.get('reset', 0)),
                'used': core.get('limit', 0) - core.get('remaining', 0)
            }
        return None


# Instancia global del analizador
github_analyzer = GitHubAnalyzer()