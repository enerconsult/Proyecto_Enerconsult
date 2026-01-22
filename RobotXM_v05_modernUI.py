# =============================================================================
#  ROBOT XM - SUITE INTEGRADA (v15 - FINAL OPTIMIZED + MODERN UI)
#  Funcionalidades:
#  1. Descarga FTP Automática (Buffer Optimizado).
#  2. Base de Datos SQLite (Blindada + Vectorizada).
#  3. Reportes Excel (SQL-side filtering).
#  4. VISUALIZADOR AVANZADO (Vectorizado).
#  5. INTERFAZ MODERNA (ttkbootstrap).
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

# --- NUEVA LIBRERÍA DE UI ---
import ttkbootstrap as tb
from ttkbootstrap.constants import *

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

# COLORES (Ajustados para el tema Flatly)
COLORES_GRAFICO = {
    "Verde Corporativo": "#18bc9c", # Flatly Green
    "Azul Corporativo": "#2c3e50",  # Flatly Dark Blue
    "Rojo Intenso": "#e74c3c",
    "Naranja": "#f39c12",
    "Morado": "#9b59b6",
    "Gris Oscuro": "#34495e",
    "Negro": "#000000"
}

import logging
import logging.handlers

# --- CONFIGURACIÓN DE LOGGING ---
def setup_logging():
    logger = logging.getLogger("RobotXM")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    # Evitar duplicar handlers si se recarga
    if not logger.handlers:
        fh = logging.handlers.RotatingFileHandler("robot_xm.log", maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
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
        msg = str(str_val)
        def _append():
            try:
                self.text_widget.configure(state='normal')
                self.text_widget.insert(tk.END, msg)
                self.text_widget.see(tk.END)
                self.text_widget.configure(state='disabled')
            except tk.TclError: pass
            except Exception: pass
        try: self.text_widget.after(0, _append)
        except: pass

    def flush(self): pass

# =============================================================================
#  GUI CLASSES ADAPTADAS (Bootstrap)
# =============================================================================
class CustomDropdownWithTooltip:
    def __init__(self, master, textvariable=None, width=18, command=None, tooltip_threshold=15, dropdown_height=160):
        self.master = master
        self.items = []
        self.filtered_items = []
        self.textvariable = textvariable
        self.command = command
        self.tooltip_threshold = tooltip_threshold
        self.dropdown_height = dropdown_height

        # Usamos tb.Entry para estilo moderno
        self.entry = tb.Entry(master, width=width, textvariable=self.textvariable, bootstyle="secondary")
        self.entry.bind("<Button-1>", self.show_dropdown)
        self.entry.bind("<KeyRelease>", self.filter_items)
        self.entry.bind("<Down>", self.focus_listbox)
        self.entry.bind("<Escape>", lambda e: self.close_dropdown())

        self.dropdown = None
        self.tooltip = None
        self.listbox = None
        self.current_index = None

    def focus_listbox(self, event=None):
        if not self.dropdown: self.show_dropdown()
        if self.listbox:
            self.listbox.focus_set()
            if self.listbox.size() > 0:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(0)
                self.listbox.activate(0)

    def update_items(self, new_items):
        self.items = [str(x) for x in new_items]
        self.filtered_items = self.items[:]

    def show_dropdown(self, event=None):
        if str(self.entry['state']) == 'disabled': return
        if self.dropdown: self.close_dropdown(); return

        self.dropdown = tk.Toplevel(self.master)
        try:
            self.dropdown.wm_overrideredirect(True)
            self.dropdown.attributes("-topmost", True)
        except Exception: pass

        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        w_pixels = max(self.entry.winfo_width(), 150)
        self.dropdown.geometry(f"{w_pixels}x{self.dropdown_height}+{x}+{y}")

        frame_list = ttk.Frame(self.dropdown) # Standard frame for dropdown internal
        frame_list.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(frame_list, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        chars_w = width_chars(w_pixels)
        self.listbox = tk.Listbox(frame_list, width=chars_w, height=8, yscrollcommand=scrollbar.set,
                                  exportselection=False, bg="#ffffff", fg="#2c3e50",
                                  selectbackground="#18bc9c", selectforeground="#ffffff", # Flatly Green
                                  font=("Segoe UI", 10), borderwidth=0)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)

        self.listbox.delete(0, tk.END)
        for item in self.filtered_items: self.listbox.insert(tk.END, item)

        self.listbox.bind("<Motion>", self.on_motion)
        self.listbox.bind("<Leave>", self.hide_tooltip)
        self.listbox.bind("<ButtonRelease-1>", self.select_item)
        self.listbox.bind("<Escape>", lambda e: self.close_dropdown())
        self.dropdown.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_out(self, event):
        self.master.after(10, self._check_focus)

    def _check_focus(self):
        if not self.dropdown: return
        try:
            focused = self.master.focus_get()
            if focused and str(focused).startswith(str(self.dropdown)): return
            if focused == self.entry: return
            self.close_dropdown()
        except: self.close_dropdown()

    def on_motion(self, event):
        if not self.listbox: return
        index = self.listbox.nearest(event.y)
        if index >= 0 and index < self.listbox.size():
            if index != self.current_index:
                self.current_index = index
                self.show_tooltip(index, event)

    def show_tooltip(self, index, event):
        self.hide_tooltip()
        try: text = self.listbox.get(index)
        except Exception: return
        if len(text) < self.tooltip_threshold: return

        x = event.x_root + 20; y = event.y_root + 10
        self.tooltip = tk.Toplevel(self.master)
        try:
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.attributes("-topmost", True)
        except: pass
        self.tooltip.geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip, text=text, background="#ffffe0", relief="solid", borderwidth=1, font=("Arial", "9", "normal"), padx=5, pady=2)
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip:
            try: self.tooltip.destroy()
            except: pass
            self.tooltip = None

    def select_item(self, event=None):
        if not self.listbox: return
        selection = self.listbox.curselection()
        if selection:
            index = selection[0]
            val = self.listbox.get(index)
            if self.textvariable: self.textvariable.set(val)
            else:
                self.entry.delete(0, tk.END)
                self.entry.insert(0, val)
        self.close_dropdown()
        if self.command:
            try: self.command(None)
            except: pass

    def close_dropdown(self):
        self.hide_tooltip()
        if self.dropdown:
            try: self.dropdown.destroy()
            except: pass
            self.dropdown = None; self.listbox = None; self.current_index = None

    def filter_items(self, event):
        if event.keysym in ['Down', 'Up', 'Return', 'Escape']: return
        query = self.entry.get().lower()
        self.filtered_items = [item for item in self.items if query in item.lower()]
        if self.dropdown and self.listbox:
            self.listbox.delete(0, tk.END)
            for item in self.filtered_items: self.listbox.insert(tk.END, item)
        else:
            if query: self.show_dropdown()

def width_chars(pixels): return int(pixels / 7)

class Card(tk.Frame):
    """
    Card adaptada para integrarse con ttkbootstrap.
    Mantiene la estructura pero usa colores compatibles.
    """
    def __init__(self, parent, title=None, icon=None, *args, **kwargs):
        # Fondo blanco para el Card funciona bien en tema Flatly (Light)
        super().__init__(parent, bg="#ffffff", bd=1, relief="solid")
        
        # Header
        if title or icon:
            header = tk.Frame(self, bg="#f8f9fa") # Light gray header
            header.pack(fill="x", pady=(0, 0))
            if icon:
                lbl_icon = tk.Label(header, text=icon, font=("Segoe UI", 12), fg="#2c3e50", bg="#f8f9fa")
                lbl_icon.pack(side="left", padx=(10, 5), pady=8, anchor="center")
            if title:
                lbl_title = tk.Label(header, text=title, font=("Segoe UI", 11, "bold"), fg="#2c3e50", bg="#f8f9fa")
                lbl_title.pack(side="left", padx=5, pady=8, anchor="w")
            
            # Separator line
            tk.Frame(self, bg="#ecf0f1", height=1).pack(fill="x")

        self.body = tk.Frame(self, bg="#ffffff", padx=15, pady=15)
        self.body.pack(fill="both", expand=True)

    def get_body(self): return self.body
    
    def pack(self, **kwargs):
        # Shadow effect simulated with padding/borders handled by parent usually, 
        # but here we keep it simple for bootstrap integration.
        super().pack(**kwargs)

class RoundedButtonWrapper(tb.Button):
    """
    Wrapper inteligente que fuerza esquinas redondeadas (Rounded)
    y traduce estilos antiguos.
    """
    def __init__(self, parent, text, command=None, style="Primary.TButton", width=None, *args, **kwargs):
        # Traducción de estilos y FORZADO DE CURVAS
        b_style = "primary" # Default
        style_lower = style.lower()
        
        if "success" in style_lower: b_style = "success"
        elif "danger" in style_lower: b_style = "danger"
        elif "warning" in style_lower: b_style = "warning"
        elif "info" in style_lower: b_style = "info"
        elif "secondary" in style_lower: b_style = "secondary"
        elif "light" in style_lower: b_style = "light"
        
        # AQUÍ ESTÁ EL TRUCO: Agregamos '-rounded' al estilo
        final_style = b_style # "-rounded" suffix removed as it causes AttributeError in this version
        
        super().__init__(parent, text=text, command=command, bootstyle=final_style, width=width, *args, **kwargs)

