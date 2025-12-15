# =============================================================================
#  ROBOT XM - SUITE INTEGRADA (v14 - FINAL + LAYOUT OPTIMIZADO + TOOLTIPS)
#  Funcionalidades:
#  1. Descarga FTP Automática.
#  2. Base de Datos SQLite.
#  3. Reportes Excel.
#  4. VISUALIZADOR AVANZADO (Con Tooltips en valores largos).
#  5. Logo Corporativo.
# =============================================================================

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import json
import os
import sys
import threading
import ftplib
import ssl
import pandas as pd
import sqlite3
import glob
import re
import csv
from datetime import datetime, timedelta
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
import socket
from typing import List, Tuple
from functools import partial

# --- LIBRERÍAS GRÁFICAS ---
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.dates as mdates
import matplotlib.ticker as ticker

# Intentar importar Pillow
try:
    from PIL import Image, ImageTk
    TIENE_PILLOW = True
    # compatibilidad: Image.Resampling existe en Pillow >= 9.1.0
    RESAMPLE_LANCZOS = getattr(Image, "Resampling", Image).LANCZOS
except ImportError:
    TIENE_PILLOW = False
    RESAMPLE_LANCZOS = None
except Exception:
    RESAMPLE_LANCZOS = None

# Silenciar advertencias
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# --- CONSTANTES ---
NOMBRE_DB_FILE = "BaseDatosXM.db"
NOMBRE_REPORTE_FILE = "Reporte_Horizontal_XM.xlsx"
ARCHIVO_CONFIG = "config_app.json"
ARCHIVOS_MENSUALES = ['PEI', 'PME140', 'tserv', 'afac']
LOGO_FILENAME = "logo_empresa.png"

# COLORES
COLORES_GRAFICO = {
    "Verde Corporativo": "#6E9D2F",
    "Azul Corporativo": "#0088C2",
    "Rojo Intenso": "#e74c3c",
    "Naranja": "#f39c12",
    "Morado": "#9b59b6",
    "Gris Oscuro": "#3E5770",
    "Negro": "#000000"
}

import logging
import logging.handlers

# --- CONFIGURACIÓN DE LOGGING ---
def setup_logging():
    logger = logging.getLogger("RobotXM")
    logger.setLevel(logging.INFO)
    
    # Formato
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    
    # Handler Archivo (Rotativo 5MB x 3 backups)
    fh = logging.handlers.RotatingFileHandler("robot_xm.log", maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    # Handler Consola (Para que PrintRedirector lo capture)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    ch.setLevel(logging.INFO)
    logger.addHandler(ch)
    
    return logger

log = setup_logging()

# --- CONSTANTES DE OPTIMIZACIÓN ---
DEFAULT_WORKERS = 4
FTP_CONNECT_TIMEOUT = 30
FTP_RETRIES = 3
RETRY_BACKOFF = 2.0 


# =============================================================================
#  CLASE PARA REDIRIGIR LA CONSOLA
# =============================================================================
class PrintRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, str_val):
        try:
            str_val = str(str_val) # Enforce string
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, str_val)
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
            self.text_widget.update_idletasks()
        except tk.TclError:
            pass # Widget destroyed
        except Exception:
            pass # Ignorar otros errores de UI logging

    def flush(self): pass

# =============================================================================
#  NUEVA CLASE: DROPDOWN CON TOOLTIP (Integración solicitada)
# =============================================================================
class CustomDropdownWithTooltip:
    """Dropdown searchable con tooltip para items largos.
    Mejoras:
      - Corrige errores de width/variables no definidas.
      - Inicializa atributos (listbox).
      - Maneja Escape y FocusOut para cerrar dropdown.
      - No depender de overrideredirect exclusivamente (pero permite usarlo).
    Uso:
      cb = CustomDropdownWithTooltip(parent, textvariable=var, width=25, command=callback)
      cb.entry.grid(...)  # el Entry es el widget visible
      cb.update_items(['A','B', ...])
    """
    def __init__(self, master, textvariable=None, width=18, command=None, tooltip_threshold=15, dropdown_height=160):
        self.master = master
        self.items = []
        self.filtered_items = []
        self.textvariable = textvariable
        self.command = command
        self.tooltip_threshold = tooltip_threshold
        self.dropdown_height = dropdown_height

        self.entry = ttk.Entry(master, width=width, textvariable=self.textvariable)
        self.entry.bind("<Button-1>", self.show_dropdown)
        self.entry.bind("<KeyRelease>", self.filter_items)
        self.entry.bind("<Down>", self.focus_listbox)
        self.entry.bind("<Escape>", lambda e: self.close_dropdown())

        # initialize attributes
        self.dropdown = None
        self.tooltip = None
        self.listbox = None
        self.current_index = None

    def focus_listbox(self, event=None):
        if not self.dropdown:
            self.show_dropdown()
        if self.listbox:
            self.listbox.focus_set()
            # ensure selection visible
            if self.listbox.size() > 0:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(0)
                self.listbox.activate(0)

    def update_items(self, new_items):
        self.items = [str(x) for x in new_items]
        self.filtered_items = self.items[:]

    def show_dropdown(self, event=None):
        # Si está deshabilitado, no hacer nada
        if str(self.entry['state']) == 'disabled': return

        # toggle
        if self.dropdown:
            self.close_dropdown()
            return

        # create dropdown Toplevel
        self.dropdown = tk.Toplevel(self.master)
        # Use transient and topmost to avoid some overrideredirect issues
        try:
            self.dropdown.wm_overrideredirect(True)
            self.dropdown.attributes("-topmost", True)
        except Exception:
            # fallback for platforms that don't support attributes
            pass

        # compute position relative to entry
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        w_pixels = max(self.entry.winfo_width(), 150)

        # geometry: width x height + x + y
        height = self.dropdown_height
        self.dropdown.geometry(f"{w_pixels}x{height}+{x}+{y}")

        # frame + scrollbar + listbox
        frame_list = tk.Frame(self.dropdown, bd=0)
        frame_list.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(frame_list, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        chars_w = width_chars(w_pixels)
        self.listbox = tk.Listbox(frame_list, width=chars_w, height=8, yscrollcommand=scrollbar.set,
                                  exportselection=False, bg="#ffffff", fg="#2c3e50",
                                  selectbackground="#0093d0", selectforeground="#ffffff",
                                  font=("Segoe UI", 10), borderwidth=0)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)

        # populate
        self.listbox.delete(0, tk.END)
        for item in self.filtered_items:
            self.listbox.insert(tk.END, item)

        # bindings
        self.listbox.bind("<Motion>", self.on_motion)
        self.listbox.bind("<Leave>", self.hide_tooltip)
        self.listbox.bind("<ButtonRelease-1>", self.select_item)
        self.listbox.bind("<Escape>", lambda e: self.close_dropdown())
        self.dropdown.bind("<FocusOut>", lambda e: self.close_dropdown())

    def on_motion(self, event):
        if not self.listbox:
            return
        index = self.listbox.nearest(event.y)
        if index >= 0 and index < self.listbox.size():
            if index != self.current_index:
                self.current_index = index
                self.show_tooltip(index, event)

    def show_tooltip(self, index, event):
        self.hide_tooltip()
        try:
            text = self.listbox.get(index)
        except Exception:
            return
        if len(text) < self.tooltip_threshold:
            return

        x = event.x_root + 20
        y = event.y_root + 10

        self.tooltip = tk.Toplevel(self.master)
        try:
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.attributes("-topmost", True)
        except:
            pass
        # position
        self.tooltip.geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip, text=text, background="#ffffe0",
                         relief="solid", borderwidth=1,
                         font=("Arial", "9", "normal"), padx=5, pady=2)
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip:
            try:
                self.tooltip.destroy()
            except Exception:
                pass
            self.tooltip = None

    def select_item(self, event=None):
        if not self.listbox:
            return
        selection = self.listbox.curselection()
        if selection:
            index = selection[0]
            val = self.listbox.get(index)
            if self.textvariable:
                self.textvariable.set(val)
            else:
                self.entry.delete(0, tk.END)
                self.entry.insert(0, val)
        self.close_dropdown()
        if self.command:
            try:
                self.command(None)
            except Exception:
                pass

    def close_dropdown(self):
        self.hide_tooltip()
        if self.dropdown:
            try:
                self.dropdown.destroy()
            except Exception:
                pass
            self.dropdown = None
            self.listbox = None
            self.current_index = None

    def filter_items(self, event):
        if event.keysym in ['Down', 'Up', 'Return', 'Escape']:
            return

        query = self.entry.get().lower()
        self.filtered_items = [item for item in self.items if query in item.lower()]

        if self.dropdown and self.listbox:
            # update listbox
            self.listbox.delete(0, tk.END)
            for item in self.filtered_items:
                self.listbox.insert(tk.END, item)
        else:
            if query:
                # show only if there's a query (prevents immediate dropdown on focus)
                self.show_dropdown()


def width_chars(pixels):
    # Estimación aproximada de caracteres basado en pixeles (depende de la fuente)
    return int(pixels / 7)

# ======================
# Card (simple, ttk-based)
# ======================
class Card(ttk.Frame):
    """Card visual mejorada con mejor espaciado, sombra simulada y efecto visual moderno.
    Usa múltiples frames para crear un efecto visual de profundidad y bordes suaves.
    """
    def __init__(self, parent, title=None, icon=None, *args, **kwargs):
        # Frame externo para sombra simulada con padding
        self.shadow_frame = tk.Frame(parent, bg="#e2e8f0")
        
        # Frame intermedio para efecto de profundidad
        self.mid_frame = tk.Frame(self.shadow_frame, bg="#f0f2f5")
        self.mid_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        # Frame principal (card) con padding aumentado
        super().__init__(self.mid_frame, style="Card.TFrame", padding=(20, 16))
        super().pack(fill="both", expand=True)  # Empaquetar el frame interno
        
        # crear header si corresponde
        if title or icon:
            header = ttk.Frame(self, style="CardHeader.TFrame")
            header.pack(fill="x", pady=(0, 12))  # Más espacio (antes 6)
            if icon:
                lbl_icon = ttk.Label(header, text=icon, style="CardIcon.TLabel")
                lbl_icon.pack(side="left", padx=(0, 8), anchor="center")  # Más espacio (antes 4)

            if title:
                lbl_title = ttk.Label(header, text=title, style="CardTitle.TLabel")
                lbl_title.pack(side="left", anchor="w")

        # body: donde el usuario pone widgets
        self.body = ttk.Frame(self, style="CardBody.TFrame")
        self.body.pack(fill="both", expand=True)

    def get_body(self):
        return self.body
    
    def pack(self, **kwargs):
        """Override pack para empaquetar el shadow_frame con padding para sombra"""
        # Agregar padding para simular sombra y efecto visual
        shadow_kwargs = kwargs.copy()
        if 'padx' not in shadow_kwargs:
            shadow_kwargs['padx'] = 3  # Aumentado para mejor efecto
        if 'pady' not in shadow_kwargs:
            shadow_kwargs['pady'] = 3  # Aumentado para mejor efecto
        self.shadow_frame.pack(**shadow_kwargs)

# ======================
# RoundedButtonWrapper (usa ttk.Button + estilo)
# ======================
class RoundedButtonWrapper(ttk.Button):
    """Pequeña envoltura para crear un botón con estilo ya definido en 'configurar_estilos_modernos'.
    Llamar con style='Primary.TButton' o 'Success.TButton' etc.
    """
    def __init__(self, parent, text, command=None, style="Primary.TButton", width=None, *args, **kwargs):
        super().__init__(parent, text=text, command=command, style=style, *args, **kwargs)
        if width:
            try:
                self.configure(width=width)
            except Exception:
                pass


# --- IMPORTS ADICIONALES PARA RED ---
# (Ya importados al inicio)

# =============================================================================
#  MÓDULO DE OPTIMIZACIÓN Y HELPER FUNCTIONS
# =============================================================================

def safe_identifier(name: str) -> str:
    """Valida que el nombre de tabla/columna sea seguro (alfanumérico + guiones bajos)."""
    if not re.match(r'^[A-Za-z0-9_]+$', str(name)):
        raise ValueError(f"Identificador inválido (posible inyección SQL): {name}")
    return name

def generar_fechas_permitidas(fecha_ini, fecha_fin):
    dias = []
    meses = set()
    delta = fecha_fin - fecha_ini
    for i in range(delta.days + 1):
        dia = fecha_ini + timedelta(days=i)
        # Soportar DD (ej. 01) y MMDD (ej. 1101) para archivos diarios
        dias.append(dia.strftime("%d"))
        dias.append(dia.strftime("%m%d"))
        meses.add(dia.strftime("%Y-%m"))
    return dias, meses

def make_ftps_connection(usuario, password):
    context = ssl.create_default_context()
    context.set_ciphers('DEFAULT:@SECLEVEL=1')
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    ftps = ftplib.FTP_TLS(context=context)
    try:
        ftps.connect('xmftps.xm.com.co', 210, timeout=FTP_CONNECT_TIMEOUT)
        ftps.auth()
        ftps.prot_p()
        ftps.login(usuario, password)
    except Exception as e:
        raise Exception(f"Fallo conexión FTP: {e}")
    return ftps



def retrbinary_safe(ftps, cmd, callback, blocksize=8192):
    attempts = 0
    while attempts < FTP_RETRIES:
        try:
            ftps.retrbinary(cmd, callback, blocksize)
            return
        except Exception as e:
            attempts += 1
            if attempts >= FTP_RETRIES: raise e
            time.sleep(RETRY_BACKOFF * attempts)

