"""
Interfaz Gráfica de Usuario para GitHub Analyzer
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime
import threading
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import GUI_CONFIG
from database.db_manager import db_manager
from utils.github_api import github_analyzer
from utils.credential_detector import credential_detector
from models.ml_classifier import commit_classifier
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns


class GitHubAnalyzerGUI:
    """Interfaz gráfica principal de la aplicación"""
    
    def __init__(self, root):
        """Inicializa la GUI"""
        self.root = root
        self.root.title(GUI_CONFIG['window_title'])
        self.root.geometry(GUI_CONFIG['window_size'])
        
        # Variables
        self.analysis_running = False
        self.current_repo_id = None
        
        # Configurar estilo
        self.setup_style()
        
        # Crear interfaz
        self.create_menu()
        self.create_widgets()
        
        # Verificar conexión inicial
        self.check_connections()
    
    def setup_style(self):
        """Configura el estilo de la aplicación 'Cyber-Guard'"""
        self.root.configure(bg='#1e1e2e')
        style = ttk.Style()
        style.theme_use('clam')
        
        # Colores Palette (Cyber-Guard)
        self.colors = {
            'bg_dark': '#1e1e2e',
            'bg_sidebar': '#11111b',
            'accent': '#cba6f7',
            'text': '#cdd6f4',
            'critical': '#f38ba8',
            'high': '#fab387',
            'medium': '#f9e2af',
            'success': '#a6e3a1'
        }

        # Estilo de Botones Sidebar
        style.configure('Sidebar.TButton', 
            font=('Segoe UI', 11), 
            padding=10, 
            background=self.colors['bg_sidebar'],
            foreground=self.colors['text']
        )
        
        # Estilo de Labels Dark
        style.configure('Dark.TLabel', background=self.colors['bg_dark'], foreground=self.colors['text'], font=('Segoe UI', 10))
        style.configure('DarkTitle.TLabel', background=self.colors['bg_dark'], foreground=self.colors['accent'], font=('Segoe UI', 18, 'bold'))
        
        # Estilo de Treeview (Resultados)
        style.configure("Treeview", 
            background="#2e2e3e", 
            foreground="white", 
            fieldbackground="#2e2e3e",
            font=('Segoe UI', 9),
            rowheight=25
        )
        style.map("Treeview", background=[('selected', self.colors['accent'])], foreground=[('selected', 'black')])
        style.configure("Treeview.Heading", background="#11111b", foreground=self.colors['accent'], font=('Segoe UI', 10, 'bold'))
    
    def create_menu(self):
        """Crea el menú de la aplicación"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menú Archivo
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=file_menu)
        file_menu.add_command(label="Exportar Resultados", command=self.export_results)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.root.quit)
        
        # Menú Modelo
        model_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Modelo ML", menu=model_menu)
        model_menu.add_command(label="Entrenar Modelo", command=self.train_model)
        model_menu.add_command(label="Información del Modelo", command=self.show_model_info)
        model_menu.add_command(label="Visualizar Árbol", command=self.visualize_tree)
        
        # Menú Ayuda
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=help_menu)
        help_menu.add_command(label="Acerca de", command=self.show_about)
    
    def create_widgets(self):
        """Crea los widgets de la interfaz con Sidebar"""
        # --- Sidebar (Izquierda) ---
        self.sidebar = tk.Frame(self.root, bg=self.colors['bg_sidebar'], width=200)
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)

        # Título en Sidebar
        tk.Label(self.sidebar, text="CYBER\nGUARD", bg=self.colors['bg_sidebar'], fg=self.colors['accent'], 
                 font=('Impact', 22), pady=20).pack()
        
        tk.Frame(self.sidebar, bg=self.colors['accent'], height=2).pack(fill='x', padx=20, pady=10)

        # Botones de Navegación
        nav_items = [
            ("🔍 Escáner", "scanner"),
            ("📋 Hallazgos", "results"),
            ("📊 Dashboard", "stats"),
            ("🧠 Inteligencia", "ml")
        ]
        
        self.nav_buttons = {}
        for text, screen in nav_items:
            btn = tk.Button(self.sidebar, text=text, bg=self.colors['bg_sidebar'], fg=self.colors['text'],
                            font=('Segoe UI', 11), bd=0, activebackground=self.colors['accent'], 
                            activeforeground=self.colors['bg_dark'], anchor='w', padx=20, pady=10,
                            command=lambda s=screen: self.show_screen(s))
            btn.pack(fill='x')
            self.nav_buttons[screen] = btn

        # --- Contenedor Principal (Derecha) ---
        self.main_container = tk.Frame(self.root, bg=self.colors['bg_dark'])
        self.main_container.pack(side='right', fill='both', expand=True)

        # Crear todas las pantallas (ocultas)
        self.screens = {}
        self.create_analysis_screen()
        self.create_results_screen()
        self.create_stats_screen()
        self.create_ml_screen()

        # Mostrar pantalla inicial
        self.show_screen("scanner")

        # Barra de estado
        self.create_status_bar()

    def show_screen(self, screen_name):
        """Alterna entre las pantallas de la interfaz"""
        for name, frame in self.screens.items():
            frame.pack_forget()
            self.nav_buttons[name].config(bg=self.colors['bg_sidebar'], fg=self.colors['text'])
        
        self.screens[screen_name].pack(fill='both', expand=True)
        self.nav_buttons[screen_name].config(bg=self.colors['accent'], fg=self.colors['bg_dark'])
    
    def create_analysis_screen(self):
        """Crea la pantalla de escaneo"""
        screen = tk.Frame(self.main_container, bg=self.colors['bg_dark'])
        self.screens['scanner'] = screen
        
        header = tk.Frame(screen, bg=self.colors['bg_dark'], pady=20)
        header.pack(fill='x', padx=20)
        ttk.Label(header, text="Escáner de Seguridad de GitHub", style='DarkTitle.TLabel').pack(side='left')

        # Panel de Entrada Estilizado
        input_frame = tk.LabelFrame(screen, text=' Configuración de Análisis ', bg=self.colors['bg_dark'], 
                                   fg=self.colors['accent'], font=('Segoe UI', 10, 'bold'), padx=20, pady=20)
        input_frame.pack(fill='x', padx=20, pady=10)
        
        # Helper para labels e inputs en dark mode
        def create_field(row, label_text, default=''):
            tk.Label(input_frame, text=label_text, bg=self.colors['bg_dark'], fg=self.colors['text'], font=('Segoe UI', 10)).grid(row=row, column=0, sticky='w', pady=8)
            entry = tk.Entry(input_frame, bg='#2e2e3e', fg='white', insertbackground='white', bd=1, relief='flat', width=35)
            entry.insert(0, default)
            entry.grid(row=row, column=1, padx=20, pady=8, sticky='w')
            return entry

        self.owner_entry = create_field(0, "Propietario / Organización (Ej: Google)")
        self.repo_entry = create_field(1, "Nombre del Repositorio")
        self.branch_entry = create_field(2, "Rama (Branch)", "main")
        self.max_commits_entry = create_field(3, "Límite de Commits", "100")
        
        # Botón de Inicio con estilo neón
        self.analyze_btn = tk.Button(input_frame, text="🚀 INICIAR ESCANEO", bg=self.colors['accent'], fg=self.colors['bg_dark'],
                                    font=('Segoe UI', 11, 'bold'), bd=0, padx=30, pady=10, cursor='hand2',
                                    command=self.start_analysis)
        self.analyze_btn.grid(row=4, column=0, columnspan=2, pady=20)
        
        # Progress bar dark
        self.progress = ttk.Progressbar(screen, mode='indeterminate')
        self.progress.pack(fill='x', padx=25, pady=5)
        
        # Área de Terminal de Log
        log_frame = tk.LabelFrame(screen, text=' Terminal de Operaciones ', bg=self.colors['bg_dark'], 
                                 fg=self.colors['accent'], font=('Segoe UI', 10, 'bold'), padx=10, pady=10)
        log_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, bg='#11111b', fg='#a6e3a1', font=('Consolas', 10),
                                               insertbackground='white', bd=0, padx=10, pady=10)
        self.log_text.pack(fill='both', expand=True)
    
    def create_results_screen(self):
        """Crea la pantalla de resultados"""
        screen = tk.Frame(self.main_container, bg=self.colors['bg_dark'])
        self.screens['results'] = screen
        
        header = tk.Frame(screen, bg=self.colors['bg_dark'], pady=20)
        header.pack(fill='x', padx=20)
        ttk.Label(header, text="Hallazgos de Seguridad", style='DarkTitle.TLabel').pack(side='left')
        
        # Controles
        control_frame = tk.Frame(screen, bg=self.colors['bg_dark'])
        control_frame.pack(fill='x', padx=20, pady=10)
        
        def create_action_btn(text, cmd):
            return tk.Button(control_frame, text=text, bg='#2e2e3e', fg=self.colors['text'],
                            font=('Segoe UI', 10), bd=0, padx=15, pady=5, cursor='hand2',
                            activebackground=self.colors['accent'], command=cmd)

        create_action_btn("🔄 Actualizar Tabla", self.load_results).pack(side='left', padx=5)
        create_action_btn("📥 Exportar a CSV", self.export_to_csv).pack(side='left', padx=5)
        
        # Tabla de resultados
        table_frame = tk.Frame(screen, bg=self.colors['bg_dark'])
        table_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        vsb = ttk.Scrollbar(table_frame, orient="vertical")
        vsb.pack(side='right', fill='y')
        hsb = ttk.Scrollbar(table_frame, orient="horizontal")
        hsb.pack(side='bottom', fill='x')
        
        columns = ('ID', 'Tipo', 'Archivo', 'Línea', 'Severidad', 'Commit SHA', 'Validez ML', 'Autor', 'Fecha')
        self.results_tree = ttk.Treeview(table_frame, columns=columns, show='headings',
                                       yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        vsb.config(command=self.results_tree.yview)
        hsb.config(command=self.results_tree.xview)
        
        for col in columns:
            self.results_tree.heading(col, text=col)
            self.results_tree.column(col, width=100)
        
        self.results_tree.pack(fill='both', expand=True)
        
        # Tags (Adaptados a Dark Mode)
        self.results_tree.tag_configure('CRITICAL', background='#4a1414', foreground='#ffcccc')
        self.results_tree.tag_configure('HIGH', background='#4a2b10', foreground='#ffe6cc')
        self.results_tree.tag_configure('MEDIUM', background='#4a4a10', foreground='#ffffcc')

    def create_stats_screen(self):
        """Crea la pantalla de Dashboard Visual"""
        screen = tk.Frame(self.main_container, bg=self.colors['bg_dark'])
        self.screens['stats'] = screen
        
        header = tk.Frame(screen, bg=self.colors['bg_dark'], pady=20)
        header.pack(fill='x', padx=20)
        ttk.Label(header, text="Estadísticas Avanzadas", style='DarkTitle.TLabel').pack(side='left')
        
        # KPIs
        self.kpi_frame = tk.Frame(screen, bg=self.colors['bg_dark'], pady=10)
        self.kpi_frame.pack(fill='x', padx=20)
        
        self.stats_labels = {}
        kpis = [
            ('REPOSITORIOS', 'repos', '#24273a'),
            ('COMMITS ANALIZADOS', 'commits', '#24273a'),
            ('AMENAZAS TOTALES', 'credentials', '#24273a'),
            ('NIVEL RIESGO', 'risk_level', '#24273a')
        ]
        
        for idx, (label, key, color) in enumerate(kpis):
            card = tk.Frame(self.kpi_frame, bg=color, bd=1, relief='flat', padx=20, pady=15)
            card.pack(side='left', expand=True, fill='both', padx=5)
            
            tk.Label(card, text=label, bg=color, font=('Segoe UI', 9, 'bold'), fg=self.colors['accent']).pack()
            val_lb = tk.Label(card, text='0', bg=color, font=('Segoe UI', 22, 'bold'), fg=self.colors['text'])
            val_lb.pack()
            self.stats_labels[key] = val_lb

        # Gráficos
        self.charts_container = tk.Frame(screen, bg=self.colors['bg_dark'], pady=10)
        self.charts_container.pack(fill='both', expand=True, padx=20)
        
        self.left_chart_frame = tk.LabelFrame(self.charts_container, text=' Gravedad de Amenazas ', 
                                            bg=self.colors['bg_dark'], fg=self.colors['text'], font=('Segoe UI', 10, 'bold'))
        self.left_chart_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        self.right_chart_frame = tk.LabelFrame(self.charts_container, text=' Radar por Proyectos ', 
                                             bg=self.colors['bg_dark'], fg=self.colors['text'], font=('Segoe UI', 10, 'bold'))
        self.right_chart_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        # Actualizar btn
        tk.Button(screen, text='🔄 REFRESCAR DASHBOARD', bg=self.colors['accent'], fg=self.colors['bg_dark'],
                  font=('Segoe UI', 10, 'bold'), bd=0, padx=20, pady=8, command=self.update_statistics).pack(pady=10)

    def create_ml_screen(self):
        """Crea la pantalla de Inteligencia Artificial"""
        screen = tk.Frame(self.main_container, bg=self.colors['bg_dark'])
        self.screens['ml'] = screen
        
        header = tk.Frame(screen, bg=self.colors['bg_dark'], pady=20)
        header.pack(fill='x', padx=20)
        ttk.Label(header, text="Centro de Inteligencia CART", style='DarkTitle.TLabel').pack(side='left')
        
        # Explicación
        concept_frame = tk.LabelFrame(screen, text=' Algoritmo de Decisión ', bg=self.colors['bg_dark'], 
                                    fg=self.colors['accent'], font=('Segoe UI', 10, 'bold'), padx=20, pady=15)
        concept_frame.pack(fill='x', padx=20, pady=10)
        
        txt = "El analizador utiliza un Bosque de Decisión para validar si un fragmento detectado por Regex es una credencial real o un falso positivo basado en el contexto del commit."
        tk.Label(concept_frame, text=txt, bg=self.colors['bg_dark'], fg=self.colors['text'], 
                 justify='left', wraplength=700).pack()
        
        # Métricas
        metrics_frame = tk.Frame(screen, bg=self.colors['bg_dark'])
        metrics_frame.pack(fill='x', padx=20, pady=10)
        
        self.ml_metrics_labels = {}
        for idx, (lbl, key) in enumerate([('Precisión (Accuracy):', 'accuracy'), ('Score F1:', 'f1')]):
            f = tk.Frame(metrics_frame, bg='#24273a', padx=20, pady=10)
            f.pack(side='left', expand=True, fill='both', padx=5)
            tk.Label(f, text=lbl, bg='#24273a', fg=self.colors['accent'], font=('Segoe UI', 10, 'bold')).pack()
            v = tk.Label(f, text='0.0000', bg='#24273a', fg='white', font=('Segoe UI', 16, 'bold'))
            v.pack()
            self.ml_metrics_labels[key] = v

        # Botones
        btn_frame = tk.Frame(screen, bg=self.colors['bg_dark'])
        btn_frame.pack(fill='x', padx=20, pady=10)
        
        def cyber_btn(text, cmd):
            return tk.Button(btn_frame, text=text, bg=self.colors['accent'], fg=self.colors['bg_dark'],
                           font=('Segoe UI', 9, 'bold'), bd=0, padx=15, pady=8, command=cmd)

        cyber_btn("🧠 ENTRENAR CEREBRO", self.train_model).pack(side='left', padx=5)
        cyber_btn("📊 FACTORES GINI", self.show_feature_importance).pack(side='left', padx=5)
        
        # Terminal de Detalles
        detail_frame = tk.LabelFrame(screen, text=' Análisis de Contexto ', bg=self.colors['bg_dark'], 
                                   fg=self.colors['accent'], font=('Segoe UI', 10, 'bold'), padx=10, pady=10)
        detail_frame.pack(fill='both', expand=True, padx=20, pady=10)
        self.ml_detail_text = scrolledtext.ScrolledText(detail_frame, bg='#11111b', fg='#f5c2e7', font=('Consolas', 10), bd=0)
        self.ml_detail_text.pack(fill='both', expand=True)

    def create_status_bar(self):
        """Crea la barra de estado con estilo Cyber"""
        self.status_bar = tk.Label(
            self.root, 
            text=' 🛡️ Sistema Cyber-Guard Operativo | Listo para Escaneo', 
            bg=self.colors['bg_sidebar'],
            fg=self.colors['accent'],
            font=('Segoe UI', 9),
            relief=tk.FLAT, 
            anchor='w',
            padx=10,
            pady=5
        )
        self.status_bar.pack(side='bottom', fill='x')
    
    def log(self, message):
        """Agrega un mensaje al log"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert('end', f'[{timestamp}] {message}\n')
        self.log_text.see('end')
        self.root.update_idletasks()
    
    def update_status(self, message):
        """Actualiza la barra de estado"""
        self.status_bar.config(text=message)
        self.root.update_idletasks()
    
    def check_connections(self):
        """Verifica las conexiones iniciales"""
        try:
            # Verificar base de datos
            repos = db_manager.get_repository_summary()
            self.log(f"✓ Conexión a PostgreSQL exitosa ({len(repos)} repositorios)")
            
            # Verificar GitHub API
            if github_analyzer.validate_token():
                rate_limit = github_analyzer.get_rate_limit()
                self.log(f"✓ Token de GitHub válido ({rate_limit['remaining']} requests disponibles)")
            else:
                self.log("⚠ Token de GitHub no configurado o inválido")
            
            self.update_status("Conexiones verificadas")
            
        except Exception as e:
            self.log(f"✗ Error verificando conexiones: {str(e)}")
            messagebox.showerror("Error", f"Error de conexión: {str(e)}")
    
    def start_analysis(self):
        """Inicia el análisis del repositorio"""
        if self.analysis_running:
            messagebox.showwarning("Advertencia", "Ya hay un análisis en ejecución")
            return
        
        owner = self.owner_entry.get().strip()
        repo = self.repo_entry.get().strip()
        branch = self.branch_entry.get().strip() or 'main'
        
        if not owner or not repo:
            messagebox.showerror("Error", "Debe ingresar propietario y repositorio")
            return
        
        try:
            max_commits = int(self.max_commits_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Máx. commits debe ser un número")
            return
        
        # Ejecutar en thread separado
        self.analysis_running = True
        self.analyze_btn.config(state='disabled')
        self.progress.start()
        
        thread = threading.Thread(
            target=self.run_analysis,
            args=(owner, repo, branch, max_commits),
            daemon=True
        )
        thread.start()
    
    def run_analysis(self, owner, repo, branch, max_commits):
        """Ejecuta el análisis completo"""
        try:
            self.log(f"\n{'='*60}")
            self.log(f"Iniciando análisis de {owner}/{repo}")
            self.log(f"{'='*60}\n")
            
            # 1. Obtener información del repositorio
            self.log("📦 Obteniendo información del repositorio...")
            repo_info = github_analyzer.get_repository_info(owner, repo)
            
            if not repo_info:
                self.log("✗ No se pudo obtener información del repositorio")
                return
            
            self.log(f"✓ Repositorio: {repo_info['full_name']}")
            self.log(f"  Lenguaje: {repo_info['language']}")
            self.log(f"  Estrellas: {repo_info['stars']}")
            
            # Guardar en BD
            repo_id = db_manager.insert_repository(
                repo_info['name'],
                repo_info['owner'],
                repo_info['url']
            )
            self.current_repo_id = repo_id
            self.log(f"✓ Repositorio guardado (ID: {repo_id})")
            
            # 2. Obtener commits
            self.log(f"\n📝 Obteniendo commits (máx: {max_commits})...")
            commits = github_analyzer.get_commits(owner, repo, branch, max_commits)
            self.log(f"✓ Obtenidos {len(commits)} commits")
            
            # 3. Analizar cada commit
            self.log(f"\n🔍 Analizando commits...")
            total_credentials = 0
            
            for idx, commit in enumerate(commits, 1):
                self.log(f"  Analizando commit {idx}/{len(commits)}: {commit['sha'][:7]}...")
                
                # Obtener detalles del commit
                commit_details = github_analyzer.get_commit_details(
                    owner, repo, commit['sha']
                )
                
                if not commit_details:
                    continue
                
                # Detectar credenciales
                commit['files_changed'] = commit_details['files_changed']
                commit['additions'] = commit_details['additions']
                commit['deletions'] = commit_details['deletions']
                
                credentials_found = []
                
                # Analizar diff de cada archivo
                file_diffs = github_analyzer.get_commit_diff(owner, repo, commit['sha'])
                
                for file_path, diff_data in file_diffs.items():
                    patch = diff_data.get('patch', '')
                    if patch:
                        detections = credential_detector.detect_in_commit_diff(patch, file_path)
                        credentials_found.extend(detections)
                
                # Calcular riesgo
                has_credentials = len(credentials_found) > 0
                risk_score = self.calculate_risk_score(
                    has_credentials, 
                    len(credentials_found),
                    commit_details
                )
                
                commit['has_credentials'] = has_credentials
                commit['risk_score'] = risk_score
                
                # Guardar commit en BD
                commit_id = db_manager.insert_commit(repo_id, commit)
                
                # Guardar credenciales detectadas
                for cred in credentials_found:
                    db_manager.insert_credential(commit_id, cred)
                    total_credentials += 1
                
                # Extraer y guardar características para ML
                features = self.extract_commit_features(commit, commit_details)
                db_manager.insert_commit_features(commit_id, features)
            
            # 4. Actualizar estadísticas del repositorio
            risk_level = self.determine_risk_level(total_credentials, len(commits))
            db_manager.update_repository_stats(
                repo_id, 
                len(commits), 
                total_credentials, 
                risk_level
            )
            
            # Resumen
            self.log(f"\n{'='*60}")
            self.log(f"✓ ANÁLISIS COMPLETADO")
            self.log(f"{'='*60}")
            self.log(f"  Total commits analizados: {len(commits)}")
            self.log(f"  Credenciales detectadas: {total_credentials}")
            self.log(f"  Nivel de riesgo: {risk_level}")
            self.log(f"{'='*60}\n")
            
            # Cargar resultados en la tabla
            self.root.after(0, self.load_results)
            self.root.after(0, self.update_statistics)
            
            self.root.after(
                0, 
                messagebox.showinfo, 
                "Análisis Completado", 
                f"Se analizaron {len(commits)} commits.\nSe detectaron {total_credentials} credenciales."
            )
            
        except Exception as e:
            self.log(f"\n✗ ERROR: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            self.root.after(
                0, 
                messagebox.showerror, 
                "Error", 
                f"Error durante el análisis: {str(e)}"
            )
        
        finally:
            self.analysis_running = False
            self.root.after(0, self.analyze_btn.config, {'state': 'normal'})
            self.root.after(0, self.progress.stop)
            self.root.after(0, self.update_status, "Análisis completado")
    
    def calculate_risk_score(self, has_credentials, num_credentials, commit_details):
        """Calcula el score de riesgo de un commit"""
        score = 0.0
        
        if has_credentials:
            score += 0.5 + (num_credentials * 0.1)
        
        # Factores adicionales
        if commit_details['additions'] > 100:
            score += 0.1
        
        if commit_details['files_changed'] > 10:
            score += 0.1
        
        return min(score, 1.0)
    
    def determine_risk_level(self, total_credentials, total_commits):
        """Determina el nivel de riesgo del repositorio"""
        if total_credentials == 0:
            return 'LOW'
        
        ratio = total_credentials / total_commits
        
        if ratio > 0.1:
            return 'CRITICAL'
        elif ratio > 0.05:
            return 'HIGH'
        elif ratio > 0.01:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def extract_commit_features(self, commit, commit_details):
        """Extrae características de un commit para ML"""
        message = commit.get('message', '')
        
        # --- INTEGRACIÓN REGEX + ML ---
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
        is_sens_file = any(
            credential_detector.is_sensitive_file(f['filename']) 
            for f in commit_details.get('files', [])
        )

        return {
            'has_suspicious_keywords': credential_detector.has_suspicious_keywords(message),
            'regex_detected_count': regex_count,
            'max_regex_severity': max_severity,
            'is_sensitive_file': is_sens_file,
            'commit_hour': commit['date'].hour,
            'commit_day_of_week': commit['date'].weekday(),
            'message_length': len(message),
            'files_modified': commit_details['files_changed'],
            'code_additions': commit_details['additions'],
            'code_deletions': commit_details['deletions'],
            'has_config_files': any(
                credential_detector.is_sensitive_file(f['filename']) 
                for f in commit_details.get('files', [])
            ),
            'has_env_files': any(
                '.env' in f['filename'].lower() 
                for f in commit_details.get('files', [])
            ),
            'prediction_label': int(commit.get('has_credentials', False)),
            'prediction_confidence': commit.get('risk_score', 0.0)
        }
    
    def load_results(self):
        """Carga los resultados en la tabla"""
        try:
            # Limpiar tabla
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            # Obtener datos
            df = db_manager.get_credentials_dataframe()
            
            if df.empty:
                self.update_status("No hay credenciales detectadas")
                return
            
            # Insertar en tabla
            for idx, row in df.iterrows():
                ml_val = "⚠️ Probable Falso Positivo" if row.get('prediction_label') == 0 else "🚨 Credencial Real"
                if pd.isna(row.get('prediction_label')):
                    ml_val = "Pendiente"

                values = (
                    row['credential_id'],
                    row['credential_type'],
                    row['file_path'][:50] if row['file_path'] else '',
                    row['line_number'],
                    row['severity'],
                    row['commit_sha'][:7],
                    ml_val,
                    row.get('author_name', '')[:30],
                    row.get('commit_date', '')
                )
                
                tag = row['severity']
                self.results_tree.insert('', 'end', values=values, tags=(tag,))
            
            self.update_status(f"Cargadas {len(df)} credenciales detectadas")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error cargando resultados: {str(e)}")
    
    def update_statistics(self):
        """Actualiza las estadísticas y los gráficos del Dashboard"""
        try:
            summary = db_manager.get_repository_summary()
            
            if not summary.empty:
                total_repos = len(summary)
                total_commits = summary['commits_analyzed'].sum()
                total_creds = summary['credentials_count'].sum()
                avg_risk = summary['avg_risk_score'].mean()
                
                # Actualizar Tarjetas (KPIs)
                self.stats_labels['repos'].config(text=str(total_repos))
                self.stats_labels['commits'].config(text=str(total_commits))
                self.stats_labels['credentials'].config(text=str(total_creds))
                self.stats_labels['risk_level'].config(text=f"{avg_risk:.2f}")
                
                # Renderizar Gráficos
                self.render_charts(summary)
            
            self.update_status("Dashboard actualizado con éxito")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error actualizando dashboard: {str(e)}")

    def render_charts(self, summary_df):
        """Genera y muestra los gráficos en el dashboard con estética Cyber-Guard"""
        # Limpiar frames de gráficos previos
        for widget in self.left_chart_frame.winfo_children():
            widget.destroy()
        for widget in self.right_chart_frame.winfo_children():
            widget.destroy()

        # Configuración Global de Estilo Matplotlib para Dark Mode
        plt.rcParams.update({
            'figure.facecolor': self.colors['bg_dark'],
            'axes.facecolor': self.colors['bg_dark'],
            'axes.edgecolor': self.colors['accent'],
            'axes.labelcolor': self.colors['text'],
            'xtick.color': self.colors['text'],
            'ytick.color': self.colors['text'],
            'text.color': self.colors['text'],
            'grid.color': '#444444'
        })

        # --- Gráfico 1: Torta de Severidad ---
        try:
            creds_df = db_manager.get_credentials_dataframe()
            if not creds_df.empty and 'severity' in creds_df.columns:
                sev_counts = creds_df['severity'].value_counts()
                
                fig1, ax1 = plt.subplots(figsize=(5, 4), dpi=100)
                fig1.patch.set_facecolor(self.colors['bg_dark'])
                
                colors_map = {
                    'CRITICAL': self.colors['critical'], 
                    'HIGH': self.colors['high'], 
                    'MEDIUM': self.colors['medium'], 
                    'LOW': self.colors['success']
                }
                c_list = [colors_map.get(s, self.colors['accent']) for s in sev_counts.index]
                
                patches, texts, autotexts = ax1.pie(
                    sev_counts, labels=sev_counts.index, autopct='%1.1f%%', 
                    startangle=90, colors=c_list, 
                    wedgeprops={'edgecolor': self.colors['bg_dark'], 'linewidth': 2}
                )
                
                for text in texts: text.set_color(self.colors['text'])
                for autotext in autotexts: autotext.set_color('black')
                
                ax1.axis('equal')
                
                canvas1 = FigureCanvasTkAgg(fig1, master=self.left_chart_frame)
                canvas1.draw()
                canvas1.get_tk_widget().pack(fill='both', expand=True)
                plt.close(fig1)
        except Exception as e:
            tk.Label(self.left_chart_frame, text=f"⚠️ Error: {e}", bg=self.colors['bg_dark'], fg=self.colors['critical']).pack()

        # --- Gráfico 2: Radar de Proyectos (Solo con hallazgos) ---
        try:
            # FILTRO: Solo repositorios con al menos 1 credencial detectada
            filtered_df = summary_df[summary_df['credentials_count'] > 0].copy()
            
            if not filtered_df.empty:
                fig2, ax2 = plt.subplots(figsize=(5, 4), dpi=100)
                fig2.patch.set_facecolor(self.colors['bg_dark'])
                
                sns.barplot(
                    data=filtered_df, 
                    x='repo_name', 
                    y='credentials_count', 
                    ax=ax2, 
                    palette=[self.colors['accent']],
                    edgecolor=self.colors['text']
                )
                
                ax2.set_title('Detecciones Activas por Proyecto', color=self.colors['accent'], pad=15)
                ax2.set_xticklabels(ax2.get_xticklabels(), rotation=45, ha='right', size=8)
                ax2.set_ylabel('Cant. Hallazgos', color=self.colors['text'])
                ax2.set_xlabel('')
                ax2.grid(axis='y', linestyle='--', alpha=0.3)
                
                plt.tight_layout()
                
                canvas2 = FigureCanvasTkAgg(fig2, master=self.right_chart_frame)
                canvas2.draw()
                canvas2.get_tk_widget().pack(fill='both', expand=True)
                plt.close(fig2)
            else:
                tk.Label(self.right_chart_frame, text="✅ No hay amenazas detectadas", 
                         bg=self.colors['bg_dark'], fg=self.colors['success'], font=('Segoe UI', 10, 'bold')).pack(pady=50)
        except Exception as e:
            tk.Label(self.right_chart_frame, text=f"⚠️ Error: {e}", bg=self.colors['bg_dark'], fg=self.colors['critical']).pack()
    
    def train_model(self):
        """Entrena el modelo de ML"""
        try:
            self.log("\n🤖 Iniciando entrenamiento del modelo ML...")
            
            # Obtener datos de características
            features_df = db_manager.get_commit_features_dataframe()
            
            if features_df.empty or len(features_df) < 10:
                messagebox.showwarning(
                    "Advertencia", 
                    "No hay suficientes datos para entrenar. Analice más repositorios primero."
                )
                return
            
            self.log(f"✓ Datos obtenidos: {len(features_df)} muestras")
            
            # Preparar características - INCLUYENDO INNOVACIÓN
            feature_columns = [
                'has_suspicious_keywords', 'regex_detected_count', 'max_regex_severity',
                'is_sensitive_file', 'commit_hour', 'commit_day_of_week',
                'message_length', 'files_modified', 'code_additions',
                'code_deletions', 'has_config_files', 'has_env_files'
            ]
            
            X = features_df[feature_columns]
            y = features_df['actual_label']
            
            # Preparar datos
            X_train, X_test, y_train, y_test = commit_classifier.prepare_data(
                pd.concat([X, y], axis=1).rename(columns={'actual_label': 'label'})
            )
            
            # Entrenar
            train_metrics = commit_classifier.train(X_train, y_train)
            self.log(f"✓ Modelo entrenado")
            
            # Evaluar
            eval_metrics = commit_classifier.evaluate(X_test, y_test)
            
            # Guardar resultados en BD
            ml_results = {
                'accuracy': eval_metrics['accuracy'],
                'precision': eval_metrics['precision'],
                'recall': eval_metrics['recall'],
                'f1': eval_metrics['f1'],
                'gini_importance': train_metrics['feature_importance'],
                'total_samples': len(features_df),
                'total_features': len(feature_columns)
            }
            
            db_manager.insert_ml_results(ml_results)
            
            # Actualizar GUI
            self.ml_metrics_labels['accuracy'].config(text=f"{eval_metrics['accuracy']:.4f}")
            self.ml_metrics_labels['f1'].config(text=f"{eval_metrics['f1']:.4f}")
            
            self.log("✓ Entrenamiento completado exitosamente")
            
            messagebox.showinfo(
                "Éxito", 
                f"Modelo entrenado exitosamente\nF1-Score: {eval_metrics['f1']:.4f}"
            )
            
        except Exception as e:
            self.log(f"✗ Error entrenando modelo: {str(e)}")
            messagebox.showerror("Error", f"Error entrenando modelo: {str(e)}")
    
    def show_feature_importance(self):
        """Muestra la importancia de características"""
        if not commit_classifier.feature_importance:
            messagebox.showwarning("Advertencia", "Debe entrenar el modelo primero")
            return
        
        self.ml_detail_text.delete('1.0', 'end')
        self.ml_detail_text.insert('end', "IMPORTANCIA DE CARACTERÍSTICAS (basada en Gini):\n\n")
        
        for feature, importance in commit_classifier.feature_importance.items():
            self.ml_detail_text.insert('end', f"{feature:30s}: {importance:.6f}\n")
    
    def show_gini_explanation(self):
        """Muestra explicación del índice de Gini"""
        explanation = commit_classifier.get_gini_impurity_explanation()
        
        self.ml_detail_text.delete('1.0', 'end')
        self.ml_detail_text.insert('end', explanation)
    
    def show_model_info(self):
        """Muestra información del modelo"""
        if commit_classifier.model is None:
            messagebox.showinfo("Información", "No hay modelo entrenado aún")
            return
        
        info = f"""
INFORMACIÓN DEL MODELO DE MACHINE LEARNING

Algoritmo: Árbol de Decisión CART
Criterio: Índice de Gini
Biblioteca: scikit-learn

Configuración:
- Max Depth: {commit_classifier.config['max_depth']}
- Min Samples Split: {commit_classifier.config['min_samples_split']}
- Random State: {commit_classifier.config['random_state']}

Características utilizadas: {len(commit_classifier.feature_names)}
{', '.join(commit_classifier.feature_names)}

El modelo clasifica commits como "seguros" o "riesgosos" basándose en:
- Patrones temporales
- Características del mensaje
- Cambios en el código
- Tipos de archivos modificados
        """
        
        messagebox.showinfo("Información del Modelo", info)
    
    def visualize_tree(self):
        """Visualiza el árbol de decisión"""
        if commit_classifier.model is None:
            messagebox.showwarning("Advertencia", "Debe entrenar el modelo primero")
            return
        
        try:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
            )
            
            if filepath:
                commit_classifier.visualize_tree(output_path=filepath)
                messagebox.showinfo("Éxito", f"Árbol guardado en:\n{filepath}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Error visualizando árbol: {str(e)}")
    
    def export_results(self):
        """Exporta los resultados"""
        try:
            df = db_manager.get_credentials_dataframe()
            
            if df.empty:
                messagebox.showwarning("Advertencia", "No hay datos para exportar")
                return
            
            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if filepath:
                df.to_csv(filepath, index=False)
                messagebox.showinfo("Éxito", f"Datos exportados a:\n{filepath}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Error exportando: {str(e)}")
    
    def export_to_csv(self):
        """Exporta la tabla actual a CSV"""
        self.export_results()
    
    def show_about(self):
        """Muestra información sobre la aplicación"""
        about_text = """
GitHub Repository Analyzer - ML

Herramienta de análisis de repositorios GitHub
que detecta credenciales expuestas y analiza
commits usando Machine Learning.

Características:
• Detección de credenciales con regex
• Análisis de commits de GitHub
• Clasificación ML con árboles CART
• Índice de Gini para pureza de nodos
• Base de datos PostgreSQL
• Interfaz gráfica con tkinter

Tecnologías:
- Python 3.x
- PostgreSQL
- scikit-learn (CART)
- pandas
- GitHub API
- tkinter

Proyecto de Grado 2024
        """
        messagebox.showinfo("Acerca de", about_text)


def main():
    """Función principal"""
    root = tk.Tk()
    app = GitHubAnalyzerGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()