# =============================================================================
#  MÓDULO DE OPTIMIZACIÓN Y HELPER FUNCTIONS
# =============================================================================

def safe_identifier(name: str) -> str:
    if not re.match(r'^[A-Za-z0-9_]+$', str(name)):
        raise ValueError(f"Identificador inválido (posible inyección SQL): {name}")
    return name

def generar_fechas_permitidas(fecha_ini, fecha_fin):
    dias = []
    meses = set()
    delta = fecha_fin - fecha_ini
    for i in range(delta.days + 1):
        dia = fecha_ini + timedelta(days=i)
        dias.append(dia.strftime("%d"))
        dias.append(dia.strftime("%m%d"))
        meses.add(dia.strftime("%Y-%m"))
    return dias, meses

def make_ftps_connection(usuario, password):
    context = ssl.create_default_context()
    context.set_ciphers('DEFAULT:@SECLEVEL=1')
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    
    ftps = ftplib.FTP_TLS(context=context, timeout=FTP_CONNECT_TIMEOUT)
    try:
        ftps.connect('xmftps.xm.com.co', 210, timeout=FTP_CONNECT_TIMEOUT)
        ftps.auth()
        ftps.prot_p()
        ftps.login(usuario, password)
    except Exception as e:
        raise Exception(f"Fallo conexión FTP: {e}")
    return ftps

def retrbinary_safe(ftps, cmd, callback, blocksize=32768): 
    attempts = 0
    while attempts < FTP_RETRIES:
        try:
            ftps.retrbinary(cmd, callback, blocksize)
            return
        except Exception as e:
            attempts += 1
            if attempts >= FTP_RETRIES: raise e
            time.sleep(RETRY_BACKOFF * attempts)

def descargar_archivos_paralelo(config, lista_tareas, workers=4, stop_event=None):
    usuario = config['usuario']
    password = config['password']
    
    def worker(tarea):
        if stop_event and stop_event.is_set(): return (tarea[1], "Detenido por usuario")
        ruta_remota, ruta_local = tarea
        conn = None
        temp_path = ruta_local + ".part"
        filename = os.path.basename(ruta_local)
        
        try:
            conn = make_ftps_connection(usuario, password)
            with open(temp_path, 'wb') as f:
                retrbinary_safe(conn, f"RETR {ruta_remota}", f.write)
            
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                os.replace(temp_path, ruta_local) 
                log.info(f"   ✅ Descargado: {filename}")
                return (ruta_local, None)
            else:
                return (ruta_local, "Descarga vacía (0 bytes)")
                
        except Exception as e:
            log.error(f"   ❌ Error {filename}: {e}")
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
        futures = []
        for t in lista_tareas:
            if stop_event and stop_event.is_set(): break
            futures.append(executor.submit(worker, t))
            
        for future in as_completed(futures):
            resultados.append(future.result())
    return resultados