def descargar_archivos_paralelo(config, lista_tareas, workers=4):
    usuario = config['usuario']
    password = config['password']
    
    def worker(tarea):
        ruta_remota, ruta_local = tarea
        conn = None
        temp_path = ruta_local + ".part"
        try:
            conn = make_ftps_connection(usuario, password)
            with open(temp_path, 'wb') as f:
                retrbinary_safe(conn, f"RETR {ruta_remota}", f.write)
            
            # Validación simple de atomicidad
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                os.replace(temp_path, ruta_local) # Atomic rename
                return (ruta_local, None)
            else:
                return (ruta_local, "Descarga vacía (0 bytes)")
                
        except Exception as e:
            if os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass
            return (ruta_local, str(e))
        finally:
            if conn: 
                try: conn.quit()
                except: pass

    resultados = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_url = {executor.submit(worker, t): t for t in lista_tareas}
        for future in as_completed(future_to_url):
            resultados.append(future.result())
    return resultados

def sqlite_fast_connect(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
    except: pass
    return conn

def bulk_insert_fast(conn, ruta_csv, tabla, meta_cols, chunksize=50000):
    # Validar nombre tabla
    tabla = safe_identifier(tabla)
    
    total_rows = 0
    # Detectar encoding o usar latin-1 por defecto (común en XM)
    try:
        with open(ruta_csv, newline='', encoding='latin-1') as f:
            reader = csv.DictReader(f, delimiter=';', skipinitialspace=True)
            if not reader.fieldnames: return 0
            
            # Normalizar columnas: quitar paréntesis y caracteres extraños de los headers del CSV
            def clean_col_name(c):
                # 1. Match v12 logic: strip, lower, space->underscore
                # Permite parentesis (ej: "fecha_(hora)") evitando duplicados.
                s = c.strip().replace(' ', '_').lower()
                # 2. Safety: Quitar comillas dobles para no romper la query SQL construida manualmente
                return s.replace('"', '')

            cols_csv = [clean_col_name(c) for c in reader.fieldnames]
            
            # Columnas totales = CSV + Meta
            all_cols = cols_csv + list(meta_cols.keys())
            
            # --- AUTO-CREATE TABLE IF NOT EXISTS ---
            # Usamos comillas dobles para soportar nombres reservados (ej. "index", "group")
            defs = [f'"{c}" TEXT' for c in all_cols]
            create_sql = f'CREATE TABLE IF NOT EXISTS "{tabla}" ({", ".join(defs)})'
            try:
                conn.execute(create_sql)
            except Exception as e:
                log.error(f"Error creando tabla {tabla}: {e}")
                raise e

            # Verificar si hay columnas nuevas
            try:
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info(\"{tabla}\")")
                existing_cols = {row[1] for row in cursor.fetchall()}
                for c in all_cols:
                    if c not in existing_cols:
                        try:
                            conn.execute(f'ALTER TABLE "{tabla}" ADD COLUMN "{c}" TEXT')
                            log.info(f"Columna nueva agregada a {tabla}: {c}")
                        except: pass 
            except: pass
            # ----------------------------------------

            cols_quoted = [f'"{c}"' for c in all_cols]
            placeholders = ",".join(["?"] * len(all_cols))
            
            sql = f'INSERT INTO "{tabla}" ({",".join(cols_quoted)}) VALUES ({placeholders})'
            
            batch = []
            
            conn.execute("BEGIN TRANSACTION")
            try:
                for row in reader:
                    # Extraer valores del CSV
                    vals = [row[k] for k in reader.fieldnames]
                    # Agregar metadata
                    vals.extend(meta_cols.values())
                    
                    batch.append(vals)
                    
                    if len(batch) >= chunksize:
                        conn.executemany(sql, batch)
                        total_rows += len(batch)
                        batch = []
                
                if batch:
                    conn.executemany(sql, batch)
                    total_rows += len(batch)
                
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
                
    except Exception as e:
        raise e
        
    return total_rows

def ensure_indexes(conn, tabla, cols):
    for col in cols:
        try: conn.execute(f'CREATE INDEX IF NOT EXISTS "idx_{tabla}_{col}" ON "{tabla}"("{col}")')
        except: pass

def proceso_descarga(config, es_reintento=False):
    if es_reintento: log.warning("--- 🔄 INICIANDO FASE DE RECUPERACIÓN (RE-DESCARGA) ---")
    else: log.info("--- INICIANDO FASE 1: DESCARGA DE ARCHIVOS (PARALELA) ---")
    
    usuario = config['usuario']
    password = config['password']
    ruta_local_base = config['ruta_local']
    
    try:
        fecha_ini = datetime.strptime(config['fecha_ini'], "%Y-%m-%d")
        fecha_fin = datetime.strptime(config['fecha_fin'], "%Y-%m-%d")
    except ValueError:
        log.error("❌ Error: Formato de fecha inválido. Use YYYY-MM-DD")
        return

    lista_archivos = config['archivos_descarga'] 
    dias_permitidos, meses_permitidos = generar_fechas_permitidas(fecha_ini, fecha_fin)

    log.info("🔎 Buscando archivos en el servidor...")
    tareas_descarga = [] 
    
    try:
        ftps = make_ftps_connection(usuario, password)
    except Exception as e:
        log.error(f"❌ No se pudo conectar para listar: {e}")
        return

    mapa_archivos = {} 
    for item in lista_archivos:
        r = item['ruta_remota']
        if r not in mapa_archivos: mapa_archivos[r] = []
        mapa_archivos[r].append(item['nombre_base'])

    for anio_mes in sorted(list(meses_permitidos)):
        mes_actual_str = anio_mes.split("-")[1] 
        ruta_local_mes = os.path.join(ruta_local_base, anio_mes)
        if not os.path.exists(ruta_local_mes): os.makedirs(ruta_local_mes)

        for ruta_remota_base, nombres_base in mapa_archivos.items():
            ruta_remota_base = str(ruta_remota_base).strip()
            if ruta_remota_base.endswith("/"): ruta_final = f"{ruta_remota_base}{anio_mes}"
            elif ruta_remota_base.endswith(anio_mes): ruta_final = ruta_remota_base
            else: ruta_final = f"{ruta_remota_base}/{anio_mes}"

            try:
                ftps.cwd(ruta_final)
                archivos_en_servidor = ftps.nlst()
            except: continue

            for nombre_base in nombres_base:
                nombre_base = str(nombre_base).strip()
                nombre_base_lower = nombre_base.lower()
                es_mensual = False
                for especial in ARCHIVOS_MENSUALES:
                    if nombre_base_lower == especial.lower():
                        es_mensual = True
                        break
                coincidencias = []
                if es_mensual:
                    patron_esperado = f"{nombre_base}{mes_actual_str}".lower()
                    for f in archivos_en_servidor:
                        if os.path.basename(f).lower().startswith(patron_esperado): coincidencias.append(f"{ruta_final}/{f}")
                else:
                    for f in archivos_en_servidor:
                        nombre_archivo = os.path.basename(f).lower()
                        if not nombre_archivo.startswith(nombre_base_lower): continue
                        for dia in dias_permitidos:
                            if dia in nombre_archivo:
                                coincidencias.append(f"{ruta_final}/{f}")
                                break 
                
                for archivo_full in coincidencias:
                    nombre_limpio = os.path.basename(archivo_full)
                    ruta_destino = os.path.join(ruta_local_mes, nombre_limpio)
                    if os.path.exists(ruta_destino) and os.path.getsize(ruta_destino) > 0: continue 
                    tareas_descarga.append((archivo_full, ruta_destino))

    try: ftps.quit()
    except: pass
    
    total_archivos = len(tareas_descarga)
    if total_archivos == 0:
        log.info("✅ Todo actualizado.")
        return

    log.info(f"⬇️ Iniciando descarga de {total_archivos} archivos...")
    resultados = descargar_archivos_paralelo(config, tareas_descarga, workers=DEFAULT_WORKERS)
    
    errores = [r for r in resultados if r[1] is not None]
    exitos = len(resultados) - len(errores)
    
    log.info(f"   ✅ Éxitos: {exitos}")
    if errores:
        log.error(f"   ❌ Errores: {len(errores)}")
        for path, err in errores[:5]:
            log.error(f"      - {os.path.basename(str(path))}: {err}")

# =============================================================================
#  MÓDULO 1: LÓGICA DE NEGOCIO
# =============================================================================

def extraer_info_nombre(nombre_archivo):
    nombre_base, extension = os.path.splitext(nombre_archivo)
    extension = extension.replace(".", "")
    for especial in ARCHIVOS_MENSUALES:
        if nombre_base.upper().startswith(especial.upper()):
            return especial, nombre_base[len(especial):], extension
    match = re.search(r"\d", nombre_base)
    if match: return nombre_base[:match.start()], nombre_base[match.start():], extension
    else: return nombre_base, "0000", extension

def obtener_anio_de_carpeta(ruta_completa):
    try:
        carpeta_padre = os.path.basename(os.path.dirname(ruta_completa))
        if "-" in carpeta_padre: return carpeta_padre.split("-")[0]
        return carpeta_padre
    except: return "0000"

def cargar_cache_archivos_existentes(cursor):
    log.info("🧠 Cargando memoria de archivos procesados...")
    cache = set()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        for (tabla,) in cursor.fetchall():
            try:
                cursor.execute(f"PRAGMA table_info({tabla})")
                cols = [info[1] for info in cursor.fetchall()]
                if 'origen_archivo' in cols:
                    cursor.execute(f"SELECT DISTINCT origen_archivo FROM {tabla}")
                    for (archivo,) in cursor.fetchall():
                        if archivo: cache.add(archivo)
            except: pass
    except: pass
    log.info(f"🧠 Memoria lista: {len(cache)} archivos.")
    return cache

def proceso_base_datos(config, es_reintento=False):
    if es_reintento: log.warning("--- 🔄 INICIANDO FASE DE PROCESAMIENTO (INTENTO #2) ---")
    else: log.info("--- INICIANDO FASE 2: ACTUALIZACIÓN DE BASE DE DATOS (OPTIMIZADA) ---")
    ruta_descargas = config['ruta_local']
    ruta_db_completa = os.path.join(ruta_descargas, NOMBRE_DB_FILE)
    try:
        fecha_ini = datetime.strptime(config['fecha_ini'], "%Y-%m-%d")
        fecha_fin = datetime.strptime(config['fecha_fin'], "%Y-%m-%d")
    except: return False
    dias_permitidos, meses_permitidos = generar_fechas_permitidas(fecha_ini, fecha_fin)
    
    log.info(f"🔌 Conectando a BD (Fast Mode): {ruta_db_completa}")
    # Usar conexión optimizada
    conn = sqlite_fast_connect(ruta_db_completa)
    cursor = conn.cursor()
    archivos_procesados_cache = cargar_cache_archivos_existentes(cursor)
    
    log.info(f"📂 Escaneando archivos locales...")
    patron = os.path.join(ruta_descargas, "**", "*.tx*")
    archivos = glob.glob(patron, recursive=True)
    log.info(f"🔍 Se encontraron {len(archivos)} archivos. Filtrando...")

    corruptos_eliminados = 0
    tablas_tocadas = set()

    for ruta_completa in archivos:
        nombre_archivo = os.path.basename(ruta_completa)
        if nombre_archivo in archivos_procesados_cache: continue
        nombre_tabla, fecha_identificador, version = extraer_info_nombre(nombre_archivo)
        anio_carpeta = obtener_anio_de_carpeta(ruta_completa)
        es_valido = False
        if nombre_tabla in ARCHIVOS_MENSUALES:
            if f"{anio_carpeta}-{fecha_identificador}" in meses_permitidos: es_valido = True
        else:
            if fecha_identificador in dias_permitidos: es_valido = True
        if not es_valido: continue

        # Validación preliminar ligera
        archivo_corrupto = False
        razon = ""
        size_bytes = os.path.getsize(ruta_completa)
        if size_bytes == 0:
            archivo_corrupto = True; razon = "0 bytes"
        
        if archivo_corrupto:
            log.warning(f"🗑️ Corrupto ({razon}): {nombre_archivo} -> ELIMINADO")
            try: os.remove(ruta_completa)
            except: pass
            corruptos_eliminados += 1
            continue
            
        try:
            # Metadata a inyectar
            meta = {
                'origen_archivo': nombre_archivo,
                'anio': anio_carpeta,
                'mes_dia': fecha_identificador,
                'version_dato': version,
                'fecha_carga': str(pd.Timestamp.now())
            }
            
            # Insertar en chunks (Optimizado con executemany)
            rows = bulk_insert_fast(conn, ruta_completa, nombre_tabla, meta, chunksize=50000)
            
            if rows > 0:
                archivos_procesados_cache.add(nombre_archivo)
                tablas_tocadas.add(nombre_tabla)
                log.info(f"💾 Guardado ({rows} filas): {nombre_archivo}")
            else:
                # Si no se insertó nada (pero no falló), asumimos vacío
                raise Exception("Archivo vacío o sin datos válidos")
                
        except Exception as e:
            # Detectar archivos vacíos o corruptos
            if "No columns to parse" in str(e) or "registros" in str(e).lower() or "vacío" in str(e).lower():
                log.warning(f"🗑️ Archivo vacío detectado: {nombre_archivo}")
                try: os.remove(ruta_completa)
                except: pass
                corruptos_eliminados += 1
            else:
                log.error(f"⚠️ Error leyendo {nombre_archivo}: {e}")

    # Finalizar: Crear índices en tablas afectadas
    if tablas_tocadas:
        log.info("🔨 Optimizando índices...")
        for t in tablas_tocadas:
            ensure_indexes(conn, t, ['anio', 'mes_dia', 'version_dato', 'origen_archivo'])
            
    conn.close()
    log.info(f"✅ FASE {'2' if not es_reintento else 'RECUPERACIÓN'} TERMINADA.")
    if corruptos_eliminados > 0: return True 
    return False

def calcular_peso_version(extension):
    if not isinstance(extension, str): return 0
    ext = extension.lower().strip().replace('.', '')
    if ext == 'tx1': return 1
    if ext == 'tx2': return 2
    if ext == 'txr': return 3
    if ext == 'txf': return 10
    if ext == 'txa': return 10 
    match = re.search(r'tx(\d+)', ext)
    if match:
        num = int(match.group(1))
        if num > 2: return 10 + num 
    return 0 

def generar_reporte_logica(config):
    log.info("🚀 INICIANDO GENERADOR HORIZONTAL XM")
    ruta_local = config['ruta_local']
    ruta_db_completa = os.path.join(ruta_local, NOMBRE_DB_FILE)
    ruta_reporte_completa = os.path.join(ruta_local, NOMBRE_REPORTE_FILE)
    try:
        fecha_ini = pd.to_datetime(config['fecha_ini'])
        fecha_fin = pd.to_datetime(config['fecha_fin'])
    except: return

    tareas_a_procesar = []
    # EL REPORTE SE GENERA EN EL ORDEN QUE ESTÉN EN LA CONFIGURACIÓN
    for item in config['filtros_reporte']:
        tareas_a_procesar.append({
            'tabla_solicitada': item['tabla'],
            'filtro_campo': item.get('campo'),
            'filtro_valor': item.get('valor'),
            'filtro_version': item.get('version')
        })

    if not os.path.exists(ruta_db_completa):
        log.error(f"❌ No existe la BD en: {ruta_db_completa}")
        return

    conn = sqlite3.connect(ruta_db_completa)
    cursor = conn.cursor()
    log.info(f"⚙️ Generando reporte en: {ruta_reporte_completa}")
    
    try:
        with pd.ExcelWriter(ruta_reporte_completa, engine='openpyxl') as writer:
            columna_actual = 0  
            tablas_escritas = 0
            for tarea in tareas_a_procesar:
                tabla_solicitada = tarea['tabla_solicitada']
                col_filtro_usuario = tarea['filtro_campo']
                val_filtro_usuario = tarea['filtro_valor']
                ver_filtro_usuario = tarea['filtro_version']
                
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND lower(name)='{tabla_solicitada.lower()}'")
                resultado = cursor.fetchone()
                if not resultado:
                    print(f"   ⚠️ Tabla '{tabla_solicitada}' no encontrada.")
                    continue
                nombre_real_bd = resultado[0]
                # Quote table name
                query = f'SELECT * FROM "{nombre_real_bd}" WHERE 1=1'
                titulo_texto = f"ARCHIVO: {tabla_solicitada.upper()}"

                if col_filtro_usuario and val_filtro_usuario:
                    # Quote table name in PRAGMA
                    cursor.execute(f'PRAGMA table_info("{nombre_real_bd}")')
                    columnas_bd = cursor.fetchall()
                    nombre_columna_real = None
                    for col_info in columnas_bd:
                        if col_info[1].lower() == col_filtro_usuario.lower():
                            nombre_columna_real = col_info[1]
                            break
                    if nombre_columna_real:
                        # Quote column name
                        query += f" AND CAST(\"{nombre_columna_real}\" AS TEXT) = '{val_filtro_usuario}'"
                        titulo_texto += f" ({val_filtro_usuario})"
                    else: print(f"   ⚠️ Campo '{col_filtro_usuario}' no existe.")

                if ver_filtro_usuario and ver_filtro_usuario != "Última":
                    query += f" AND \"version_dato\" = '{ver_filtro_usuario}'"
                    titulo_texto += f" [Ver: {ver_filtro_usuario}]"
                    print(f"   🔹 Procesando: {nombre_real_bd} (Filtro Ver: {ver_filtro_usuario})")
                else: 
                    # Si es "Última" o vacío, entra aquí -> Versión Automática
                    ver_filtro_usuario = None # Forzamos None para activar lógica posterior
                    print(f"   🔹 Procesando: {nombre_real_bd} (Versión Automática)")

                try:
                    df = pd.read_sql_query(query, conn)
                    if df.empty: continue
                    
                    cols_no = ['index', 'anio', 'mes_dia', 'version_dato', 'origen_archivo', 'fecha_carga']
                    for col in df.columns:
                        if col not in cols_no and df[col].dtype == 'object':
                            try: df[col] = pd.to_numeric(df[col])
                            except: pass

                    def armar_fecha(row):
                        try:
                            anio = str(row['anio']); md = str(row['mes_dia']).zfill(4)
                            if len(str(row['mes_dia'])) <= 2: return pd.to_datetime(f"{anio}-{str(row['mes_dia']).zfill(2)}-01")
                            else: return pd.to_datetime(f"{anio}-{md[:2]}-{md[2:]}")
                        except: return pd.NaT

                    df['Fecha'] = df.apply(armar_fecha, axis=1)
                    cols = ['Fecha'] + [c for c in df.columns if c != 'Fecha']
                    df = df[cols]
                    df = df[(df['Fecha'] >= fecha_ini) & (df['Fecha'] <= fecha_fin)]
                    if df.empty: 
                        print("   ⚠️ Rango de fechas vacío. (¿Actualizaste la BD con la Descarga?)")
                        continue

                    df['Fecha'] = df['Fecha'].dt.date

                    if ver_filtro_usuario:
                        df_final = df.sort_values(by='Fecha', ascending=True)
                    else:
                        df['peso_version'] = df['version_dato'].apply(calcular_peso_version)
                        df['max_peso_dia'] = df.groupby('Fecha')['peso_version'].transform('max')
                        df_final = df[df['peso_version'] == df['max_peso_dia']].copy()
                        df_final = df_final.sort_values(by='Fecha', ascending=True)
                    
                    cols_borrar = ['peso_version', 'max_peso_dia', 'origen_archivo', 'anio', 'mes_dia', 'fecha_carga']
                    df_final = df_final.drop(columns=[c for c in cols_borrar if c in df_final.columns], errors='ignore')
                    
                    pd.DataFrame({titulo_texto: []}).to_excel(writer, sheet_name="Datos", startrow=0, startcol=columna_actual, index=False)
                    df_final.to_excel(writer, sheet_name="Datos", startrow=1, startcol=columna_actual, index=False)
                    columna_actual += len(df_final.columns) + 1 
                    tablas_escritas += 1
                except Exception as e: log.error(f"      ❌ Error interno: {e}")
        conn.close()
        if tablas_escritas > 0: log.info(f"✅ REPORTE LISTO: {ruta_reporte_completa}")
        else: log.warning("⚠️ Reporte vacío.")
    except Exception as e: log.error(f"❌ Error guardando Excel: {e}")

# =============================================================================
#  MÓDULO 4: VISUALIZADOR (INTEGRADO EN PESTAÑA)
# =============================================================================

class ModuloVisualizador:
    def __init__(self, parent_frame, config):
        self.frame_main = parent_frame 
        # Cargar ruta desde config o usar default
        self.ruta_db = config.get('ruta_db_viz', "BaseDatosXM.db")
        self.datos_actuales = None 
        
        self.var_tabla = tk.StringVar(); self.var_version = tk.StringVar()
        self.var_campo_filtro1 = tk.StringVar(); self.var_valor_filtro1 = tk.StringVar()
        self.var_campo_filtro2 = tk.StringVar(); self.var_valor_filtro2 = tk.StringVar()
        self.var_campo_valor = tk.StringVar(); self.var_agregacion = tk.StringVar(value="Promedio")
        self.var_tipo_grafico = tk.StringVar(value="Línea")
        self.var_color_grafico = tk.StringVar(value="Verde Corporativo")
        self.var_fecha_ini = tk.StringVar(); self.var_fecha_fin = tk.StringVar()
        self.var_temporalidad = tk.StringVar(value="Diaria")

        frame_top = ttk.Frame(self.frame_main, padding=3)  # Reducido de 5 a 3
        frame_top.pack(fill="x")
        ttk.Label(frame_top, text="BD Gráfica:").pack(side="left")
        self.lbl_db = ttk.Entry(frame_top, width=60)
        self.lbl_db.pack(side="left", padx=5)
        self.lbl_db.insert(0, os.path.abspath(self.ruta_db))
        ttk.Button(frame_top, text="📂", command=self.seleccionar_db).pack(side="left")
        ttk.Button(frame_top, text="🔄 Leer Tablas", command=self.cargar_tablas, style="Primary.TButton").pack(side="left", padx=5)

        # --- LAYOUT OPTIMIZADO (3 COLUMNAS) ---
        frame_controls = ttk.Frame(self.frame_main)
        frame_controls.pack(fill="x", padx=5, pady=2)  # Reducido de pady=5 a pady=2

        # COLUMNA 1: FUENTE DE DATOS
        col1 = ttk.LabelFrame(frame_controls, text="1. Fuente de Datos")
        col1.pack(side="left", fill="both", expand=True, padx=5)
        
        ttk.Label(col1, text="Archivo:").grid(row=0, column=0, sticky="w", pady=2, padx=5)  # Reducido de pady=5 a pady=2
        self.cb_tabla = ttk.Combobox(col1, textvariable=self.var_tabla, state="readonly", width=18)
        self.cb_tabla.grid(row=0, column=1, padx=2); self.cb_tabla.bind("<<ComboboxSelected>>", self.al_seleccionar_tabla)

        ttk.Label(col1, text="Versión:").grid(row=1, column=0, sticky="w", pady=1, padx=5)  # Reducido de pady=2 a pady=1
        self.cb_version = ttk.Combobox(col1, textvariable=self.var_version, state="readonly", width=18)
        self.cb_version.grid(row=1, column=1, padx=2)

        ttk.Label(col1, text="Filtro 1:").grid(row=2, column=0, sticky="w", pady=1, padx=5)  # Reducido de pady=2 a pady=1
        ttk.Label(col1, text="Filtro 1:").grid(row=2, column=0, sticky="w", pady=1, padx=5)  # Duplicado, pero mantenemos reducido
        # REEMPLAZO COMBOBOX POR CUSTOM SEARCHABLE
        self.cb_campo_filtro1 = CustomDropdownWithTooltip(col1, textvariable=self.var_campo_filtro1, width=25, command=self.al_seleccionar_campo_filtro1)
        self.cb_campo_filtro1.entry.grid(row=2, column=1, padx=2, pady=1)  # Reducido de pady=2 a pady=1
        # self.cb_campo_filtro1.bind("<<ComboboxSelected>>", self.al_seleccionar_campo_filtro1) # YA NO SE USA BIND, SE USA COMMAND
        
        # --- CAMBIO: INTEGRACIÓN DE TOOLTIP CUSTOM DROPDOWN ---
        # Reemplazamos el Combobox de Valor 1 por la clase custom
        self.cb_valor_filtro1 = CustomDropdownWithTooltip(col1, textvariable=self.var_valor_filtro1, width=25)
        self.cb_valor_filtro1.entry.grid(row=3, column=1, padx=2, pady=1)  # Reducido de pady=2 a pady=1
        # --------------------------------------------------------

        ttk.Label(col1, text="Filtro 2 (opc):").grid(row=4, column=0, sticky="w", pady=1, padx=5)  # Reducido de pady=2 a pady=1
        ttk.Label(col1, text="Filtro 2 (opc):").grid(row=4, column=0, sticky="w", pady=1, padx=5)  # Duplicado, pero mantenemos reducido
        # REEMPLAZO COMBOBOX POR CUSTOM SEARCHABLE
        self.cb_campo_filtro2 = CustomDropdownWithTooltip(col1, textvariable=self.var_campo_filtro2, width=25, command=self.al_seleccionar_campo_filtro2)
        self.cb_campo_filtro2.entry.grid(row=4, column=1, padx=2)
        # self.cb_campo_filtro2.bind("<<ComboboxSelected>>", self.al_seleccionar_campo_filtro2) # YA NO SE USA BIND
        
        # --- CAMBIO: INTEGRACIÓN DE TOOLTIP CUSTOM DROPDOWN ---
        # Reemplazamos el Combobox de Valor 2 por la clase custom
        self.cb_valor_filtro2 = CustomDropdownWithTooltip(col1, textvariable=self.var_valor_filtro2, width=25)
        self.cb_valor_filtro2.entry.grid(row=5, column=1, padx=2, pady=2)  # Mantenemos pady=2 solo en el último elemento
        # --------------------------------------------------------

        # COLUMNA 2: CONFIGURACIÓN
        col2 = ttk.LabelFrame(frame_controls, text="2. Configuración")
        col2.pack(side="left", fill="both", expand=True, padx=5)

        ttk.Label(col2, text="Temporalidad:").grid(row=0, column=0, sticky="w", pady=2, padx=5)  # Reducido de pady=5 a pady=2
        self.cb_temporalidad = ttk.Combobox(col2, textvariable=self.var_temporalidad, state="readonly", width=18)
        self.cb_temporalidad['values'] = ["Diaria", "Mensual", "Horaria (24h)"]
        self.cb_temporalidad.grid(row=0, column=1, padx=2)
        self.cb_temporalidad.bind("<<ComboboxSelected>>", self.toggle_campo_valor)

        self.lbl_valor = ttk.Label(col2, text="Variable:")
        self.lbl_valor.grid(row=1, column=0, sticky="w", pady=1, padx=5)  # Reducido de pady=2 a pady=1
        # REEMPLAZO COMBOBOX POR CUSTOM SEARCHABLE
        self.cb_campo_valor = CustomDropdownWithTooltip(col2, textvariable=self.var_campo_valor, width=25)
        self.cb_campo_valor.entry.grid(row=1, column=1, padx=2)

        ttk.Label(col2, text="Operación:").grid(row=2, column=0, sticky="w", pady=1, padx=5)  # Reducido de pady=2 a pady=1
        self.cb_agregacion = ttk.Combobox(col2, textvariable=self.var_agregacion, state="readonly", width=18)
        self.cb_agregacion['values'] = ["Valor", "Promedio", "Suma", "Máximo", "Mínimo"]; self.cb_agregacion.current(0)
        self.cb_agregacion.grid(row=2, column=1, padx=2)

        ttk.Label(col2, text="Tipo:").grid(row=3, column=0, sticky="w", pady=1, padx=5)  # Reducido de pady=2 a pady=1
        self.cb_tipo = ttk.Combobox(col2, textvariable=self.var_tipo_grafico, state="readonly", width=18)
        self.cb_tipo['values'] = ["Línea", "Barras", "Área", "Dispersión"]; self.cb_tipo.current(0)
        self.cb_tipo.grid(row=3, column=1, padx=2)

        ttk.Label(col2, text="Color:").grid(row=4, column=0, sticky="w", pady=1, padx=5)  # Reducido de pady=2 a pady=1
        self.cb_color = ttk.Combobox(col2, textvariable=self.var_color_grafico, state="readonly", width=18)
        self.cb_color['values'] = list(COLORES_GRAFICO.keys()); self.cb_color.current(0)
        self.cb_color.grid(row=4, column=1, padx=2)

        # COLUMNA 3: TIEMPO Y ACCIÓN
        col3 = ttk.LabelFrame(frame_controls, text="3. Periodo y Acción")
        col3.pack(side="left", fill="both", expand=True, padx=5)

        ttk.Label(col3, text="Inicio:").grid(row=0, column=0, sticky="w", pady=2, padx=5)  # Reducido de pady=10 a pady=2
        self.ent_fecha_ini = ttk.Entry(col3, textvariable=self.var_fecha_ini, width=12)
        self.ent_fecha_ini.grid(row=0, column=1, padx=2)
        self.ent_fecha_ini.insert(0, config.get('viz_fecha_ini', '2025-01-01')) 

        ttk.Label(col3, text="Fin:").grid(row=1, column=0, sticky="w", pady=1, padx=5)  # Reducido de pady=5 a pady=1
        self.ent_fecha_fin = ttk.Entry(col3, textvariable=self.var_fecha_fin, width=12)
        self.ent_fecha_fin.grid(row=1, column=1, padx=2)
        self.ent_fecha_fin.insert(0, config.get('viz_fecha_fin', datetime.today().strftime('%Y-%m-%d')))
        
        # Bindings para actualizar versiones al cambiar fechas
        self.ent_fecha_ini.bind("<FocusOut>", self.actualizar_versiones)
        self.ent_fecha_fin.bind("<FocusOut>", self.actualizar_versiones) 

        ttk.Button(col3, text="📊 GRAFICAR", command=self.generar_grafico, style="Primary.TButton").grid(row=3, column=0, columnspan=2, pady=8, sticky="ew", padx=10)  # Reducido de pady=15 a pady=8
        ttk.Button(col3, text="📥 EXCEL", command=self.exportar_datos_excel, style="Success.TButton").grid(row=4, column=0, columnspan=2, pady=3, sticky="ew", padx=10)  # Reducido de pady=5 a pady=3

        # PANEL ESTADÍSTICAS
        self.frame_stats = ttk.Frame(self.frame_main)
        self.frame_stats.pack(fill="x", padx=10, pady=1)  # Reducido de pady=2 a pady=1
        self.lbl_stat_prom = ttk.Label(self.frame_stats, text="Promedio: --", font=('Arial', 8, 'bold'))
        self.lbl_stat_prom.pack(side="left", padx=8)  # Reducido de padx=10 a padx=8
        self.lbl_stat_max = ttk.Label(self.frame_stats, text="Max: --", font=('Arial', 8, 'bold'), foreground="green")
        self.lbl_stat_max.pack(side="left", padx=8)  # Reducido de padx=10 a padx=8
        self.lbl_stat_min = ttk.Label(self.frame_stats, text="Min: --", font=('Arial', 8, 'bold'), foreground="red")
        self.lbl_stat_min.pack(side="left", padx=8)  # Reducido de padx=10 a padx=8
        self.lbl_stat_sum = ttk.Label(self.frame_stats, text="Suma: --", font=('Arial', 8, 'bold'), foreground="blue")
        self.lbl_stat_sum.pack(side="left", padx=8)  # Reducido de padx=10 a padx=8

        self.frame_plot = ttk.Frame(self.frame_main)
        # Reservar altura fija moderada para que ni título ni gráfico se recorten
        self.frame_plot.config(height=400)
        # Permitimos que el contenido se ajuste dentro del área reservada
        self.frame_plot.pack_propagate(True)
        self.frame_plot.pack(fill="both", expand=True, padx=10, pady=5)
        
        if os.path.exists(self.ruta_db): self.cargar_tablas()

    def toggle_campo_valor(self, event=None):
        if self.var_temporalidad.get() == "Horaria (24h)":
            self.cb_campo_valor.entry.configure(state="disabled"); self.lbl_valor.configure(text="(Modo horario)")
        else:
            self.cb_campo_valor.entry.configure(state="normal"); self.lbl_valor.configure(text="Variable:")

    def seleccionar_db(self):
        f = filedialog.askopenfilename(filetypes=[("SQLite DB", "*.db")])
        if f: self.ruta_db = f; self.lbl_db.delete(0, tk.END); self.lbl_db.insert(0, f); self.cargar_tablas()

    def conectar(self): return sqlite3.connect(self.ruta_db)

    def cargar_tablas(self):
        if not os.path.exists(self.ruta_db): return
        try:
            conn = self.conectar(); cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'"); tablas = [t[0] for t in cur.fetchall()]
            conn.close(); self.cb_tabla['values'] = sorted(tablas)
            if tablas: self.cb_tabla.set("Seleccione Archivo...")
        except Exception as e: messagebox.showerror("Error", str(e))

    def al_seleccionar_tabla(self, event):
        tabla = self.var_tabla.get()
        if not tabla: return
        
        # --- RESET UI ---
        self.var_agregacion.set("Promedio")
        self.var_tipo_grafico.set("Línea")
        self.var_color_grafico.set("Verde Corporativo")
        self.var_campo_valor.set('')
        # ----------------
        
        conn = self.conectar(); cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({tabla})"); info = cur.fetchall(); cols = [c[1] for c in info]
        
        self.actualizar_versiones() # Llamada inicial para cargar versiones filtradas (o todas si no hay filtro)
        
        conn.close()
        
        cols_horarias = [str(i) for i in range(24)]
        es_horario = all(h in cols for h in cols_horarias)
        if es_horario: self.var_temporalidad.set("Horaria (24h)")
        else: self.var_temporalidad.set("Diaria")
        self.toggle_campo_valor()
        
        ignorar = ['index', 'anio', 'mes_dia', 'version_dato', 'origen_archivo', 'fecha_carga'] + cols_horarias
        candidatos = [c for c in cols if c.lower() not in ignorar]
        self.cb_campo_filtro1.update_items(candidatos); self.cb_campo_filtro2.update_items(candidatos)
        self.cb_campo_valor.update_items(candidatos)
        self.cb_campo_filtro1.entry.delete(0, tk.END); self.var_valor_filtro1.set('')
        self.cb_campo_filtro2.entry.delete(0, tk.END); self.var_valor_filtro2.set('')

    def actualizar_versiones(self, event=None):
        tabla = self.var_tabla.get()
        if not tabla: return
        
        conn = self.conectar()
        try:
            # Verificar si existe la columna version_dato
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info({tabla})"); info = cur.fetchall(); cols = [c[1] for c in info]
            if 'version_dato' not in cols:
                self.cb_version['values'] = []; self.cb_version.set("N/A")
                conn.close(); return

            # Obtener fechas en formato entero YYYYMMDD
            try:
                f_ini = self.var_fecha_ini.get().replace("-", "")
                f_fin = self.var_fecha_fin.get().replace("-", "")
                
                # Validar que sean números
                int(f_ini); int(f_fin)
                
                # FIX: Usar comparación de cadenas o concatenación segura
                # mes_dia suele ser texto "MMDD". Si es "0130", cast a int es 130. 
                # (anio * 10000 + 130) = 20250130 -> CORRECTO para int.
                # PERO si mes_dia es "130" (sin cero), falla.
                # Mejor usamos concatenación de strings que es más robusta en SQLite si los tipos varian.
                # Y aseguramos formato de fechas de entrada.
                
                f_ini_str = self.var_fecha_ini.get().replace("-", "")
                f_fin_str = self.var_fecha_fin.get().replace("-", "")
                
                # FIX: Lógica diferenciada para MENSUALES vs DIARIOS
                # Archivos mensuales (afac, tserv, etc) tienen mes_dia = "11" (Noviembre) -> Length 1 o 2.
                # Archivos diarios (trsd) tienen mes_dia = "1130" -> Length 3 o 4.
                
                es_mensual_var = False
                for especial in ARCHIVOS_MENSUALES:
                    if tabla.lower().startswith(especial.lower()):
                        es_mensual_var = True; break
                
                query = ""
                if es_mensual_var:
                    # Para mensuales, buscamos YYYYMM
                    # Rango entrada: 20251101 - 20251130 -> Extraemos YYYYMM de f_ini_str
                    f_ini_mes = f_ini_str[:6] # 202511
                    f_fin_mes = f_fin_str[:6] # 202511
                    
                    # Usamos printf para asegurar 2 digitos en mes (e.g. 9 -> 09)
                    query = f"""
                        SELECT DISTINCT version_dato 
                        FROM {tabla} 
                        WHERE (
                            CAST(anio AS TEXT) || printf('%02d', CAST(mes_dia AS INTEGER))
                        ) BETWEEN '{f_ini_mes}' AND '{f_fin_mes}'
                        ORDER BY version_dato
                    """
                else:
                    # Para diarios, buscamos YYYYMMDD
                    # Usamos printf para asegurar 4 digitos en mes_dia (e.g. 101 -> 0101)
                    query = f"""
                        SELECT DISTINCT version_dato 
                        FROM {tabla} 
                        WHERE (
                            CAST(anio AS TEXT) || printf('%04d', CAST(mes_dia AS INTEGER))
                        ) BETWEEN '{f_ini_str}' AND '{f_fin_str}'
                        ORDER BY version_dato
                    """
            except:
                # Fallback por si las fechas no son validas o estan vacias
                query = f"SELECT DISTINCT version_dato FROM {tabla} ORDER BY version_dato"

            versiones_df = pd.read_sql_query(query, conn)
            lista_versiones = versiones_df['version_dato'].astype(str).tolist()
            
            # --- FEATURE: AGREGAR "ÚLTIMA" AL INICIO ---
            if lista_versiones:
                lista_versiones.insert(0, "Última")
            # --------------------------------------------
            
            self.cb_version['values'] = lista_versiones
            
            # Mantener selección si sigue existiendo, si no, seleccionar default ("Última" si existe)
            actual = self.var_version.get()
            if actual in lista_versiones: pass 
            elif lista_versiones: self.cb_version.current(0)
            else: self.cb_version.set('')
            
        except Exception as e: print(f"Error actualizando versiones: {e}")
        finally: conn.close()

    def al_seleccionar_campo_filtro1(self, event): self._cargar_valores_filtro(self.var_campo_filtro1, self.cb_valor_filtro1)
    def al_seleccionar_campo_filtro2(self, event): self._cargar_valores_filtro(self.var_campo_filtro2, self.cb_valor_filtro2)

    def _cargar_valores_filtro(self, var_campo, widget_cb):
        tabla = self.var_tabla.get(); campo = var_campo.get()
        if not tabla or not campo: return
        try:
            conn = self.conectar()
            df = pd.read_sql_query(f"SELECT DISTINCT {campo} FROM {tabla} ORDER BY {campo}", conn)
            conn.close(); vals = df[campo].astype(str).tolist()
            
            # Verificación de tipo: ¿Es un Combobox normal o nuestro CustomDropdown?
            if hasattr(widget_cb, 'update_items'):
                widget_cb.update_items(vals) # CustomDropdown
                # Para resetear el valor, usamos la variable asociada
                if widget_cb == self.cb_valor_filtro1: self.var_valor_filtro1.set('')
                elif widget_cb == self.cb_valor_filtro2: self.var_valor_filtro2.set('')
            else:
                widget_cb['values'] = vals; widget_cb.set('') # Combobox normal
                
        except: pass

    def generar_grafico(self):
        tabla = self.var_tabla.get(); version = self.var_version.get()
        campo1 = self.var_campo_filtro1.get(); valor1 = self.var_valor_filtro1.get()
        campo2 = self.var_campo_filtro2.get(); valor2 = self.var_valor_filtro2.get()
        operacion = self.var_agregacion.get(); temporalidad = self.var_temporalidad.get()
        f_ini_str = self.var_fecha_ini.get(); f_fin_str = self.var_fecha_fin.get()
        
        tipo_grafico = self.var_tipo_grafico.get()
        nombre_color = self.var_color_grafico.get()
        color_hex = COLORES_GRAFICO.get(nombre_color, "#27ae60")

        if not tabla: return

        try:
            conn = self.conectar(); query = f"SELECT * FROM {tabla} WHERE 1=1"
            if campo1 and valor1: query += f" AND CAST({campo1} AS TEXT) = '{valor1}'"
            if campo2 and valor2: query += f" AND CAST({campo2} AS TEXT) = '{valor2}'"
            
            # Lógica Versión: Si es "Última" o "N/A", NO filtramos en SQL (traemos todo)
            # Si es una versión específica, sí filtramos.
            if version and version not in ["N/A", "Última"]: 
                query += f" AND version_dato = '{version}'"
            
            print(f"Graficador SQL: {query}")
            df = pd.read_sql_query(query, conn); conn.close()
            if df.empty: messagebox.showinfo("Vacío", f"No hay datos para graficar."); return

            # Verificar si es mensual según la lista configurada
            es_mensual_graf = False
            for especial in ARCHIVOS_MENSUALES:
                if tabla.lower().startswith(especial.lower()):
                    es_mensual_graf = True; break

            def armar_fecha(row):
                try:
                    anio = int(row['anio'])
                    md_val = row['mes_dia']
                    # Convertir a entero robustamente
                    try: md_int = int(float(md_val))
                    except: return pd.NaT
                    
                    if es_mensual_graf:
                        # Si es mensual por configuración, md_int es el MES (1-12)
                        # OJO: Si viene como 202510 (YYYYMM) por error, deberiamos validarlo?
                        # Asumimos formato estandar: anio=YYYY, mes_dia=MM
                        return pd.to_datetime(f"{anio}-{md_int:02d}-01")
                    else:
                        # Diario: md_int es MMDD
                        md_str = f"{md_int:04d}" # 101 -> 0101
                        # Validar longitud
                        if len(md_str) != 4: return pd.NaT # O intentar parsear
                        return pd.to_datetime(f"{anio}-{md_str[:2]}-{md_str[2:]}")
                except: return pd.NaT

            df['Fecha'] = df.apply(armar_fecha, axis=1); df = df.dropna(subset=['Fecha'])
            try:
                if f_ini_str: df = df[df['Fecha'] >= pd.to_datetime(f_ini_str)]
                if f_fin_str: df = df[df['Fecha'] <= pd.to_datetime(f_fin_str)]
                if df.empty: return
            except: return
            
            # --- LÓGICA DE DEDUPLICACIÓN DE VERSIONES (SI SE ELIGIÓ "ÚLTIMA") ---
            if version == "Última":
                # Usamos la misma función global 'calcular_peso_version' que ya existe en el archivo
                df['peso'] = df['version_dato'].apply(calcular_peso_version)
                # Agrupamos por Fecha (y hora si aplica) para quedarnos con el peso máximo
                # Identificamos columnas clave para agrupar (excluyendo los valores)
                # O simplemente filtramos: Para cada Fecha, max(peso).
                
                # OJO: Si hay datos horarios, puede haber multiples filas por fecha (una por hora si está vertical, o 1 fila con 24 cols).
                # Como el formato standard aqui parece ser 1 fila con 24 columnas (o 1 valor diario), la clave única es 'Fecha' + filtros.
                # Pero como ya filtramos por filtros en SQL, la clave es 'Fecha'.
                
                df['max_peso'] = df.groupby('Fecha')['peso'].transform('max')
                df = df[df['peso'] == df['max_peso']].copy()
                # Limpieza aux
                df.drop(columns=['peso', 'max_peso'], inplace=True, errors='ignore')
            # --------------------------------------------------------------------

            serie_graficar = None
            if temporalidad == "Horaria (24h)":
                cols_horas = [c for c in df.columns if c in [str(i) for i in range(24)]]
                if not cols_horas: cols_horas = [c for c in df.columns if 'hora' in c.lower()]
                for c in cols_horas: df[c] = pd.to_numeric(df[c], errors='coerce')
                
                if operacion == "Promedio": df['Res'] = df[cols_horas].mean(axis=1)
                elif operacion == "Suma": df['Res'] = df[cols_horas].sum(axis=1)
                elif operacion == "Máximo": df['Res'] = df[cols_horas].max(axis=1)
                elif operacion == "Mínimo": df['Res'] = df[cols_horas].min(axis=1)
                elif operacion == "Valor": df['Res'] = df[cols_horas].mean(axis=1) # Equivale a promedio en 24h
                serie_graficar = df.groupby('Fecha')['Res'].mean()
            else:
                col_val = self.var_campo_valor.get()
                # Fallback: si el usuario no eligió variable, intentar autoseleccionar la primera columna numérica
                if not col_val:
                    # Excluir columnas de control
                    excl = {'anio', 'mes_dia', 'version_dato', 'fecha'}
                    candidatos = [c for c in df.columns if c.lower() not in excl]
                    # Mantener solo columnas convertibles a numérico
                    for c in candidatos:
                        col_tmp = pd.to_numeric(df[c], errors='coerce')
                        if not col_tmp.dropna().empty:
                            col_val = c
                            # Reflejar selección en la UI
                            self.var_campo_valor.set(col_val)
                            break
                    if not col_val:
                        messagebox.showwarning("Selecciona variable", "Elige una variable para graficar.")
                        return
                # A partir de aquí col_val está definido
                df[col_val] = pd.to_numeric(df[col_val], errors='coerce')

                # LOGICA MENSUAL O DIARIA
                if temporalidad == "Mensual":
                    # Convertir a primer dia del mes
                    df['Fecha'] = df['Fecha'].apply(lambda x: x.replace(day=1))
                
                grupo = df.groupby('Fecha')[col_val]
                if operacion == "Promedio": serie_graficar = grupo.mean()
                elif operacion == "Suma": serie_graficar = grupo.sum()
                elif operacion == "Máximo": serie_graficar = grupo.max()
                elif operacion == "Mínimo": serie_graficar = grupo.min()
                elif operacion == "Valor": serie_graficar = grupo.mean() # Valor único

            # --- GUARDAR DATOS PARA EXPORTAR ---
            self.datos_actuales = serie_graficar.sort_index()
            
            # Guardar el nombre de la variable para el Excel
            if temporalidad == "Horaria (24h)":
                # Para Horaria, la variable suele estar definida en los filtros (ej: Recurso, Agente)
                # Construimos el nombre usando los valores de los filtros si existen
                partes = []
                if valor1: partes.append(valor1)
                if valor2: partes.append(valor2)
                
                if partes: self.var_actual_excel = " - ".join(partes)
                else: self.var_actual_excel = "Promedio 24h" # Fallback si no hay filtros
            else:
                self.var_actual_excel = self.var_campo_valor.get()
            
            # --- CALCULAR ESTADÍSTICAS ---
            val_prom = self.datos_actuales.mean()
            val_max = self.datos_actuales.max()
            val_min = self.datos_actuales.min()
            val_sum = self.datos_actuales.sum()
            
            self.lbl_stat_prom.config(text=f"Promedio: {val_prom:,.2f}")
            self.lbl_stat_max.config(text=f"Max: {val_max:,.2f}")
            self.lbl_stat_min.config(text=f"Min: {val_min:,.2f}")
            self.lbl_stat_sum.config(text=f"Suma: {val_sum:,.2f}")
            # -----------------------------

            titulo_grafico = f"{tabla.upper()}"
            if valor1: titulo_grafico += f"\n{valor1}"
            if valor2: titulo_grafico += f" - {valor2}"
            titulo_grafico += f" ({operacion})"
            
            self.titulo_actual = titulo_grafico.replace("\n", " ") # Guardar para Excel
            
            self.dibujar_plot(self.datos_actuales, titulo_grafico, tipo_grafico, color_hex, temporalidad)

        except Exception as e: messagebox.showerror("Error", f"{e}")

    def exportar_datos_excel(self):
        if self.datos_actuales is None:
            messagebox.showwarning("Sin Datos", "Primero genera un gráfico.")
            return
        
        file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")])
        if not file_path: return
        
        try:
            df_export = self.datos_actuales.reset_index()
            df_export.columns = ['Fecha', 'Valor']
            
            # Insertar columna "Variable" con el nombre guardado
            nombre_var = getattr(self, 'var_actual_excel', 'Desconocido')
            df_export.insert(1, 'Variable', nombre_var)
            
            df_export['Fecha'] = df_export['Fecha'].dt.date 
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name="Datos Gráfico")
            messagebox.showinfo("Éxito", f"Datos exportados a:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))


    def dibujar_plot(self, serie, titulo, tipo, color, temporalidad="Diaria"):
        for widget in self.frame_plot.winfo_children(): widget.destroy()
        
        # --- ESTILO LIMPIO Y MODERNO ---
        fig = Figure(figsize=(8, 4.1), dpi=100, facecolor='#ffffff')
        # Ajuste de márgenes para evitar recorte de título sin empujar el gráfico hacia arriba
        fig.subplots_adjust(top=0.88, bottom=0.14, left=0.10, right=0.95)
        
        ax = fig.add_subplot(111)
        ax.set_facecolor('#ffffff')

        # Bordes (Spines) minimalistas
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#bdc3c7')
        ax.spines['bottom'].set_color('#bdc3c7')
        
        # Grilla suave
        ax.grid(True, axis='y', linestyle=':', color='#ecf0f1', linewidth=1.5, alpha=0.8, zorder=0)
        ax.set_axisbelow(True) # Grilla detrás de datos
        
        if tipo == "Línea":
            ax.plot(serie.index, serie.values, marker='o', linestyle='-', markersize=5, color=color, linewidth=2, zorder=3)
            # Relleno suave para efecto de "peso"
            ax.fill_between(serie.index, serie.values, color=color, alpha=0.1, zorder=2)
            
        elif tipo == "Barras":
            # Calcular ancho dinámico
            ancho_barras = 0.8
            if temporalidad == "Mensual": ancho_barras = 20
            
            ax.bar(serie.index, serie.values, color=color, alpha=0.85, width=ancho_barras, edgecolor=color, zorder=3)
            
        elif tipo == "Área":
            ax.fill_between(serie.index, serie.values, color=color, alpha=0.5, zorder=3)
            ax.plot(serie.index, serie.values, color=color, linewidth=2, zorder=4)
            
        elif tipo == "Dispersión":
            ax.scatter(serie.index, serie.values, color=color, s=40, alpha=0.8, zorder=3)
        
        line_ghost, = ax.plot(serie.index, serie.values, color=color, alpha=0.0) 

        # FUENTES Y EJES
        font_title = {'fontname': 'Segoe UI', 'fontsize': 12, 'weight': 'bold', 'color': '#2c3e50'}
        font_label = {'fontname': 'Segoe UI', 'fontsize': 9, 'color': '#7f8c8d'}
        
        ax.set_title(titulo, **font_title, pad=15)
        
        if temporalidad == "Mensual":
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.MonthLocator())
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            # Si hay muchos datos, rotar
            if len(serie) > 30:
                fig.autofmt_xdate(rotation=45)
        
        ax.tick_params(axis='x', colors='#7f8c8d', labelsize=9)
        ax.tick_params(axis='y', colors='#7f8c8d', labelsize=9)
        
        # Separador de miles
        ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}')) 

        annot = ax.annotate("", xy=(0,0), xytext=(10,10),textcoords="offset points",
                            bbox=dict(boxstyle="round4,pad=0.5", fc="#ffffff", ec="#bdc3c7", alpha=0.95, lw=1),
                            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.1", color="#7f8c8d"))
        annot.set_visible(False)

        def update_annot(ind):
            x, y = line_ghost.get_data()
            idx = ind["ind"][0]
            val_x = x[idx]
            annot.xy = (val_x, y[idx])
            try: fecha_dt = mdates.num2date(val_x)
            except: fecha_dt = val_x
            try:
                fmt = "%Y-%m" if temporalidad == "Mensual" else "%Y-%m-%d"
                if hasattr(fecha_dt, 'strftime'): f_str = fecha_dt.strftime(fmt)
                else: f_str = pd.to_datetime(fecha_dt).strftime(fmt)
            except: f_str = "?"
            annot.set_text(f"{f_str}\n{y[idx]:,.2f}")

        def hover(event):
            vis = annot.get_visible()
            if event.inaxes == ax:
                cont, ind = line_ghost.contains(event)
                if cont: update_annot(ind); annot.set_visible(True); fig.canvas.draw_idle()
                else:
                    if vis: annot.set_visible(False); fig.canvas.draw_idle()

        fig.canvas.mpl_connect("motion_notify_event", hover)
        canvas = FigureCanvasTkAgg(fig, master=self.frame_plot)
        canvas.draw()
        
        # Toolbar primero (en la parte inferior del frame_plot)
        toolbar = NavigationToolbar2Tk(canvas, self.frame_plot)
        toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Canvas después, con expand para usar el espacio disponible pero respetando el monitor
        # El monitor ya está reservado en la parte inferior de la ventana principal
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# =============================================================================
#  INTERFAZ GRÁFICA PRINCIPAL (ROBOT + TABS)
# =============================================================================

class AplicacionXM:
    def __init__(self, root):
        self.root = root
        self.root.title("Suite XM Inteligente - Enerconsult")
        self.root.geometry("1100x900") 
        
        self.config = self.cargar_config()

        self.configurar_estilos_modernos() # NUEVO TEMA

        self.construir_encabezado_logo()

        # Monitor mejorado con estilo moderno - EMPAQUETAR PRIMERO EN LA PARTE INFERIOR
        # Esto asegura que tenga espacio reservado y no desaparezca
        console_container = tk.Frame(root, bg="#1e293b")
        console_container.pack(side="bottom", fill="x", expand=False, padx=10, pady=5)
        
        # Header de la consola
        header_frame = tk.Frame(console_container, bg="#1e293b", height=35)
        header_frame.pack(fill="x", side="top")
        
        title_label = tk.Label(
            header_frame,
            text=">_ Monitor de Ejecución",
            font=("Segoe UI", 10, "bold"),
            bg="#1e293b",
            fg="white",
            anchor="w"
        )
        title_label.pack(side="left", padx=15, pady=8)
        
        # Botón limpiar consola
        def limpiar_consola():
            self.txt_console.config(state="normal")
            self.txt_console.delete(1.0, tk.END)
            self.txt_console.config(state="disabled")
        
        btn_clear = tk.Button(
            header_frame,
            text="🗑️ Limpiar",
            command=limpiar_consola,
            bg="#374151",
            fg="white",
            font=("Segoe UI", 9),
            relief="flat",
            padx=10,
            pady=5,
            cursor="hand2"
        )
        btn_clear.pack(side="right", padx=10, pady=5)
        
        # Área de texto con fondo más oscuro y verde más suave
        # Altura fija para asegurar que siempre sea visible
        self.txt_console = scrolledtext.ScrolledText(
            console_container,
            height=8,
            state='disabled',
            bg='#0f172a',  # Más oscuro
            fg='#22c55e',  # Verde más suave
            font=('Consolas', 10),
            insertbackground='#22c55e',
            selectbackground='#374151',
            selectforeground='white',
            wrap='word',
            relief='flat',
            borderwidth=0
        )
        self.txt_console.pack(fill="x", expand=False, padx=0, pady=0)  # Solo fill="x", no expand
        sys.stdout = PrintRedirector(self.txt_console)

        # Ahora empaquetar el tab_control DESPUÉS del monitor
        # Esto asegura que respete el espacio del monitor
        tab_control = ttk.Notebook(root)
        self.tab_general = tk.Frame(tab_control, bg="#f8fafc")  # Fondo mejorado
        self.tab_archivos = tk.Frame(tab_control, bg="#f8fafc")
        self.tab_filtros = tk.Frame(tab_control, bg="#f8fafc")
        self.tab_visualizador = tk.Frame(tab_control, bg="#f8fafc")
        
        # Iconos originales restaurados
        tab_control.add(self.tab_general, text='🔧 Configuración')
        tab_control.add(self.tab_archivos, text='📥 Descargas')
        tab_control.add(self.tab_filtros, text='📋 Filtros Reporte')
        tab_control.add(self.tab_visualizador, text='📈 Visualizador')
        
        # Empaquetar el tab_control DESPUÉS del monitor para que respete su espacio
        tab_control.pack(expand=True, fill="both", padx=10, pady=5)

        self.crear_tab_general()
        self.crear_tab_archivos()
        self.crear_tab_filtros()
        
        # --- PASAMOS LA CONFIG AL VISUALIZADOR ---
        self.app_visualizador = ModuloVisualizador(self.tab_visualizador, self.config)
        
        # Cargar valores iniciales en dashboard (al final de todo)
        self.actualizar_dashboard()
        
        # FIX: Redirigir logging a la consola UI
        self.update_logger_output()

    def update_logger_output(self):
        """Redirige los logs al widget de texto en la GUI"""
        logger = logging.getLogger("RobotXM")
        # Remover handlers de consola antiguos para evitar duplicados
        for h in logger.handlers[:]:
            # Cuidado: FileHandler hereda de StreamHandler, usamos type() para distinguir
            if type(h) is logging.StreamHandler:
                logger.removeHandler(h)
        
        # Nuevo handler apuntando al redirector (sys.stdout ya fue parcheado)
        # O podemos pasar self.redirector directamente si lo guardamos en self
        # Como sys.stdout ya es el redirector:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        ch.setLevel(logging.INFO)
        logger.addHandler(ch)


    def toggle_controls(self, state='normal'):
        """Bloquea o desbloquea botones críticos durante procesos."""
        try:
            self.btn_guardar.config(state=state)
            self.btn_descargar.config(state=state)
            self.btn_reporte.config(state=state)
        except: pass

    def validar_config(self):
        cfg = self.get_config()
        if not cfg['usuario'] or not cfg['password']:
            messagebox.showwarning("Configuración Incompleta", "Por favor ingresa Usuario y Password FTP.")
            return False
        if not os.path.exists(cfg['ruta_local']):
            try: os.makedirs(cfg['ruta_local'])
            except: 
                messagebox.showerror("Ruta Inválida", "La ruta local no existe y no se pudo crear.")
                return False
        return True

    def add_placeholder(self, entry, text):
        """Agrega comportamiento de placeholder mejorado a un Entry"""
        entry.insert(0, text)
        try: 
            entry.configure(foreground="#94a3b8", font=("Segoe UI", 11, "italic"))  # Color placeholder mejorado
        except: pass
        
        def on_focus_in(event):
            if entry.get() == text:
                entry.delete(0, tk.END)
                try: 
                    entry.configure(foreground="#1e293b", font=("Segoe UI", 11))  # Color normal mejorado
                except: pass
        
        def on_focus_out(event):
            if not entry.get():
                entry.insert(0, text)
                try: 
                    entry.configure(foreground="#94a3b8", font=("Segoe UI", 11, "italic"))
                except: pass
        
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    def configurar_estilos_modernos(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TLabel", font=("Segoe UI Semibold", 10), background="#ffffff")

        
        # --- PALETA DE COLORES MEJORADA ENERCONSULT ---
        c_azul_primario = "#0093d0"
        c_azul_hover = "#007bb5"
        c_azul_claro = "#e0f2fe"
        c_verde_primario = "#8cc63f"
        c_verde_hover = "#7ab828"
        c_fondo_principal = "#f8fafc"  # Más claro y moderno
        c_fondo_secundario = "#ffffff"
        c_borde_claro = "#e2e8f0"
        c_texto_primario = "#1e293b"  # Más oscuro para mejor contraste
        c_texto_secundario = "#64748b"
        c_texto_placeholder = "#94a3b8"
        c_exito = "#10b981"
        c_error = "#ef4444"
        c_gris_header = "#f1f5f9"  # Para headers de tablas y pestañas

        self.root.configure(bg=c_fondo_principal)

        # --- FUENTES MEJORADAS ---
        f_h1 = ("Segoe UI", 24, "bold")
        f_h2 = ("Segoe UI", 18, "bold")
        f_h3 = ("Segoe UI", 14, "bold")
        f_main = ("Segoe UI", 11)  # Aumentado de 10 a 11
        f_head = ("Segoe UI", 11, "bold")  # Más consistente
        f_title = ("Segoe UI", 12, "bold")
        f_small = ("Segoe UI", 9)
        f_mono = ("Consolas", 10)

        # --- CONFIG GENERAL ---
        style.configure(".", background=c_fondo_principal, foreground=c_texto_primario, font=f_main)
        style.configure("TFrame", background=c_fondo_principal)
        style.configure("TLabelframe", 
            background=c_fondo_secundario, 
            borderwidth=1, 
            relief="solid",
            bordercolor=c_borde_claro
        )
        style.configure("TLabelframe.Label", 
            background=c_fondo_secundario, 
            foreground=c_azul_primario, 
            font=f_title
        )
        
        # --- PESTAÑAS (NOTEBOOK) MEJORADAS ---
        style.configure("TNotebook", 
            background=c_fondo_principal, 
            borderwidth=0, 
            tabmargins=[0, 0, 0, 0], 
            relief="flat"
        )
        style.configure("TNotebook.Tab", 
            padding=[20, 12],  # Más espacioso (antes 15, 8)
            font=("Segoe UI Semibold", 11),
            background=c_gris_header,  # Gris muy claro para hover
            foreground=c_texto_secundario,
            borderwidth=0,
            relief="flat"
        )
        style.map("TNotebook.Tab", 
            background=[
                ("selected", c_fondo_secundario),  # Blanco cuando está seleccionada
                ("active", c_gris_header)  # Gris claro al pasar mouse
            ],
            foreground=[
                ("selected", c_azul_primario),  # Azul cuando está seleccionada
                ("active", c_azul_primario)
            ],
            expand=[("selected", [0, 0, 0, 0])]
        )

        # --- BOTONES MEJORADOS CON ESTILO MODERNO ---
        # Botón Primario (Azul) - Más grande y con mejor padding
        style.configure("Primary.TButton", 
            font=("Segoe UI Semibold", 11),
            background=c_azul_primario,
            foreground="white",
            borderwidth=0,
            focuscolor="none",
            padding=[18, 14]  # Padding aumentado para look más moderno
        )
        style.map("Primary.TButton", 
            background=[
                ("active", c_azul_hover),
                ("pressed", "#006a9c"),  # Color más oscuro al presionar
                ("disabled", "#cbd5e1")
            ]
        )
        
        # Botón Success (Verde)
        style.configure("Success.TButton", 
            font=("Segoe UI", 11, "bold"),
            background=c_verde_primario,
            foreground="white",
            borderwidth=0,
            focuscolor="none",
            padding=[18, 14]  # Padding aumentado
        )
        style.map("Success.TButton", 
            background=[
                ("active", c_verde_hover),
                ("pressed", "#6a9a1f"),  # Color más oscuro al presionar
                ("disabled", "#cbd5e1")
            ]
        )

        # Botón Danger (Rojo)
        style.configure("Danger.TButton", 
            font=("Segoe UI", 11, "bold"),
            background=c_error,
            foreground="white",
            borderwidth=0,
            focuscolor="none",
            padding=[18, 14]  # Padding aumentado
        )
        style.map("Danger.TButton", 
            background=[
                ("active", "#dc2626"),
                ("pressed", "#b91c1c"),  # Color más oscuro al presionar
                ("disabled", "#cbd5e1")
            ]
        )

        # Botón Neutro (Gris/Default)
        style.configure("TButton", font=f_main, padding=[12, 8])

        # --- TREEVIEW (TABLAS) MEJORADAS ---
        style.configure("Treeview", 
            background=c_fondo_secundario,
            foreground=c_texto_primario,
            fieldbackground=c_fondo_secundario,
            rowheight=32,  # Más alto para mejor legibilidad (antes 25)
            font=f_main,
            borderwidth=1,
            relief="solid",
            bordercolor=c_borde_claro
        )
        style.configure("Treeview.Heading", 
            font=("Segoe UI", 11, "bold"),
            background=c_gris_header,  # Header con fondo gris claro
            foreground=c_texto_primario,
            padding=[12, 8],  # Más padding (antes 5)
            relief="flat"
        )
        style.map("Treeview", 
            background=[
                ("selected", c_azul_primario),
                ("!selected", c_fondo_secundario)
            ],
            foreground=[
                ("selected", "white"),
                ("!selected", c_texto_primario)
            ]
        )

        # --- ENTRADAS MEJORADAS CON ESTILO MODERNO ---
        style.configure("TEntry", 
            padding=[12, 10],  # Más padding interno
            relief="flat",  # Sin relieve para look moderno
            borderwidth=1,
            bordercolor=c_borde_claro,
            fieldbackground=c_fondo_secundario
        )
        style.map("TEntry", 
            bordercolor=[
                ("focus", c_azul_primario),  # Borde azul al enfocar
                ("!focus", c_borde_claro)
            ],
            lightcolor=[
                ("focus", c_azul_claro)  # Resplandor suave al enfocar
            ]
        )
        
        # Estilo para Entry con aspecto más moderno (simula bordes redondeados visualmente)
        style.configure("Modern.TEntry",
            padding=[14, 11],  # Padding extra para look más espacioso
            relief="flat",
            borderwidth=2,  # Borde más grueso para mejor visibilidad
            bordercolor=c_borde_claro,
            fieldbackground=c_fondo_secundario
        )
        style.map("Modern.TEntry",
            bordercolor=[
                ("focus", c_azul_primario),
                ("!focus", c_borde_claro)
            ]
        )
        
        # --- SCROLLBAR MEJORADA ---
        style.configure("Vertical.TScrollbar", 
            background="#cbd5e1",
            troughcolor=c_fondo_principal,
            borderwidth=0,
            arrowsize=14,
            width=14
        )
        style.map("Vertical.TScrollbar", 
            background=[
                ("active", "#94a3b8"),
                ("!active", "#cbd5e1")
            ]
        )

        # --- CARD STYLES MEJORADOS CON BORDES SUTILES ---
        style.configure("Card.TFrame", 
            background=c_fondo_secundario,
            relief="flat",
            borderwidth=1,  # Borde sutil
            bordercolor=c_borde_claro
        )
        style.configure("CardHeader.TFrame", 
            background="#fafbfc"  # Fondo ligeramente diferente
        )
        style.configure("CardTitle.TLabel", 
            font=("Segoe UI", 14, "bold"),
            background="#fafbfc",
            foreground=c_azul_primario
        )
        style.configure("CardIcon.TLabel", 
            font=("Segoe UI", 16),  # Aumentado de 15 a 16
            foreground=c_azul_primario,
            background="#fafbfc"
        )
        style.configure("CardBody.TFrame", 
            background=c_fondo_secundario
        )

    def construir_encabezado_logo(self):
        # Frame principal con altura reducida y fondo azul muy claro
        frame_header = tk.Frame(self.root, bg="#f0f9ff", height=70)  # Altura reducida de 120 a 70
        frame_header.pack(fill="x", side="top")
        
        # Frame interno para contenido horizontal (logo y texto lado a lado)
        frame_content = tk.Frame(frame_header, bg="#f0f9ff")
        frame_content.pack(expand=True, fill="both", pady=10)
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ruta_logo = os.path.join(script_dir, LOGO_FILENAME)
        
        if TIENE_PILLOW and os.path.exists(ruta_logo):
            try:
                pil_img = Image.open(ruta_logo)
                base_height = 50  # Reducido de 80 a 50 para ahorrar espacio
                w_percent = (base_height / float(pil_img.size[1]))
                w_size = int((float(pil_img.size[0]) * float(w_percent)))
                pil_img = pil_img.resize((w_size, base_height), RESAMPLE_LANCZOS)
                self.logo_img = ImageTk.PhotoImage(pil_img)
                lbl_logo = tk.Label(frame_content, image=self.logo_img, bg="#f0f9ff")
                lbl_logo.pack(side="left", padx=20)  # Logo a la izquierda
                
                # Título al lado del logo (horizontal)
                lbl_title = tk.Label(
                    frame_content, 
                    text="-    Suite Inteligente", 
                    bg="#f0f9ff",
                    fg="#0093d0",
                    font=("Segoe UI", 16, "bold")  # Tamaño aumentado para compensar posición horizontal
                )
                lbl_title.pack(side="left", padx=15)  # Texto al lado del logo
            except Exception as e: 
                print(f"⚠️ Error logo: {e}")
        
        # Línea separadora sutil
        separator = tk.Frame(self.root, bg="#e2e8f0", height=1)
        separator.pack(fill="x", side="top")

    # --- MÉTODOS VISUALES LEGACY ELIMINADOS (v03 utiliza ttk + estilos) ---
    def create_styled_label(self, parent, text, font=("Segoe UI Semibold", 9)):
         return ttk.Label(parent, text=text, font=font, background="#ffffff")
    
    # create_card, create_rounded_button, create_rounded_entry, round_rectangle fueron removidos
    # en favor de componentes ttk nativos.


    def crear_tab_general(self):
        # -- CONTENEDOR PRINCIPAL --
        self.tab_general.configure(bg="#f8fafc")  # Fondo mejorado 
        
        main_container = tk.Frame(self.tab_general, bg="#f8fafc")
        main_container.pack(fill="both", expand=True, padx=20, pady=10) # Minimal padding

        # =========================================================
        # SECCIÓN 1: TARJETA ÚNICA DE CONFIGURACIÓN
        # =========================================================
        
        card_main = Card(main_container)
        card_main.pack(fill="x", pady=(0, 10))
        c_content = card_main.get_body()
        
        # Grid Configuration
        c_content.columnconfigure(0, weight=1)
        c_content.columnconfigure(1, weight=1)

        # -- SUB-SECCIÓN: CREDENCIALES --
        ttk.Label(c_content, text="Credenciales FTP y Rutas", font=("Segoe UI", 12, "bold"), foreground="#0093d0", background="#ffffff").grid(row=0, column=0, columnspan=2, sticky="w", padx=0, pady=(0, 10))

        # Usuario
        ttk.Label(c_content, text="Usuario FTP", background="#ffffff").grid(row=1, column=0, sticky="w", pady=(2, 2), padx=(0, 10))
        self.ent_user = ttk.Entry(c_content)
        self.ent_user.grid(row=2, column=0, sticky="ew", padx=(0, 20), pady=(0, 5))
        self.ent_user.insert(0, self.config.get('usuario', ''))

        # Password
        ttk.Label(c_content, text="Password FTP", background="#ffffff").grid(row=1, column=1, sticky="w", pady=(2, 2), padx=(0, 10))
        self.ent_pass = ttk.Entry(c_content, show="*")
        self.ent_pass.grid(row=2, column=1, sticky="ew", pady=(0, 5))
        self.ent_pass.insert(0, self.config.get('password', ''))

        # Ruta
        ttk.Label(c_content, text="Ruta Local", background="#ffffff").grid(row=3, column=0, sticky="w", pady=(2, 2), padx=(0, 10))
        fr_ruta = tk.Frame(c_content, bg="#ffffff")
        fr_ruta.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 10)) 
        
        self.ent_ruta = ttk.Entry(fr_ruta)
        self.ent_ruta.pack(side="left", fill="x", expand=True)
        self.ent_ruta.insert(0, self.config.get('ruta_local', ''))
        
        self.btn_fold = RoundedButtonWrapper(fr_ruta, text="📂", style="Primary.TButton", width=5, command=self.seleccionar_carpeta)
        self.btn_fold.pack(side="left", padx=(5, 0))

        # -- SEPARADOR --
        ttk.Separator(c_content, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", pady=(5, 5))

        # -- SUB-SECCIÓN: FECHAS --
        ttk.Label(c_content, text="Rango de Fechas (YYYY-MM-DD)", font=("Segoe UI", 10, "bold"), foreground="#0093d0", background="#ffffff").grid(row=6, column=0, columnspan=2, sticky="w", padx=0, pady=(5, 5))

        # Fechas
        ttk.Label(c_content, text="Fecha Inicio", background="#ffffff").grid(row=7, column=0, sticky="w", pady=(2, 2), padx=(0, 10))
        self.ent_ini = ttk.Entry(c_content)
        self.ent_ini.grid(row=8, column=0, sticky="ew", padx=(0, 20))
        self.ent_ini.insert(0, self.config.get('fecha_ini', '2025-01-01'))
        
        ttk.Label(c_content, text="Fecha Fin", background="#ffffff").grid(row=7, column=1, sticky="w", pady=(2, 2), padx=(0, 10))
        self.ent_fin = ttk.Entry(c_content)
        self.ent_fin.grid(row=8, column=1, sticky="ew")
        self.ent_fin.insert(0, self.config.get('fecha_fin', '2025-01-31'))

        # =========================================================
        # SECCIÓN 2: BOTONES DE ACCIÓN
        # =========================================================
        row_actions = tk.Frame(main_container, bg="#f8fafc")
        row_actions.pack(pady=(0, 10))
        
        def create_action_btn(parent, text, icon, color, command):
            style = "Primary.TButton"
            if color == "green": style = "Success.TButton"
            elif color == "red": style = "Danger.TButton"
            
            full_text = f"{icon}  {text}" if icon else text
            return RoundedButtonWrapper(parent, text=full_text, style=style, command=command, width=30)

        self.btn_guardar = create_action_btn(row_actions, "GUARDAR CONFIG", "📁", "green", self.guardar_config)
        self.btn_guardar.grid(row=0, column=0, padx=10)

        self.btn_descargar = create_action_btn(row_actions, "EJECUTAR DESCARGA", "⏬", "blue", self.run_descarga)
        self.btn_descargar.grid(row=0, column=1, padx=10)
        
        self.btn_reporte = create_action_btn(row_actions, "GENERAR REPORTE", "📊", "blue", self.run_reporte)
        self.btn_reporte.grid(row=0, column=2, padx=10)

        # =========================================================
        # SECCIÓN 3: DASHBOARD
        # =========================================================
        self.frame_dashboard = tk.Frame(main_container, bg="#f8fafc")
        self.frame_dashboard.pack(fill="both", expand=True)
        self.actualizar_dashboard()

    def crear_tab_archivos(self):
        self.tab_archivos.configure(bg="#f8fafc")
        main_container = tk.Frame(self.tab_archivos, bg="#f8fafc")
        main_container.pack(fill="both", expand=True, padx=20, pady=10) # Reduced padding

        # --- TARJETA 1: INPUTS ---
        card_input = Card(main_container)
        card_input.pack(fill="x", pady=(0, 10))
        c1_content = card_input.get_body()

        c1_content.columnconfigure(0, weight=1)
        c1_content.columnconfigure(1, weight=2)
        c1_content.columnconfigure(2, weight=0)

        # Nombre Archivo
        ttk.Label(c1_content, text="Nombre Archivo", background="#ffffff").grid(row=0, column=0, sticky="w", pady=(0, 5), padx=5)
        self.ent_f_nom = ttk.Entry(c1_content)
        self.ent_f_nom.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 2))
        self.add_placeholder(self.ent_f_nom, "ej: trsd, PEI, tserv")

        # Ruta FTP
        ttk.Label(c1_content, text="Ruta FTP", background="#ffffff").grid(row=0, column=1, sticky="w", pady=(0, 5), padx=5)
        self.ent_f_rut = ttk.Entry(c1_content)
        self.ent_f_rut.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 2))
        self.add_placeholder(self.ent_f_rut, "ej: /Reportes/Predespacho")

        # Botón Agregar
        self.btn_add_file = RoundedButtonWrapper(c1_content, text="+", command=self.add_file, style="Success.TButton", width=5)
        self.btn_add_file.grid(row=1, column=2, padx=5)

        # --- TARJETA 2: LISTADO ---
        card_list = Card(main_container)
        card_list.pack(fill="both", expand=True, pady=(0, 10))
        c2_content = card_list.get_body()
        
        columns = ("nombre", "ruta", "acciones")
        self.tree_files = ttk.Treeview(c2_content, columns=columns, show="headings", height=8)
        self.tree_files.heading("nombre", text="Nombre Archivo", anchor="w")
        self.tree_files.heading("ruta", text="Ruta FTP", anchor="w")
        self.tree_files.heading("acciones", text="Acciones", anchor="center") 
        
        self.tree_files.column("nombre", width=150)
        self.tree_files.column("ruta", width=400, stretch=True) 
        self.tree_files.column("acciones", width=80, anchor="center")
        
        self.tree_files.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(c2_content, orient="vertical", command=self.tree_files.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree_files.configure(yscrollcommand=scrollbar.set)
        
        # Configurar tags para filas alternadas
        self.tree_files.tag_configure("even", background="#ffffff")
        self.tree_files.tag_configure("odd", background="#f8fafc")
        
        # Insertar datos con colores alternados
        for idx, i in enumerate(self.config.get('archivos_descarga', [])):
            tags = ("even",) if idx % 2 == 0 else ("odd",)
            self.tree_files.insert("", "end", values=(i['nombre_base'], i['ruta_remota'], "🗑️"), tags=tags)

        def on_tree_click(event):
            region = self.tree_files.identify("region", event.x, event.y)
            if region == "cell":
                col = self.tree_files.identify_column(event.x)
                if col == "#3": 
                    self.del_file()

        self.tree_files.bind("<Button-1>", on_tree_click)

        # --- INFO BOX ---
        fr_info = tk.Frame(main_container, bg="#e0f2fe", bd=1, relief="solid")
        fr_info.pack(fill="x")
        fr_info.configure(highlightbackground="#bae6fd", highlightthickness=1)
        
        tk.Label(fr_info, text="⏬", bg="#e0f2fe", font=("Arial", 12)).pack(side="left", padx=10, pady=10)
        
        n_files = len(self.tree_files.get_children())
        lbl_info_text = tk.Label(fr_info, text=f"Archivos Configurados: {n_files}\nEstos archivos serán descargados del servidor FTP de XM en el rango de fechas especificado.", 
                                 justify="left", bg="#e0f2fe", fg="#0369a1", font=("Segoe UI", 9))
        lbl_info_text.pack(side="left", pady=10)
        self.lbl_info_files_summary = lbl_info_text

    def crear_tab_filtros(self):
        self.tab_filtros.configure(bg="#f8fafc")
        main_container = tk.Frame(self.tab_filtros, bg="#f8fafc")
        main_container.pack(fill="both", expand=True, padx=20, pady=10) # Reduced padding

        # --- TARJETA 1: INPUTS (GRID 4 COLUMNAS) ---
        fr_card_input = tk.Frame(main_container, bg="#f8fafc")
        fr_card_input.pack(fill="x", pady=(0, 10))
        
        card_input = Card(fr_card_input)
        card_input.pack(fill="both", expand=True)
        c1_content = card_input.get_body()

        # Configurar Grid
        c1_content.columnconfigure(0, weight=1)
        c1_content.columnconfigure(1, weight=1)
        c1_content.columnconfigure(2, weight=1) 
        c1_content.columnconfigure(3, weight=0, minsize=80) # Fixed size
        c1_content.columnconfigure(4, weight=0) # Botones

        # Col 0: Tabla
        ttk.Label(c1_content, text="Tabla", background="#ffffff").grid(row=0, column=0, sticky="w", pady=(0, 5), padx=5)
        self.ent_r_tab = ttk.Entry(c1_content)
        self.ent_r_tab.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 2))
        self.add_placeholder(self.ent_r_tab, "ej: trsd, afac")

        # Col 1: Campo
        ttk.Label(c1_content, text="Campo", background="#ffffff").grid(row=0, column=1, sticky="w", pady=(0, 5), padx=5)
        self.ent_r_cam = ttk.Entry(c1_content)
        self.ent_r_cam.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 2))
        self.add_placeholder(self.ent_r_cam, "ej: Recurso, Agente")

        # Col 2: Valor
        ttk.Label(c1_content, text="Valor", background="#ffffff").grid(row=0, column=2, sticky="w", pady=(0, 5), padx=5)
        self.ent_r_val = ttk.Entry(c1_content)
        self.ent_r_val.grid(row=1, column=2, sticky="ew", padx=5, pady=(0, 2))
        self.add_placeholder(self.ent_r_val, "ej: IXEG")

        # Col 3: Versión (Combobox)
        ttk.Label(c1_content, text="Versión", background="#ffffff").grid(row=0, column=3, sticky="w", pady=(0, 5), padx=5)
        self.cb_r_ver = ttk.Combobox(c1_content, values=["Última", "tx1", "tx2", "tx3", "txR"], state="readonly", width=10) # Fixed width
        self.cb_r_ver.set("Última")
        self.cb_r_ver.grid(row=1, column=3, sticky="ew", padx=5, ipady=3)
        self.cb_r_ver.bind("<<ComboboxSelected>>", self.actualizar_todas_versiones_filtro)

        # Botones (+, Up, Down)
        fr_btns = tk.Frame(c1_content, bg="#ffffff")
        fr_btns.grid(row=1, column=4, padx=5)
        
        def small_btn(txt, cmd, color="#0093d0"):
            style = "Primary.TButton"
            if color == "#8cc63f": style = "Success.TButton"
            b = RoundedButtonWrapper(fr_btns, text=txt, style=style, width=5, command=cmd) # Width approx for small btn
            b.pack(side="left", padx=2)
            return b

        small_btn("✚", self.add_filtro, "#8cc63f")
        small_btn("▲", self.move_up)
        small_btn("▼", self.move_down)

        # --- TARJETA 2: LISTADO ---
        fr_card_list = tk.Frame(main_container, bg="#f8fafc")
        fr_card_list.pack(fill="both", expand=True, pady=(0, 10))
        
        card_list = Card(fr_card_list, fill_height=True)
        card_list.pack(fill="both", expand=True)
        c2_content = card_list.get_body()
        
        columns = ("tabla", "campo", "valor", "version", "acciones")
        self.tree_filtros = ttk.Treeview(c2_content, columns=columns, show="headings", height=8)
        
        self.tree_filtros.heading("tabla", text="Tabla", anchor="w")
        self.tree_filtros.heading("campo", text="Campo", anchor="w")
        self.tree_filtros.heading("valor", text="Valor", anchor="w")
        self.tree_filtros.heading("version", text="Versión", anchor="center")
        self.tree_filtros.heading("acciones", text="Acciones", anchor="center")
        
        self.tree_filtros.column("tabla", width=120)
        self.tree_filtros.column("campo", width=150)
        self.tree_filtros.column("valor", width=200, stretch=True)
        self.tree_filtros.column("version", width=100, anchor="center")
        self.tree_filtros.column("acciones", width=80, anchor="center")
        
        self.tree_filtros.pack(fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(c2_content, orient="vertical", command=self.tree_filtros.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree_filtros.configure(yscrollcommand=scrollbar.set)
        
        # Configurar tags para filas alternadas
        self.tree_filtros.tag_configure("even", background="#ffffff")
        self.tree_filtros.tag_configure("odd", background="#f8fafc")
        
        # Insertar datos con colores alternados
        for idx, i in enumerate(self.config.get('filtros_reporte', [])):
            tags = ("even",) if idx % 2 == 0 else ("odd",)
            self.tree_filtros.insert("", "end", values=(i['tabla'], i.get('campo',''), i.get('valor',''), i.get('version',''), "🗑️"), tags=tags)

        # Binding Doble Click
        self.tree_filtros.bind("<Button-1>", lambda e: self.del_filtro() if self.tree_filtros.identify_column(e.x) == "#5" else None)

        # --- INFO BOX (Blue) ---
        fr_info = tk.Frame(main_container, bg="#e0f2fe", bd=1, relief="solid") 
        fr_info.pack(fill="x")
        fr_info.configure(highlightbackground="#bae6fd", highlightthickness=1)
        
        tk.Label(fr_info, text="🝖", font=("Segoe UI Symbol", 14), bg="#e0f2fe", fg="#0369a1").pack(side="left", padx=10, pady=10) # Icono filtros

        n_filtros = len(self.tree_filtros.get_children())
        lbl_text = tk.Label(fr_info, text=f"Filtros Configurados: {n_filtros}\nLos filtros se aplicarán en el orden mostrado al generar el reporte Excel horizontal.", 
                                 justify="left", bg="#e0f2fe", fg="#0369a1", font=("Segoe UI", 9))
        lbl_text.pack(side="left", pady=10)
        self.lbl_info_filtros_summary = lbl_text

    def move_up(self):
        selection = self.tree_filtros.selection()
        if not selection: return
        for item_id in selection:
            idx = self.tree_filtros.index(item_id)
            if idx > 0: self.tree_filtros.move(item_id, "", idx - 1); self.tree_filtros.see(item_id)

    def move_down(self):
        selection = self.tree_filtros.selection()
        if not selection: return
        for item_id in reversed(selection):
            idx = self.tree_filtros.index(item_id)
            last_idx = len(self.tree_filtros.get_children()) - 1
            if idx < last_idx: self.tree_filtros.move(item_id, "", idx + 1); self.tree_filtros.see(item_id)

    def seleccionar_carpeta(self):
        d = filedialog.askdirectory()
        if d: self.ent_ruta.delete(0, tk.END); self.ent_ruta.insert(0, d)
    
    def add_file(self):
        nom, rut = self.ent_f_nom.get(), self.ent_f_rut.get()
        ph_nom = "ej: trsd, PEI, tserv"
        ph_rut = "ej: /Reportes/Predespacho"
        
        if nom and rut and nom != ph_nom and rut != ph_rut:
            # Determinar tag para fila alternada
            num_items = len(self.tree_files.get_children())
            tags = ("even",) if num_items % 2 == 0 else ("odd",)
            self.tree_files.insert("", "end", values=(nom, rut, "🗑️"), tags=tags)
            
            # Reset a placeholder
            self.ent_f_nom.delete(0, tk.END); self.ent_f_nom.insert(0, ph_nom); self.ent_f_nom.configure(fg="#95a5a6")
            self.ent_f_rut.delete(0, tk.END); self.ent_f_rut.insert(0, ph_rut); self.ent_f_rut.configure(fg="#95a5a6")
            
            self.update_file_count_ui()
            # Foco al nombre para seguir añadiendo rápido
            self.ent_f_nom.focus_set()
            # Hack: Al hacer focus, el evento FocusIn borrará el placeholder recién puesto?
            # SÍ. Si hacemos focus, trigger FocusIn -> borra.
            # Mejor NO hacer focus set, o si lo hacemos, dejarlo vacio.
            # El usuario pide comportamiento "placeholder", asi que dejarlo en estado placeholder es lo correcto.

    def del_file(self):
        for s in self.tree_files.selection(): self.tree_files.delete(s)
        self.update_file_count_ui()
        
    def update_file_count_ui(self):
        if hasattr(self, 'lbl_info_files_summary'):
            n = len(self.tree_files.get_children())
            self.lbl_info_files_summary.config(text=f"Archivos Configurados: {n}\nEstos archivos serán descargados del servidor FTP de XM en el rango de fechas especificado.")

    def add_filtro(self):
        t, c, v = self.ent_r_tab.get(), self.ent_r_cam.get(), self.ent_r_val.get()
        ph_t, ph_c, ph_v = "ej: trsd, afac", "ej: Recurso, Agente", "ej: IXEG"
        
        # Validar SOLO Tabla como obligatorio (como era antes)
        if t and t != ph_t:
            # Si los otros son placeholders, enviar vacío
            val_c = c if c != ph_c else ""
            val_v = v if v != ph_v else ""
            
            # Determinar tag para fila alternada
            num_items = len(self.tree_filtros.get_children())
            tags = ("even",) if num_items % 2 == 0 else ("odd",)
            self.tree_filtros.insert("", "end", values=(t, val_c, val_v, self.cb_r_ver.get(), "🗑️"), tags=tags)
            
            # Reset
            self.ent_r_tab.delete(0, tk.END); self.ent_r_tab.insert(0, ph_t); self.ent_r_tab.configure(fg="#95a5a6")
            self.ent_r_cam.delete(0, tk.END); self.ent_r_cam.insert(0, ph_c); self.ent_r_cam.configure(fg="#95a5a6")
            self.ent_r_val.delete(0, tk.END); self.ent_r_val.insert(0, ph_v); self.ent_r_val.configure(fg="#95a5a6")
            
            self.update_filtro_count_ui()

    def actualizar_todas_versiones_filtro(self, event=None):
        nueva_version = self.cb_r_ver.get()
        if not nueva_version: return
        # Recorrer todos los items del treeview y actualizar columna versión (índice 3)
        for item_id in self.tree_filtros.get_children():
            vals = list(self.tree_filtros.item(item_id, 'values'))
            if len(vals) >= 4:
                vals[3] = nueva_version
                self.tree_filtros.item(item_id, values=vals)

    def del_filtro(self):
        for s in self.tree_filtros.selection(): self.tree_filtros.delete(s)
        self.update_filtro_count_ui()

    def update_filtro_count_ui(self):
        if hasattr(self, 'lbl_info_filtros_summary'):
            n = len(self.tree_filtros.get_children())
            self.lbl_info_filtros_summary.config(text=f"Filtros Configurados: {n}\nLos filtros se aplicarán en el orden mostrado al generar el reporte Excel horizontal.")
        # self.actualizar_dashboard()

    def get_config(self):
        return {
            'usuario': self.ent_user.get(), 'password': self.ent_pass.get(),
            'ruta_local': self.ent_ruta.get(),
            'fecha_ini': self.ent_ini.get(), 'fecha_fin': self.ent_fin.get(),
            'viz_fecha_ini': self.app_visualizador.ent_fecha_ini.get(),
            'viz_fecha_fin': self.app_visualizador.ent_fecha_fin.get(),
            'ruta_db_viz': self.app_visualizador.lbl_db.get(), # Persistir ruta BD Visualizador
            'archivos_descarga': [{'nombre_base': str(self.tree_files.item(i)['values'][0]), 'ruta_remota': str(self.tree_files.item(i)['values'][1])} for i in self.tree_files.get_children()],
            'filtros_reporte': [{
                'tabla': str(self.tree_filtros.item(i)['values'][0]), 
                'campo': str(self.tree_filtros.item(i)['values'][1]), 
                'valor': str(self.tree_filtros.item(i)['values'][2]),
                'version': str(self.tree_filtros.item(i)['values'][3])
            } for i in self.tree_filtros.get_children()]
        }

    def guardar_config(self):
        try:
            with open(ARCHIVO_CONFIG, 'w') as f: json.dump(self.get_config(), f, indent=4)
            print("✅ Configuración guardada (Incluyendo fechas del gráfico).")
            self.actualizar_dashboard()
        except Exception as e: print(f"❌ Error guardando: {e}")

    def crear_metric_card(self, parent, icon, value, label, color="#0093d0"):
        """Crea una tarjeta de métrica destacada"""
        card = tk.Frame(parent, bg="#ffffff", relief="flat", bd=0)
        
        # Frame interno con padding
        inner = tk.Frame(card, bg="#ffffff")
        inner.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Icono grande
        icon_label = tk.Label(
            inner, 
            text=icon, 
            font=("Segoe UI", 32),
            bg="#ffffff",
            fg=color
        )
        icon_label.pack(side="left", padx=(0, 15))
        
        # Frame para texto
        text_frame = tk.Frame(inner, bg="#ffffff")
        text_frame.pack(side="left", fill="both", expand=True)
        
        # Valor destacado
        value_label = tk.Label(
            text_frame,
            text=str(value),
            font=("Segoe UI", 24, "bold"),
            bg="#ffffff",
            fg="#1e293b"
        )
        value_label.pack(anchor="w")
        
        # Etiqueta
        label_label = tk.Label(
            text_frame,
            text=label,
            font=("Segoe UI", 10),
            bg="#ffffff",
            fg="#64748b"
        )
        label_label.pack(anchor="w")
        
        return card

    def actualizar_dashboard(self):
        # 0. Limpiar previo
        for w in self.frame_dashboard.winfo_children(): w.destroy()
        
        # 1. Recopilar Stats
        ruta = self.ent_ruta.get()
        db_path = os.path.join(ruta, NOMBRE_DB_FILE)
        
        n_files = 0
        if hasattr(self, 'tree_files'): n_files = len(self.tree_files.get_children())
        n_filters = 0
        if hasattr(self, 'tree_filtros'): n_filters = len(self.tree_filtros.get_children())
        
        db_exists = os.path.exists(db_path)
        db_size = f"{os.path.getsize(db_path)/(1024*1024):.2f} MB" if db_exists else "0 MB"
        db_time = datetime.fromtimestamp(os.path.getmtime(db_path)).strftime('%Y-%m-%d %H:%M') if db_exists else "--"
        
        # 2. Construir Layout Grid con métricas destacadas
        
        # Contenedor con grid de 3 columnas
        grid_container = tk.Frame(self.frame_dashboard, bg="#f8fafc")
        grid_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Configurar grid de 3 columnas
        for i in range(3):
            grid_container.columnconfigure(i, weight=1, uniform="metric")
        
        # Crear tarjetas de métricas destacadas
        card1 = self.crear_metric_card(grid_container, "💾", db_size, "Base de Datos", "#0093d0" if db_exists else "#ef4444")
        card1.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        card2 = self.crear_metric_card(grid_container, "📥", n_files, "Archivos Configurados", "#8cc63f")
        card2.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        card3 = self.crear_metric_card(grid_container, "📋", n_filters, "Filtros Reporte", "#f59e0b")
        card3.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")
        
        # Panel de información adicional (debajo de las métricas)
        info_frame = tk.Frame(grid_container, bg="#f8fafc")
        info_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
        
        # Información de última modificación
        if db_exists:
            info_text = f"Última modificación: {db_time}"
            info_label = tk.Label(
                info_frame,
                text=info_text,
                font=("Segoe UI", 10),
                bg="#f8fafc",
                fg="#64748b"
            )
            info_label.pack(side="left", padx=10)
        
        # Flujo de trabajo
        flow_text = "FTP XM  ➔  📥 Descarga  ➔  💾 BD  ➔  📈 Visualizador"
        flow_label = tk.Label(
            info_frame,
            text=flow_text,
            font=("Segoe UI", 11, "bold"),
            bg="#f8fafc",
            fg="#0093d0"
        )
        flow_label.pack(side="right", padx=10)

    def cargar_config(self):
        if os.path.exists(ARCHIVO_CONFIG):
            try:
                with open(ARCHIVO_CONFIG, 'r') as f: return json.load(f)
            except: pass
        return {}

    def run_descarga(self):
        if not self.validar_config(): return
        self.toggle_controls('disabled')
        threading.Thread(target=self._exec_descarga, args=(self.get_config(),)).start()
    
    def _exec_descarga(self, cfg):
        try:
            proceso_descarga(cfg)
            necesita_fix = proceso_base_datos(cfg)
            if necesita_fix:
                log.warning("⚠️ DETECTADOS ARCHIVOS CORRUPTOS. AUTORREPARANDO...")
                time.sleep(1)
                proceso_descarga(cfg, es_reintento=True)
                proceso_base_datos(cfg, es_reintento=True)
            log.info("🏁 PROCESO FINALIZADO.")
        except Exception as e:
            log.error(f"❌ Error crítico en proceso: {e}")
        finally:
            self.root.after(0, lambda: [self.toggle_controls('normal'), self.actualizar_dashboard()])

    def run_reporte(self):
        if not self.validar_config(): return
        self.toggle_controls('disabled')
        threading.Thread(target=self._exec_reporte, args=(self.get_config(),)).start()

    def _exec_reporte(self, cfg):
        try:
            generar_reporte_logica(cfg)
        except Exception as e:
            log.error(f"❌ Error crítico generando reporte: {e}")
        finally:
            self.root.after(0, lambda: [self.toggle_controls('normal'), self.actualizar_dashboard()])

if __name__ == "__main__":
    root = tk.Tk()
    app = AplicacionXM(root)
    root.mainloop()