def sqlite_fast_connect(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
    except: pass
    return conn

def bulk_insert_fast(conn, ruta_csv, tabla, meta_cols, chunksize=100000):
    tabla = safe_identifier(tabla)
    total_rows = 0
    
    try:
        df_iter = pd.read_csv(ruta_csv, sep=';', encoding='latin-1', 
                              chunksize=chunksize, dtype=str, engine='c', 
                              skipinitialspace=True)
    except Exception as e:
        log.error(f"Error leyendo CSV {ruta_csv}: {e}")
        raise e

    first_chunk = True
    
    for df_chunk in df_iter:
        df_chunk.columns = [
            re.sub(r'[^a-z0-9]+', '_', c.strip().lower()).strip('_') 
            for c in df_chunk.columns
        ]
        
        for k, v in meta_cols.items():
            df_chunk[k] = v
            
        if first_chunk:
            try:
                cursor = conn.cursor()
                cursor.execute(f'PRAGMA table_info("{tabla}")')
                existing_cols_info = cursor.fetchall()
                existing_cols = {info[1] for info in existing_cols_info}
                
                if existing_cols:
                    for col in df_chunk.columns:
                        if col not in existing_cols:
                            try:
                                conn.execute(f'ALTER TABLE "{tabla}" ADD COLUMN "{col}" TEXT')
                            except: pass
            except: pass
            first_chunk = False

        try:
            df_chunk.to_sql(tabla, conn, if_exists='append', index=False, chunksize=chunksize)
            total_rows += len(df_chunk)
        except Exception as e:
            log.error(f"Fallo insertando chunk en {tabla}: {e}")
            raise e

    return total_rows

def ensure_indexes(conn, tabla, cols):
    for col in cols:
        try: conn.execute(f'CREATE INDEX IF NOT EXISTS "idx_{tabla}_{col}" ON "{tabla}"("{col}")')
        except: pass

def proceso_descarga(config, es_reintento=False, stop_event=None):
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
        if stop_event and stop_event.is_set():
            log.warning("⚠️ Proceso detenido por usuario durante búsqueda FTP.")
            return

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
    if stop_event and stop_event.is_set(): return

    resultados = descargar_archivos_paralelo(config, tareas_descarga, workers=DEFAULT_WORKERS, stop_event=stop_event)
    
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
                cursor.execute(f"PRAGMA table_info(\"{tabla}\")")
                cols = [info[1] for info in cursor.fetchall()]
                if 'origen_archivo' in cols and 'anio' in cols:
                    cursor.execute(f"SELECT DISTINCT origen_archivo, anio FROM \"{tabla}\"")
                    for archivo, anio in cursor.fetchall():
                        if archivo: cache.add((str(archivo), str(anio)))
            except: pass
    except: pass
    log.info(f"🧠 Memoria lista: {len(cache)} archivos.")
    return cache

def proceso_base_datos(config, es_reintento=False, stop_event=None):
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
        if stop_event and stop_event.is_set():
            log.warning("⚠️ Proceso detenido por usuario durante actualización BD.")
            conn.close()
            return False

        nombre_archivo = os.path.basename(ruta_completa)
        nombre_tabla, fecha_identificador, version = extraer_info_nombre(nombre_archivo)
        anio_carpeta = obtener_anio_de_carpeta(ruta_completa)

        if (nombre_archivo, anio_carpeta) in archivos_procesados_cache: continue
        es_valido = False
        if nombre_tabla in ARCHIVOS_MENSUALES:
            if f"{anio_carpeta}-{fecha_identificador}" in meses_permitidos: es_valido = True
        else:
            if fecha_identificador in dias_permitidos: es_valido = True
        if not es_valido: continue

        archivo_corrupto = False
        razon = ""
        size_bytes = os.path.getsize(ruta_completa)
        if size_bytes == 0: archivo_corrupto = True; razon = "0 bytes"
        
        if archivo_corrupto:
            log.warning(f"🗑️ Corrupto ({razon}): {nombre_archivo} -> ELIMINADO")
            try: os.remove(ruta_completa)
            except: pass
            corruptos_eliminados += 1
            continue
            
        try:
            meta = {
                'origen_archivo': nombre_archivo,
                'anio': anio_carpeta,
                'mes_dia': fecha_identificador,
                'version_dato': version,
                'fecha_carga': str(pd.Timestamp.now())
            }
            
            rows = bulk_insert_fast(conn, ruta_completa, nombre_tabla, meta, chunksize=100000)
            
            if rows > 0:
                archivos_procesados_cache.add((nombre_archivo, anio_carpeta))
                tablas_tocadas.add(nombre_tabla)
                log.info(f"💾 Guardado ({rows} filas): {nombre_archivo}")
            else:
                raise Exception("Archivo vacío o sin datos válidos")
                
        except Exception as e:
            if "No columns to parse" in str(e) or "registros" in str(e).lower() or "vacío" in str(e).lower():
                log.warning(f"🗑️ Archivo vacío detectado: {nombre_archivo}")
                try: os.remove(ruta_completa)
                except: pass
                corruptos_eliminados += 1
            else:
                log.error(f"⚠️ Error leyendo {nombre_archivo}: {e}")

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
    if ext == 'tx1': return 100
    if ext == 'tx2': return 200
    if ext == 'txr': return 250
    if ext == 'txf': return 290
    if ext == 'txa': return 290
    match = re.search(r'tx(\d+)', ext)
    if match: return int(match.group(1)) * 100
    return 0 

def generar_reporte_logica(config, stop_event=None):
    log.info("🚀 INICIANDO GENERADOR HORIZONTAL XM (OPTIMIZADO)")
    ruta_local = config['ruta_local']
    ruta_db_completa = os.path.join(ruta_local, NOMBRE_DB_FILE)
    ruta_reporte_completa = os.path.join(ruta_local, NOMBRE_REPORTE_FILE)
    
    try:
        fecha_ini_str = config['fecha_ini']
        fecha_fin_str = config['fecha_fin']
        datetime.strptime(fecha_ini_str, "%Y-%m-%d")
        datetime.strptime(fecha_fin_str, "%Y-%m-%d")
    except: 
        log.error("Fechas inválidas")
        return

    tareas_a_procesar = config['filtros_reporte']
    
    if not os.path.exists(ruta_db_completa):
        log.error(f"❌ No existe la BD en: {ruta_db_completa}")
        return

    conn = sqlite3.connect(ruta_db_completa)
    cursor = conn.cursor()
    
    try:
        with pd.ExcelWriter(ruta_reporte_completa, engine='openpyxl') as writer:
            columna_actual = 0  
            tablas_escritas = 0
            
            for tarea in tareas_a_procesar:
                if stop_event and stop_event.is_set(): break

                tabla = tarea['tabla']
                col_filtro = tarea.get('campo')
                val_filtro = tarea.get('valor')
                ver_filtro = tarea.get('version')

                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND lower(name)='{tabla.lower()}'")
                res = cursor.fetchone()
                if not res: continue
                nombre_real_table = res[0]

                es_mensual = any(tabla.upper().startswith(x.upper()) for x in ARCHIVOS_MENSUALES)
                
                where_clauses = ["1=1"]
                
                if col_filtro and val_filtro:
                    where_clauses.append(f"CAST(\"{col_filtro}\" AS TEXT) = '{val_filtro}'")

                if ver_filtro and ver_filtro != "Última":
                    where_clauses.append(f"\"version_dato\" = '{ver_filtro}'")
                
                if es_mensual:
                    sql_date = f"CAST(anio AS TEXT) || '-' || printf('%02d', CAST(mes_dia AS INTEGER)) || '-01'"
                else:
                    col_md = "printf('%04d', CAST(mes_dia AS INTEGER))"
                    sql_date = f"CAST(anio AS TEXT) || '-' || substr({col_md}, 1, 2) || '-' || substr({col_md}, 3, 2)"

                where_clauses.append(f"date({sql_date}) BETWEEN date('{fecha_ini_str}') AND date('{fecha_fin_str}')")

                query = f'SELECT * FROM "{nombre_real_table}" WHERE {" AND ".join(where_clauses)}'
                
                try:
                    df = pd.read_sql_query(query, conn)
                    if df.empty: continue
                    
                    if es_mensual:
                         df['Fecha'] = pd.to_datetime(
                             df['anio'].astype(str) + '-' + 
                             df['mes_dia'].astype(str).str.zfill(2) + '-01'
                         )
                    else:
                         md_str = df['mes_dia'].astype(str).str.zfill(4)
                         df['Fecha'] = pd.to_datetime(
                             df['anio'].astype(str) + '-' + 
                             md_str.str.slice(0, 2) + '-' + 
                             md_str.str.slice(2, 4),
                             errors='coerce'
                         )
                    
                    df = df.dropna(subset=['Fecha'])

                    if not ver_filtro or ver_filtro == "Última":
                        df['peso'] = df['version_dato'].apply(calcular_peso_version)
                        df = df.sort_values(by=['Fecha', 'peso'], ascending=[True, True])
                        df = df.drop_duplicates(subset=['Fecha'], keep='last')
                        df = df.drop(columns=['peso'])

                    cols_borrar = ['anio', 'mes_dia', 'version_dato', 'origen_archivo', 'fecha_carga', 'index']
                    df = df.drop(columns=[c for c in cols_borrar if c in df.columns], errors='ignore')
                    
                    cols = ['Fecha'] + [c for c in df.columns if c != 'Fecha']
                    df = df[cols]
                    df['Fecha'] = df['Fecha'].dt.date

                    titulo = f"{tabla.upper()} {val_filtro if val_filtro else ''}"
                    pd.DataFrame({titulo: []}).to_excel(writer, sheet_name="Datos", startrow=0, startcol=columna_actual, index=False)
                    df.to_excel(writer, sheet_name="Datos", startrow=1, startcol=columna_actual, index=False)
                    columna_actual += len(df.columns) + 1 
                    tablas_escritas += 1
                    
                    print(f"   ✅ Exportado: {tabla}")

                except Exception as e:
                    log.error(f"Error procesando tabla {tabla}: {e}")

        if tablas_escritas > 0: log.info(f"✅ REPORTE LISTO: {ruta_reporte_completa}")
        else: log.warning("⚠️ Reporte vacío (verifique filtros o descargas).")
            
    except Exception as e:
        log.error(f"❌ Error fatal en reporte: {e}")
    finally:
        conn.close()

# =============================================================================
#  MÓDULO 4: VISUALIZADOR
# =============================================================================

class ModuloVisualizador:
    def __init__(self, parent_frame, config):
        self.frame_main = parent_frame
        self.ruta_db = config.get('ruta_db_viz', "BaseDatosXM.db")
        self.datos_actuales = None 
        
        # --- Variables ---
        self.var_tabla = tk.StringVar()
        self.var_version = tk.StringVar()
        self.var_campo_filtro1 = tk.StringVar()
        self.var_valor_filtro1 = tk.StringVar()
        self.var_campo_filtro2 = tk.StringVar()
        self.var_valor_filtro2 = tk.StringVar()
        self.var_campo_valor = tk.StringVar()
        self.var_agregacion = tk.StringVar(value="Promedio")
        self.var_tipo_grafico = tk.StringVar(value="Línea")
        self.var_color_grafico = tk.StringVar(value="Verde Corporativo")
        
        self.var_fecha_ini = tk.StringVar(value=config.get('viz_fecha_ini', '2025-01-01'))
        self.var_fecha_fin = tk.StringVar(value=config.get('viz_fecha_fin', datetime.today().strftime('%Y-%m-%d')))
        self.var_solo_un_dia = tk.BooleanVar(value=False)
        self.var_temporalidad = tk.StringVar(value="Diaria")

        # --- Top Bar (Estilo Cápsula) ---
        frame_top = tb.Frame(self.frame_main, padding=15)
        frame_top.pack(fill="x")
        
        # Input Group Redondeado
        lbl_db_title = tb.Label(frame_top, text="Base de Datos:", font=("Segoe UI", 10, "bold"))
        lbl_db_title.pack(side="left", padx=(0, 10))
        
        self.lbl_db = tb.Entry(frame_top, bootstyle="secondary") # Entry normal
        self.lbl_db.pack(side="left", fill="x", expand=True, padx=5)
        self.lbl_db.insert(0, os.path.abspath(self.ruta_db))
        
        # Botones Redondeados
        tb.Button(frame_top, text="📂", command=self.seleccionar_db, bootstyle="secondary-outline").pack(side="left", padx=2)
        tb.Button(frame_top, text="🔄 Actualizar", command=self.cargar_tablas, bootstyle="primary").pack(side="left", padx=10)

        # --- Grid de Controles ---
        frame_controls = tb.Frame(self.frame_main, padding=5)
        frame_controls.pack(fill="x")

        # Helper para Cards más limpias
        def crear_card_moderna(parent, titulo):
            # Usamos Labelframe pero con titulo en negrita y padding amplio
            lf = ttk.LabelFrame(parent, text=f" {titulo} ", padding=15)
            lf.pack(side="left", fill="both", expand=True, padx=8)
            lf.columnconfigure(1, weight=1)
            return lf

        def add_row(parent, row, label, widget):
            tb.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
            widget.grid(row=row, column=1, sticky="ew", padx=5, pady=6)

        # COLUMNA 1
        col1 = crear_card_moderna(frame_controls, "1. Fuente de Datos")
        self.cb_tabla = tb.Combobox(col1, textvariable=self.var_tabla, state="readonly", bootstyle="primary")
        self.cb_tabla.bind("<<ComboboxSelected>>", self.al_seleccionar_tabla)
        add_row(col1, 0, "Archivo:", self.cb_tabla)

        self.cb_version = tb.Combobox(col1, textvariable=self.var_version, state="readonly", bootstyle="primary")
        add_row(col1, 1, "Versión:", self.cb_version)

        self.cb_campo_filtro1 = CustomDropdownWithTooltip(col1, textvariable=self.var_campo_filtro1, command=self.al_seleccionar_campo_filtro1)
        add_row(col1, 2, "Filtro 1:", self.cb_campo_filtro1.entry)
        
        self.cb_valor_filtro1 = CustomDropdownWithTooltip(col1, textvariable=self.var_valor_filtro1)
        add_row(col1, 3, "Valor 1:", self.cb_valor_filtro1.entry)

        # COLUMNA 2
        col2 = crear_card_moderna(frame_controls, "2. Configuración")
        self.cb_temporalidad = tb.Combobox(col2, textvariable=self.var_temporalidad, state="readonly", bootstyle="info")
        self.cb_temporalidad['values'] = ["Diaria", "Mensual", "Horaria (24h)"]
        self.cb_temporalidad.bind("<<ComboboxSelected>>", self.toggle_campo_valor)
        add_row(col2, 0, "Temporalidad:", self.cb_temporalidad)

        self.lbl_valor = tb.Label(col2, text="Variable:")
        self.lbl_valor.grid(row=1, column=0, sticky="w", pady=6)
        self.cb_campo_valor = CustomDropdownWithTooltip(col2, textvariable=self.var_campo_valor)
        self.cb_campo_valor.entry.grid(row=1, column=1, sticky="ew", padx=5, pady=6)

        self.cb_agregacion = tb.Combobox(col2, textvariable=self.var_agregacion, state="readonly", bootstyle="info")
        self.cb_agregacion['values'] = ["Valor", "Promedio", "Suma", "Máximo", "Mínimo"]; self.cb_agregacion.current(0)
        add_row(col2, 2, "Operación:", self.cb_agregacion)

        self.cb_tipo = tb.Combobox(col2, textvariable=self.var_tipo_grafico, state="readonly", bootstyle="info")
        self.cb_tipo['values'] = ["Línea", "Barras", "Área", "Dispersión"]; self.cb_tipo.current(0)
        add_row(col2, 3, "Gráfico:", self.cb_tipo)

        self.cb_color = tb.Combobox(col2, textvariable=self.var_color_grafico, state="readonly", bootstyle="info")
        self.cb_color['values'] = list(COLORES_GRAFICO.keys()); self.cb_color.current(0)
        add_row(col2, 4, "Color:", self.cb_color)

        # COLUMNA 3
        col3 = crear_card_moderna(frame_controls, "3. Periodo")
        
        chk_single = tb.Checkbutton(col3, text="Solo un día", variable=self.var_solo_un_dia, bootstyle="round-toggle", command=self.toggle_single_day)
        chk_single.pack(fill="x", pady=(0, 10))

        def crear_fila_fecha(parent, var, label_text):
            f = tb.Frame(parent)
            f.pack(fill="x", pady=4)
            tb.Label(f, text=label_text, width=6).pack(side="left")
            
            # Botones circulares (Outline)
            btn_prev = tb.Button(f, text="◀", bootstyle="secondary-outline", width=2, command=lambda: self.mover_fecha(var, -1))
            btn_prev.pack(side="left", padx=3)
            
            e = tb.Entry(f, textvariable=var, width=12, justify="center")
            e.pack(side="left", padx=3)
            e.bind("<FocusOut>", self.actualizar_versiones)
            
            btn_next = tb.Button(f, text="▶", bootstyle="secondary-outline", width=2, command=lambda: self.mover_fecha(var, 1))
            btn_next.pack(side="left", padx=3)
            return e

        self.ent_fecha_ini = crear_fila_fecha(col3, self.var_fecha_ini, "Inicio:")
        self.ent_fecha_fin = crear_fila_fecha(col3, self.var_fecha_fin, "Fin:")
        
        f_actions = tb.Frame(col3)
        f_actions.pack(fill="x", pady=(20, 0))
        # Botones de acción principales con estilo ROUNDED
        tb.Button(f_actions, text="📊 GRAFICAR", command=self.generar_grafico, bootstyle="primary").pack(fill="x", pady=3)
        tb.Button(f_actions, text="📥 EXCEL", command=self.exportar_datos_excel, bootstyle="success-outline").pack(fill="x", pady=3)

        # --- Stats ---
        self.frame_stats = tb.Frame(self.frame_main, padding=10, bootstyle="bg")
        self.frame_stats.pack(fill="x", padx=10, pady=5)
        
        def add_stat(label, color):
            # Simulamos una 'Pill' o etiqueta redondeada
            lbl = tb.Label(self.frame_stats, text=f"{label}: --", font=('Segoe UI', 9, 'bold'), foreground=color)
            lbl.pack(side="left", padx=20)
            return lbl

        self.lbl_stat_prom = add_stat("Promedio", "#2c3e50")
        self.lbl_stat_max = add_stat("Max", "#18bc9c")
        self.lbl_stat_min = add_stat("Min", "#e74c3c")
        self.lbl_stat_sum = add_stat("Suma", "#3498db")

        # --- Plot ---
        self.frame_plot = tb.Frame(self.frame_main, relief="flat") # Sin bordes para look limpio
        self.frame_plot.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        if os.path.exists(self.ruta_db): self.cargar_tablas()

    # --- MÉTODOS DE LÓGICA (Idénticos al anterior) ---
    def mover_fecha(self, variable, dias):
        try:
            actual = datetime.strptime(variable.get(), '%Y-%m-%d')
            nueva = actual + timedelta(days=dias)
            variable.set(nueva.strftime('%Y-%m-%d'))
            if self.var_solo_un_dia.get() and variable == self.var_fecha_ini:
                self.var_fecha_fin.set(variable.get())
            self.actualizar_versiones()
        except: pass

    def toggle_single_day(self):
        if self.var_solo_un_dia.get():
            self.ent_fecha_fin.configure(state='disabled')
            self.var_fecha_fin.set(self.var_fecha_ini.get())
        else:
            self.ent_fecha_fin.configure(state='normal')

    # ... (Copia aquí el resto de métodos: toggle_campo_valor, seleccionar_db, conectar, 
    # cargar_tablas, al_seleccionar_tabla, actualizar_versiones, _cargar_valores_filtro, 
    # al_seleccionar_campo_filtro1/2, generar_grafico, exportar_datos_excel, dibujar_plot)
    # IMPORTANTE: No necesitas cambiar nada en la lógica interna de esos métodos, solo la UI arriba.
    
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
        self.var_agregacion.set("Promedio"); self.var_tipo_grafico.set("Línea"); self.var_campo_valor.set('')
        conn = self.conectar(); cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({tabla})"); info = cur.fetchall(); cols = [c[1] for c in info]
        self.actualizar_versiones()
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
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info({tabla})"); info = cur.fetchall(); cols = [c[1] for c in info]
            if 'version_dato' not in cols:
                self.cb_version['values'] = []; self.cb_version.set("N/A")
                conn.close(); return
            
            f_ini_str = self.var_fecha_ini.get().replace("-", "")
            f_fin_str = self.var_fecha_fin.get().replace("-", "")
            es_mensual_var = any(tabla.lower().startswith(x.lower()) for x in ARCHIVOS_MENSUALES)

            if es_mensual_var:
                query = f"SELECT DISTINCT version_dato FROM {tabla} WHERE (CAST(anio AS TEXT) || printf('%02d', CAST(mes_dia AS INTEGER))) BETWEEN '{f_ini_str[:6]}' AND '{f_fin_str[:6]}' ORDER BY version_dato"
            else:
                query = f"SELECT DISTINCT version_dato FROM {tabla} WHERE (CAST(anio AS TEXT) || printf('%04d', CAST(mes_dia AS INTEGER))) BETWEEN '{f_ini_str}' AND '{f_fin_str}' ORDER BY version_dato"

            versiones_df = pd.read_sql_query(query, conn)
            lista_versiones = versiones_df['version_dato'].astype(str).tolist()
            if lista_versiones: lista_versiones.insert(0, "Última")
            self.cb_version['values'] = lista_versiones
            if lista_versiones: self.cb_version.current(0)
            
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
            if hasattr(widget_cb, 'update_items'):
                widget_cb.update_items(vals)
                if widget_cb == self.cb_valor_filtro1: self.var_valor_filtro1.set('')
                elif widget_cb == self.cb_valor_filtro2: self.var_valor_filtro2.set('')
            else: widget_cb['values'] = vals; widget_cb.set('')
        except: pass

    def generar_grafico(self):
        # ... (Mantener tu lógica de generar_grafico sin cambios, es la versión optimizada)
        # Solo asegúrate de copiar y pegar la versión BLINDADA y VECTORIZADA que te di antes.
        # Por brevedad en el chat no la repito toda, pero usa la que ya tenías funcionando.
        tabla = self.var_tabla.get(); version = self.var_version.get()
        campo1 = self.var_campo_filtro1.get(); valor1 = self.var_valor_filtro1.get()
        campo2 = self.var_campo_filtro2.get(); valor2 = self.var_valor_filtro2.get()
        operacion = self.var_agregacion.get(); temporalidad = self.var_temporalidad.get()
        f_ini_str = self.var_fecha_ini.get(); f_fin_str = self.var_fecha_fin.get()
        
        tipo_grafico = self.var_tipo_grafico.get()
        nombre_color = self.var_color_grafico.get()
        color_hex = COLORES_GRAFICO.get(nombre_color, "#18bc9c")

        if not tabla: return

        try:
            conn = self.conectar()
            where_clauses = ["1=1"]
            params = []

            if campo1 and valor1: 
                where_clauses.append(f"CAST({campo1} AS TEXT) = ?")
                params.append(valor1)
            
            if campo2 and valor2: 
                where_clauses.append(f"CAST({campo2} AS TEXT) = ?")
                params.append(valor2)
            
            if version and version not in ["N/A", "Última"]: 
                where_clauses.append("version_dato = ?")
                params.append(version)
            
            es_mensual_graf = any(tabla.lower().startswith(x.lower()) for x in ARCHIVOS_MENSUALES)
            
            if es_mensual_graf:
                sql_date = f"CAST(anio AS TEXT) || '-' || printf('%02d', CAST(mes_dia AS INTEGER)) || '-01'"
            else:
                col_md = "printf('%04d', CAST(mes_dia AS INTEGER))"
                sql_date = f"CAST(anio AS TEXT) || '-' || substr({col_md}, 1, 2) || '-' || substr({col_md}, 3, 2)"
            
            where_clauses.append(f"date({sql_date}) BETWEEN date(?) AND date(?)")
            params.extend([f_ini_str, f_fin_str])

            query = f"SELECT * FROM {tabla} WHERE {' AND '.join(where_clauses)}"
            
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            if df.empty: 
                messagebox.showinfo("Vacío", f"No hay datos para graficar en ese rango.")
                return

            df['anio'] = pd.to_numeric(df['anio'], errors='coerce')
            df['mes_dia'] = pd.to_numeric(df['mes_dia'], errors='coerce')
            df.dropna(subset=['anio', 'mes_dia'], inplace=True)

            if es_mensual_graf:
                temp_dates = pd.DataFrame({'year': df['anio'], 'month': df['mes_dia'], 'day': 1})
                df['Fecha'] = pd.to_datetime(temp_dates, errors='coerce')
            else:
                temp_dates = pd.DataFrame({'year': df['anio'], 'month': df['mes_dia'] // 100, 'day': df['mes_dia'] % 100})
                df['Fecha'] = pd.to_datetime(temp_dates, errors='coerce')

            df = df.dropna(subset=['Fecha'])

            if version == "Última":
                df['peso'] = df['version_dato'].apply(calcular_peso_version)
                df.sort_values(by=['Fecha', 'peso'], ascending=[True, True], inplace=True)
                df.drop_duplicates(subset=['Fecha'], keep='last', inplace=True)
                df.drop(columns=['peso'], inplace=True, errors='ignore')

            serie_graficar = None
            if temporalidad == "Horaria (24h)":
                cols_range_1 = [str(i) for i in range(1, 25)]
                cols_range_0 = [str(i) for i in range(24)]
                cols_existentes = set(df.columns)
                if set(cols_range_1).issubset(cols_existentes): cols_horas = cols_range_1; es_base_0 = False
                elif set(cols_range_0).issubset(cols_existentes): cols_horas = cols_range_0; es_base_0 = True
                else: cols_horas = [c for c in df.columns if 'hora' in c.lower()]; es_base_0 = False

                for c in cols_horas: df[c] = pd.to_numeric(df[c], errors='coerce')
                
                if operacion == "Valor":
                    df_melted = df.melt(id_vars=['Fecha'], value_vars=cols_horas, var_name='HoraStr', value_name='Res')
                    df_melted['Hora'] = pd.to_numeric(df_melted['HoraStr'].astype(str).str.extract(r'(\d+)')[0], errors='coerce').fillna(0).astype(int)
                    if not es_base_0: df_melted['Hora'] = df_melted['Hora'] - 1
                    df_melted['FechaHora'] = df_melted['Fecha'] + pd.to_timedelta(df_melted['Hora'], unit='h')
                    serie_graficar = df_melted.set_index('FechaHora')['Res']
                else:
                    if operacion == "Promedio": df['Res'] = df[cols_horas].mean(axis=1)
                    elif operacion == "Suma": df['Res'] = df[cols_horas].sum(axis=1)
                    elif operacion == "Máximo": df['Res'] = df[cols_horas].max(axis=1)
                    elif operacion == "Mínimo": df['Res'] = df[cols_horas].min(axis=1)
                    serie_graficar = df.groupby('Fecha')['Res'].mean()
            else:
                col_val = self.var_campo_valor.get()
                if not col_val:
                    excl = {'anio', 'mes_dia', 'version_dato', 'fecha', 'year', 'month', 'day'}
                    for c in df.columns:
                        if c.lower() not in excl and pd.to_numeric(df[c], errors='coerce').notna().any():
                            col_val = c; self.var_campo_valor.set(col_val); break
                    if not col_val: messagebox.showwarning("Info", "Selecciona variable."); return
                
                df[col_val] = pd.to_numeric(df[col_val], errors='coerce')
                if temporalidad == "Mensual": df['Fecha'] = df['Fecha'].values.astype('datetime64[M]')
                grupo = df.groupby('Fecha')[col_val]
                if operacion == "Promedio": serie_graficar = grupo.mean()
                elif operacion == "Suma": serie_graficar = grupo.sum()
                elif operacion == "Máximo": serie_graficar = grupo.max()
                elif operacion == "Mínimo": serie_graficar = grupo.min()
                elif operacion == "Valor": serie_graficar = grupo.mean()

            self.datos_actuales = serie_graficar.sort_index()
            
            if temporalidad == "Horaria (24h)":
                partes = []
                if valor1: partes.append(valor1)
                if valor2: partes.append(valor2)
                self.var_actual_excel = " - ".join(partes) if partes else "Promedio 24h"
            else: self.var_actual_excel = self.var_campo_valor.get()
            
            val_prom = self.datos_actuales.mean(); val_max = self.datos_actuales.max()
            val_min = self.datos_actuales.min(); val_sum = self.datos_actuales.sum()
            self.lbl_stat_prom.config(text=f"Promedio: {val_prom:,.2f}")
            self.lbl_stat_max.config(text=f"Max: {val_max:,.2f}")
            self.lbl_stat_min.config(text=f"Min: {val_min:,.2f}")
            self.lbl_stat_sum.config(text=f"Suma: {val_sum:,.2f}")

            titulo_grafico = f"{tabla.upper()}"
            if valor1: titulo_grafico += f"\n{valor1}"
            if valor2: titulo_grafico += f" - {valor2}"
            if temporalidad == "Horaria (24h)" and f_ini_str == f_fin_str:
                titulo_grafico += f"\n[{f_ini_str}]"
            if operacion != "Valor": titulo_grafico += f" ({operacion})"
            
            self.titulo_actual = titulo_grafico.replace("\n", " ")
            self.dibujar_plot(self.datos_actuales, titulo_grafico, tipo_grafico, color_hex, temporalidad)
        except Exception as e:
            messagebox.showerror("Error Generando Gráfico", f"Ocurrió un error: {str(e)}")

    def exportar_datos_excel(self):
        if self.datos_actuales is None: messagebox.showwarning("Sin Datos", "Primero genera un gráfico."); return
        file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")])
        if not file_path: return
        try:
            df_export = self.datos_actuales.reset_index(); df_export.columns = ['Fecha', 'Valor']
            nombre_var = getattr(self, 'var_actual_excel', 'Desconocido')
            df_export.insert(1, 'Variable', nombre_var)
            df_export['Fecha'] = df_export['Fecha'].dt.date 
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name="Datos Gráfico")
            messagebox.showinfo("Éxito", f"Datos exportados a:\n{file_path}")
        except Exception as e: messagebox.showerror("Error", str(e))

    def dibujar_plot(self, serie, titulo, tipo, color, temporalidad="Diaria"):
        for widget in self.frame_plot.winfo_children(): widget.destroy()
        fig = Figure(figsize=(8, 4.1), dpi=100, facecolor='#ffffff')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#ffffff')
        ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#bdc3c7'); ax.spines['bottom'].set_color('#bdc3c7')
        ax.grid(True, axis='y', linestyle=':', color='#ecf0f1', linewidth=1.5, alpha=0.8, zorder=0)
        ax.set_axisbelow(True)
        
        if tipo == "Línea":
            ax.plot(serie.index, serie.values, marker='o', linestyle='-', markersize=5, color=color, linewidth=2, zorder=3)
            ax.fill_between(serie.index, serie.values, color=color, alpha=0.1, zorder=2)
        elif tipo == "Barras":
            ancho = 20 if temporalidad == "Mensual" else 0.8
            ax.bar(serie.index, serie.values, color=color, alpha=0.85, width=ancho, edgecolor=color, zorder=3)
        elif tipo == "Área":
            ax.fill_between(serie.index, serie.values, color=color, alpha=0.5, zorder=3)
            ax.plot(serie.index, serie.values, color=color, linewidth=2, zorder=4)
        elif tipo == "Dispersión":
            ax.scatter(serie.index, serie.values, color=color, s=40, alpha=0.8, zorder=3)
        
        line_ghost, = ax.plot(serie.index, serie.values, color=color, alpha=0.0) 
        try: init_x = serie.index[0]
        except: init_x = 0
        cursor_line = ax.axvline(x=init_x, color='#7f8c8d', linestyle='--', linewidth=1, alpha=0.6, zorder=0)
        cursor_line.set_visible(False)

        ax.set_title(titulo, fontname='Segoe UI', fontsize=12, weight='bold', color='#2c3e50', pad=15)
        if temporalidad == "Mensual":
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.MonthLocator())
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            if len(serie) > 30: fig.autofmt_xdate(rotation=45)
        
        ax.tick_params(axis='x', colors='#7f8c8d', labelsize=9)
        ax.tick_params(axis='y', colors='#7f8c8d', labelsize=9)
        ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}')) 

        annot = ax.annotate("", xy=(0,0), xytext=(10,10),textcoords="offset points",
                            bbox=dict(boxstyle="round4,pad=0.5", fc="#ffffff", ec="#bdc3c7", alpha=0.95, lw=1),
                            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.1", color="#7f8c8d"))
        annot.set_visible(False)

        def update_annot(ind):
            x, y = line_ghost.get_data()
            idx = ind["ind"][0]
            val_x = x[idx]; annot.xy = (val_x, y[idx])
            try: fecha_dt = mdates.num2date(val_x)
            except: fecha_dt = val_x
            fmt = "%Y-%m" if temporalidad == "Mensual" else "%Y-%m-%d"
            try: f_str = fecha_dt.strftime(fmt)
            except: f_str = "?"
            annot.set_text(f"{f_str}\n{y[idx]:,.2f}")

        def hover(event):
            vis = annot.get_visible(); vis_line = cursor_line.get_visible()
            if event.inaxes == ax:
                cursor_line.set_xdata([event.xdata, event.xdata])
                if not vis_line: cursor_line.set_visible(True)
                cont, ind = line_ghost.contains(event)
                if cont: 
                    update_annot(ind); annot.set_visible(True); fig.canvas.draw_idle()
                elif vis: annot.set_visible(False); fig.canvas.draw_idle()
                else: fig.canvas.draw_idle()
            elif vis_line or vis:
                cursor_line.set_visible(False); annot.set_visible(False); fig.canvas.draw_idle()

        fig.canvas.mpl_connect("motion_notify_event", hover)
        try: fig.tight_layout(rect=[0, 0.05, 1, 0.88], pad=2.0)
        except: pass
        
        canvas = FigureCanvasTkAgg(fig, master=self.frame_plot)
        canvas.draw()
        toolbar = NavigationToolbar2Tk(canvas, self.frame_plot); toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# =============================================================================
#  INTERFAZ GRÁFICA PRINCIPAL
# =============================================================================

class AplicacionXM:
    def __init__(self, root):
        self.root = root
        self.root.title("Suite XM Inteligente - Enerconsult (MODERN UI)")
        
        # Geometría centrada
        screen_width = self.root.winfo_screenwidth(); screen_height = self.root.winfo_screenheight()
        w_app = int(screen_width * 0.85); h_app = int(screen_height * 0.85)
        x_pos = (screen_width - w_app) // 2; y_pos = (screen_height - h_app) // 2
        self.root.geometry(f"{w_app}x{h_app}+{x_pos}+{y_pos}")
        try: self.root.state('zoomed')
        except: self.root.attributes('-zoomed', True)
        
        self.config = self.cargar_config()
        self.stop_event = threading.Event()
        self.construir_encabezado_logo()

        # Console area
        console_container = tb.Frame(root, bootstyle="dark")
        console_container.pack(side="bottom", fill="x", expand=False)
        
        header_frame = tb.Frame(console_container, bootstyle="dark", padding=5)
        header_frame.pack(fill="x", side="top")
        
        tb.Label(header_frame, text=">_ Monitor de Ejecución", font=("Consolas", 10, "bold"), bootstyle="inverse-dark").pack(side="left", padx=10)
        
        def limpiar_consola():
            self.txt_console.config(state="normal"); self.txt_console.delete(1.0, tk.END); self.txt_console.config(state="disabled")
        
        tb.Button(header_frame, text="🗑️ Limpiar", command=limpiar_consola, bootstyle="secondary-outline", width=10).pack(side="right", padx=10)
        
        self.txt_console = scrolledtext.ScrolledText(console_container, height=6, state='disabled', bg='#2c3e50', fg='#2ecc71', font=('Consolas', 10), relief='flat', borderwidth=0)
        self.txt_console.pack(fill="x", expand=False)
        sys.stdout = PrintRedirector(self.txt_console)

        # Tabs Modernos
        tab_control = tb.Notebook(root, bootstyle="light")
        self.tab_general = tb.Frame(tab_control)
        self.tab_archivos = tb.Frame(tab_control)
        self.tab_filtros = tb.Frame(tab_control)
        self.tab_visualizador = tb.Frame(tab_control)
        
        tab_control.add(self.tab_general, text='🔧 Configuración')
        tab_control.add(self.tab_archivos, text='📥 Descargas')
        tab_control.add(self.tab_filtros, text='📋 Filtros Reporte')
        tab_control.add(self.tab_visualizador, text='📈 Visualizador')
        tab_control.pack(expand=True, fill="both", padx=10, pady=10)

        def on_tab_change(event):
            try:
                if "Visualizador" in tab_control.tab(tab_control.select(), "text"): self.txt_console.configure(height=4)
                else: self.txt_console.configure(height=6)
            except: pass
        tab_control.bind("<<NotebookTabChanged>>", on_tab_change)

        self.crear_tab_general(); self.crear_tab_archivos(); self.crear_tab_filtros()
        self.app_visualizador = ModuloVisualizador(self.tab_visualizador, self.config)
        self.actualizar_dashboard()
        self.update_logger_output()

    def update_logger_output(self):
        logger = logging.getLogger("RobotXM")
        for h in logger.handlers[:]:
            if type(h) is logging.StreamHandler: logger.removeHandler(h)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        ch.setLevel(logging.INFO)
        logger.addHandler(ch)

    def toggle_controls(self, state='normal'):
        try:
            self.btn_guardar.config(state=state); self.btn_descargar.config(state=state); self.btn_reporte.config(state=state)
        except: pass

    def validar_config(self):
        cfg = self.get_config()
        if not cfg['usuario'] or not cfg['password']: messagebox.showwarning("Incompleto", "Ingrese Usuario y Password FTP."); return False
        if not os.path.exists(cfg['ruta_local']):
            try: os.makedirs(cfg['ruta_local'])
            except: messagebox.showerror("Error", "Ruta local inválida."); return False
        return True

    def add_placeholder(self, entry, text):
        entry.insert(0, text)
        try: entry.configure(foreground="#95a5a6") # Gray
        except: pass
        def on_focus_in(event):
            if entry.get() == text: entry.delete(0, tk.END); entry.configure(foreground="#2c3e50")
        def on_focus_out(event):
            if not entry.get(): entry.insert(0, text); entry.configure(foreground="#95a5a6")
        entry.bind("<FocusIn>", on_focus_in); entry.bind("<FocusOut>", on_focus_out)

    def construirm_encabezado_logo(self):
        # ... (Mantener lógica de logo si existe)
        pass

    def construir_encabezado_logo(self):
        frame_header = tb.Frame(self.root, bootstyle="light")
        frame_header.pack(fill="x", side="top", pady=5)
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ruta_logo = os.path.join(script_dir, LOGO_FILENAME)
        
        if TIENE_PILLOW and os.path.exists(ruta_logo):
            try:
                pil_img = Image.open(ruta_logo)
                base_height = 50 
                w_percent = (base_height / float(pil_img.size[1]))
                w_size = int((float(pil_img.size[0]) * float(w_percent)))
                pil_img = pil_img.resize((w_size, base_height), RESAMPLE_LANCZOS)
                self.logo_img = ImageTk.PhotoImage(pil_img)
                lbl_logo = tk.Label(frame_header, image=self.logo_img, bg="#f8f9fa")
                lbl_logo.pack(side="left", padx=20)
                
                # Título Empresa
                tb.Label(frame_header, text="Suite Inteligente Enerconsult", font=("Segoe UI", 18, "bold"), bootstyle="primary").pack(side="left", padx=10)
            except: pass
        else:
            tb.Label(frame_header, text="Suite Inteligente Enerconsult", font=("Segoe UI", 18, "bold"), bootstyle="primary").pack(side="left", padx=20, pady=10)

    def crear_tab_general(self):
        main_container = tb.Frame(self.tab_general)
        main_container.pack(fill="both", expand=True, padx=20, pady=10)
        
        card_main = Card(main_container)
        card_main.pack(fill="x", pady=(0, 10))
        c_content = card_main.get_body()
        c_content.columnconfigure(0, weight=1); c_content.columnconfigure(1, weight=1)

        tb.Label(c_content, text="Credenciales FTP y Rutas", font=("Segoe UI", 12, "bold"), bootstyle="primary").grid(row=0, column=0, columnspan=2, sticky="w", padx=0, pady=(0, 10))
        
        tb.Label(c_content, text="Usuario FTP").grid(row=1, column=0, sticky="w", pady=2, padx=(0, 10))
        self.ent_user = tb.Entry(c_content)
        self.ent_user.grid(row=2, column=0, sticky="ew", padx=(0, 20), pady=(0, 5))
        self.ent_user.insert(0, self.config.get('usuario', ''))

        tb.Label(c_content, text="Password FTP").grid(row=1, column=1, sticky="w", pady=2, padx=(0, 10))
        self.ent_pass = tb.Entry(c_content, show="*")
        self.ent_pass.grid(row=2, column=1, sticky="ew", pady=(0, 5))
        self.ent_pass.insert(0, self.config.get('password', ''))

        tb.Label(c_content, text="Ruta Local").grid(row=3, column=0, sticky="w", pady=2, padx=(0, 10))
        fr_ruta = tb.Frame(c_content)
        fr_ruta.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 10)) 
        self.ent_ruta = tb.Entry(fr_ruta)
        self.ent_ruta.pack(side="left", fill="x", expand=True)
        self.ent_ruta.insert(0, self.config.get('ruta_local', ''))
        self.btn_fold = RoundedButtonWrapper(fr_ruta, text="📂", style="Primary.TButton", width=5, command=self.seleccionar_carpeta)
        self.btn_fold.pack(side="left", padx=(5, 0))

        ttk.Separator(c_content, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", pady=(5, 5))
        tb.Label(c_content, text="Rango de Fechas (YYYY-MM-DD)", font=("Segoe UI", 10, "bold"), bootstyle="primary").grid(row=6, column=0, columnspan=2, sticky="w", padx=0, pady=(5, 5))
        
        tb.Label(c_content, text="Fecha Inicio").grid(row=7, column=0, sticky="w", pady=2, padx=(0, 10))
        self.ent_ini = tb.Entry(c_content)
        self.ent_ini.grid(row=8, column=0, sticky="ew", padx=(0, 20))
        self.ent_ini.insert(0, self.config.get('fecha_ini', '2025-01-01'))
        
        tb.Label(c_content, text="Fecha Fin").grid(row=7, column=1, sticky="w", pady=2, padx=(0, 10))
        self.ent_fin = tb.Entry(c_content)
        self.ent_fin.grid(row=8, column=1, sticky="ew")
        self.ent_fin.insert(0, self.config.get('fecha_fin', '2025-01-31'))

        row_actions = tb.Frame(main_container)
        row_actions.pack(pady=(0, 2))
        
        def create_action_btn(parent, text, icon, color, command):
            style = "primary"
            if color == "green": style = "success"
            elif color == "red": style = "danger"
            return tb.Button(parent, text=f"{icon}  {text}", bootstyle=style, command=command, width=25)

        self.btn_guardar = create_action_btn(row_actions, "GUARDAR CONFIG", "📁", "green", self.guardar_config)
        self.btn_guardar.grid(row=0, column=0, padx=10)
        self.btn_descargar = create_action_btn(row_actions, "EJECUTAR DESCARGA", "⏬", "blue", self.run_descarga)
        self.btn_descargar.grid(row=0, column=1, padx=10)
        self.btn_reporte = create_action_btn(row_actions, "GENERAR REPORTE", "📊", "blue", self.run_reporte)
        self.btn_reporte.grid(row=0, column=2, padx=10)
        self.btn_reset = create_action_btn(row_actions, "RESET", "⏹️", "red", self.reset_process)
        self.btn_reset.grid(row=0, column=3, padx=10)

        self.frame_dashboard = tb.Frame(main_container)
        self.frame_dashboard.pack(fill="both", expand=True, pady=10)
        self.actualizar_dashboard()

    def crear_tab_archivos(self):
        main_container = tb.Frame(self.tab_archivos)
        main_container.pack(fill="both", expand=True, padx=20, pady=10)

        card_input = Card(main_container)
        card_input.pack(fill="x", pady=(0, 10))
        c1 = card_input.get_body()
        c1.columnconfigure(0, weight=1); c1.columnconfigure(1, weight=2); c1.columnconfigure(2, weight=0)

        tb.Label(c1, text="Nombre Archivo").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        self.ent_f_nom = tb.Entry(c1); self.ent_f_nom.grid(row=1, column=0, sticky="ew", padx=5, pady=2)
        self.add_placeholder(self.ent_f_nom, "ej: trsd, PEI, tserv")

        tb.Label(c1, text="Ruta FTP").grid(row=0, column=1, sticky="w", pady=5, padx=5)
        self.ent_f_rut = tb.Entry(c1); self.ent_f_rut.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        self.add_placeholder(self.ent_f_rut, "ej: /Reportes/Predespacho")

        self.btn_add_file = RoundedButtonWrapper(c1, text="+", command=self.add_file, style="Success.TButton", width=5)
        self.btn_add_file.grid(row=1, column=2, padx=5)

        card_list = Card(main_container)
        card_list.pack(fill="both", expand=True, pady=(0, 10))
        c2 = card_list.get_body()
        
        self.tree_files = tb.Treeview(c2, columns=("nombre", "ruta", "acciones"), show="headings", height=8, bootstyle="primary")
        self.tree_files.heading("nombre", text="Nombre Archivo", anchor="w")
        self.tree_files.heading("ruta", text="Ruta FTP", anchor="w")
        self.tree_files.heading("acciones", text="Acciones", anchor="center") 
        self.tree_files.column("nombre", width=150); self.tree_files.column("ruta", width=400, stretch=True); self.tree_files.column("acciones", width=80, anchor="center")
        
        scrollbar = tb.Scrollbar(c2, orient="vertical", command=self.tree_files.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree_files.configure(yscrollcommand=scrollbar.set)
        self.tree_files.pack(side="left", fill="both", expand=True)
        
        for idx, i in enumerate(self.config.get('archivos_descarga', [])):
            self.tree_files.insert("", "end", values=(i['nombre_base'], i['ruta_remota'], "🗑️"))

        self.tree_files.bind("<Button-1>", lambda e: self.del_file() if self.tree_files.identify_column(e.x) == "#3" else None)

        fr_info = tb.Frame(main_container, padding=10)
        fr_info.pack(fill="x")
        self.lbl_info_files_summary = tb.Label(fr_info, text=f"Archivos Configurados: {len(self.tree_files.get_children())}", bootstyle="info")
        self.lbl_info_files_summary.pack(side="left")

    def crear_tab_filtros(self):
        main_container = tb.Frame(self.tab_filtros)
        main_container.pack(fill="both", expand=True, padx=20, pady=10)

        fr_card_input = tb.Frame(main_container)
        fr_card_input.pack(fill="x", pady=(0, 10))
        card_input = Card(fr_card_input); card_input.pack(fill="both", expand=True)
        c1 = card_input.get_body()

        c1.columnconfigure(0, weight=1); c1.columnconfigure(1, weight=1); c1.columnconfigure(2, weight=1); c1.columnconfigure(3, weight=0, minsize=80); c1.columnconfigure(4, weight=0)

        tb.Label(c1, text="Tabla").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        self.ent_r_tab = tb.Entry(c1); self.ent_r_tab.grid(row=1, column=0, sticky="ew", padx=5, pady=2)
        self.add_placeholder(self.ent_r_tab, "ej: trsd, afac")

        tb.Label(c1, text="Campo").grid(row=0, column=1, sticky="w", pady=5, padx=5)
        self.ent_r_cam = tb.Entry(c1); self.ent_r_cam.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        self.add_placeholder(self.ent_r_cam, "ej: Recurso, Agente")

        tb.Label(c1, text="Valor").grid(row=0, column=2, sticky="w", pady=5, padx=5)
        self.ent_r_val = tb.Entry(c1); self.ent_r_val.grid(row=1, column=2, sticky="ew", padx=5, pady=2)
        self.add_placeholder(self.ent_r_val, "ej: IXEG")

        tb.Label(c1, text="Versión").grid(row=0, column=3, sticky="w", pady=5, padx=5)
        self.cb_r_ver = tb.Combobox(c1, values=["Última", "tx1", "tx2", "tx3", "txR", "txF"], state="readonly", width=10)
        self.cb_r_ver.set("Última"); self.cb_r_ver.grid(row=1, column=3, sticky="ew", padx=5)
        self.cb_r_ver.bind("<<ComboboxSelected>>", self.actualizar_todas_versiones_filtro)

        fr_btns = tb.Frame(c1); fr_btns.grid(row=1, column=4, padx=5)
        def small_btn(txt, cmd, color="#0093d0"):
            style = "primary"
            if color == "#8cc63f": style = "success"
            b = tb.Button(fr_btns, text=txt, bootstyle=style, width=4, command=cmd)
            b.pack(side="left", padx=2)
            return b
        small_btn("✚", self.add_filtro, "#8cc63f"); small_btn("▲", self.move_up); small_btn("▼", self.move_down)

        fr_card_list = tb.Frame(main_container)
        fr_card_list.pack(fill="both", expand=True, pady=(0, 10))
        card_list = Card(fr_card_list); card_list.pack(fill="both", expand=True)
        c2 = card_list.get_body()
        
        self.tree_filtros = tb.Treeview(c2, columns=("tabla", "campo", "valor", "version", "acciones"), show="headings", height=8, bootstyle="info")
        self.tree_filtros.heading("tabla", text="Tabla", anchor="w"); self.tree_filtros.heading("campo", text="Campo", anchor="w")
        self.tree_filtros.heading("valor", text="Valor", anchor="w"); self.tree_filtros.heading("version", text="Versión", anchor="center")
        self.tree_filtros.heading("acciones", text="Acciones", anchor="center")
        self.tree_filtros.column("tabla", width=120); self.tree_filtros.column("campo", width=150)
        self.tree_filtros.column("valor", width=200, stretch=True); self.tree_filtros.column("version", width=100, anchor="center")
        self.tree_filtros.column("acciones", width=80, anchor="center")
        
        scrollbar = tb.Scrollbar(c2, orient="vertical", command=self.tree_filtros.yview)
        scrollbar.pack(side="right", fill="y"); self.tree_filtros.configure(yscrollcommand=scrollbar.set)
        self.tree_filtros.pack(side="left", fill="both", expand=True)
        
        for idx, i in enumerate(self.config.get('filtros_reporte', [])):
            self.tree_filtros.insert("", "end", values=(i['tabla'], i.get('campo',''), i.get('valor',''), i.get('version',''), "🗑️"))
        self.tree_filtros.bind("<Button-1>", lambda e: self.del_filtro() if self.tree_filtros.identify_column(e.x) == "#5" else None)

        fr_info = tb.Frame(main_container, padding=10) 
        fr_info.pack(fill="x")
        self.lbl_info_filtros_summary = tb.Label(fr_info, text=f"Filtros Configurados: {len(self.tree_filtros.get_children())}", bootstyle="info")
        self.lbl_info_filtros_summary.pack(side="left")

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
            if idx < len(self.tree_filtros.get_children()) - 1: self.tree_filtros.move(item_id, "", idx + 1); self.tree_filtros.see(item_id)

    def seleccionar_carpeta(self):
        d = filedialog.askdirectory()
        if d: self.ent_ruta.delete(0, tk.END); self.ent_ruta.insert(0, d)
    
    def add_file(self):
        nom, rut = self.ent_f_nom.get(), self.ent_f_rut.get()
        if nom and rut and nom != "ej: trsd, PEI, tserv":
            self.tree_files.insert("", "end", values=(nom, rut, "🗑️"))
            self.ent_f_nom.delete(0, tk.END); self.add_placeholder(self.ent_f_nom, "ej: trsd, PEI, tserv")
            self.ent_f_rut.delete(0, tk.END); self.add_placeholder(self.ent_f_rut, "ej: /Reportes/Predespacho")
            self.update_file_count_ui()

    def del_file(self):
        for s in self.tree_files.selection(): self.tree_files.delete(s)
        self.update_file_count_ui()
    def update_file_count_ui(self):
        if hasattr(self, 'lbl_info_files_summary'): self.lbl_info_files_summary.config(text=f"Archivos Configurados: {len(self.tree_files.get_children())}")

    def add_filtro(self):
        t, c, v = self.ent_r_tab.get(), self.ent_r_cam.get(), self.ent_r_val.get()
        if t and t != "ej: trsd, afac":
            val_c = c if c != "ej: Recurso, Agente" else ""; val_v = v if v != "ej: IXEG" else ""
            self.tree_filtros.insert("", "end", values=(t, val_c, val_v, self.cb_r_ver.get(), "🗑️"))
            self.ent_r_tab.delete(0, tk.END); self.add_placeholder(self.ent_r_tab, "ej: trsd, afac")
            self.ent_r_cam.delete(0, tk.END); self.add_placeholder(self.ent_r_cam, "ej: Recurso, Agente")
            self.ent_r_val.delete(0, tk.END); self.add_placeholder(self.ent_r_val, "ej: IXEG")
            self.update_filtro_count_ui()

    def actualizar_todas_versiones_filtro(self, event=None):
        nueva = self.cb_r_ver.get()
        if not nueva: return
        for item_id in self.tree_filtros.get_children():
            vals = list(self.tree_filtros.item(item_id, 'values'))
            if len(vals) >= 4: vals[3] = nueva; self.tree_filtros.item(item_id, values=vals)

    def del_filtro(self):
        for s in self.tree_filtros.selection(): self.tree_filtros.delete(s)
        self.update_filtro_count_ui()
    def update_filtro_count_ui(self):
        if hasattr(self, 'lbl_info_filtros_summary'): self.lbl_info_filtros_summary.config(text=f"Filtros Configurados: {len(self.tree_filtros.get_children())}")

    def get_config(self):
        return {
            'usuario': self.ent_user.get(), 'password': self.ent_pass.get(),
            'ruta_local': self.ent_ruta.get(),
            'fecha_ini': self.ent_ini.get(), 'fecha_fin': self.ent_fin.get(),
            'viz_fecha_ini': self.app_visualizador.ent_fecha_ini.get(),
            'viz_fecha_fin': self.app_visualizador.ent_fecha_fin.get(),
            'ruta_db_viz': self.app_visualizador.lbl_db.get(),
            'archivos_descarga': [{'nombre_base': str(self.tree_files.item(i)['values'][0]), 'ruta_remota': str(self.tree_files.item(i)['values'][1])} for i in self.tree_files.get_children()],
            'filtros_reporte': [{'tabla': str(self.tree_filtros.item(i)['values'][0]), 'campo': str(self.tree_filtros.item(i)['values'][1]), 'valor': str(self.tree_filtros.item(i)['values'][2]), 'version': str(self.tree_filtros.item(i)['values'][3])} for i in self.tree_filtros.get_children()]
        }

    def guardar_config(self):
        try:
            with open(ARCHIVO_CONFIG, 'w') as f: json.dump(self.get_config(), f, indent=4)
            print("✅ Configuración guardada.")
            self.actualizar_dashboard()
        except Exception as e: print(f"❌ Error guardando: {e}")

    def crear_metric_card(self, parent, icon, value, label, color="primary"):
        # Dashboard Cards modernizadas
        card = ttk.Frame(parent, padding=10)
        
        # Frame interno con borde y color de fondo leve
        inner = ttk.LabelFrame(card, text=label, style=f"{color}.TLabelframe", padding=10)
        inner.pack(fill="both", expand=True)

        tb.Label(inner, text=icon, font=("Segoe UI", 20)).pack(side="left", padx=5)
        tb.Label(inner, text=str(value), font=("Segoe UI", 22, "bold"), bootstyle=color).pack(side="right", padx=10)
        
        return card

    def actualizar_dashboard(self):
        for w in self.frame_dashboard.winfo_children(): w.destroy()
        ruta = self.ent_ruta.get(); db_path = os.path.join(ruta, NOMBRE_DB_FILE)
        n_files = len(self.tree_files.get_children()) if hasattr(self, 'tree_files') else 0
        n_filters = len(self.tree_filtros.get_children()) if hasattr(self, 'tree_filtros') else 0
        db_exists = os.path.exists(db_path)
        db_size = f"{os.path.getsize(db_path)/(1024*1024):.2f} MB" if db_exists else "0 MB"
        
        grid_container = tb.Frame(self.frame_dashboard)
        grid_container.pack(fill="both", expand=True, padx=20)
        for i in range(3): grid_container.columnconfigure(i, weight=1, uniform="metric")
        
        self.crear_metric_card(grid_container, "💾", db_size, "Base de Datos", "info").grid(row=0, column=0, padx=10, sticky="nsew")
        self.crear_metric_card(grid_container, "📥", n_files, "Archivos", "success").grid(row=0, column=1, padx=10, sticky="nsew")
        self.crear_metric_card(grid_container, "📋", n_filters, "Filtros", "warning").grid(row=0, column=2, padx=10, sticky="nsew")

    def cargar_config(self):
        if os.path.exists(ARCHIVO_CONFIG):
            try:
                with open(ARCHIVO_CONFIG, 'r') as f: return json.load(f)
            except: pass
        return {}

    def reset_process(self):
        if not self.stop_event.is_set(): self.stop_event.set(); log.warning("🛑 Deteniendo procesos...")
        else: log.info("ℹ️ Ya se está deteniendo...")

    def run_descarga(self):
        if not self.validar_config(): return
        self.stop_event.clear(); self.toggle_controls('disabled')
        threading.Thread(target=self._exec_descarga, args=(self.get_config(),)).start()
    
    def _exec_descarga(self, cfg):
        try:
            proceso_descarga(cfg, stop_event=self.stop_event)
            if self.stop_event.is_set(): return
            necesita_fix = proceso_base_datos(cfg, stop_event=self.stop_event)
            if self.stop_event.is_set(): return
            if necesita_fix:
                log.warning("⚠️ Reparando corruptos..."); time.sleep(1)
                proceso_descarga(cfg, es_reintento=True, stop_event=self.stop_event)
                proceso_base_datos(cfg, es_reintento=True, stop_event=self.stop_event)
            log.info("🏁 FINALIZADO." if not self.stop_event.is_set() else "🏁 DETENIDO.")
        except Exception as e: log.error(f"❌ Error crítico: {e}")
        finally: self.root.after(0, lambda: [self.toggle_controls('normal'), self.actualizar_dashboard()])

    def run_reporte(self):
        if not self.validar_config(): return
        self.stop_event.clear(); self.toggle_controls('disabled')
        threading.Thread(target=self._exec_reporte, args=(self.get_config(),)).start()

    def _exec_reporte(self, cfg):
        try: generar_reporte_logica(cfg, stop_event=self.stop_event)
        except Exception as e: log.error(f"❌ Error reporte: {e}")
        finally: self.root.after(0, lambda: [self.toggle_controls('normal'), self.actualizar_dashboard()])

if __name__ == "__main__":
    # INICIALIZACIÓN BOOTSTRAP (Magic)
    # Temas recomendados: flatly, cosmo, litera, minty, lumen, sandstone, yeti
    root = tb.Window(themename="minty")
    
    # Ajustes globales de estilo
    style = tb.Style()
    style.configure('.', font=('Segoe UI', 10))
    style.configure('Treeview', rowheight=30)
    
    app = AplicacionXM(root)
    root.mainloop()
