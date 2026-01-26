# =============================================================================
#  ROBOT XM - SUITE INTEGRADA (v14.1 - MODERNIZED GUI)
#  Funcionalidades:
#  1. Descarga FTP Automática (Optimized Buffer).
#  2. Base de Datos SQLite (Pandas Bulk Insert).
#  3. Reportes Excel (SQL-side filtering).
#  4. VISUALIZADOR AVANZADO (ttkbootstrap).
# =============================================================================

import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.widgets import ToastNotification
# ScrolledText location varies by version
try:
    from ttkbootstrap.widgets.scrolled import ScrolledText
except ImportError:
    try:
        from ttkbootstrap.scrolled import ScrolledText
    except ImportError:
        from tkinter.scrolledtext import ScrolledText
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
ICON_WINDOW_FILENAME = "Enerconsult.png"

# Colores para gráficos (Mantenemos mapeo para matplotlib)
COLORES_GRAFICO = {
    "Verde Corporativo": "#6E9D2F",
    "Azul Corporativo": "#0088C2",
    "Rojo Intenso": "#e74c3c",
    "Naranja": "#f39c12",
    "Morado": "#9b59b6",
    "Gris Oscuro": "#3E5770",
    "Negro": "#000000",
    "Verde Menta": "#78C2AD",
    "Salmón": "#F3969A",
    "Verde Éxito": "#56CC9D",
    "Cian": "#6CC3D5",
    "Amarillo": "#FFCE67",
    "Naranja Intenso": "#FF7851"
}

import logging
import logging.handlers

# --- CONFIGURACIÓN DE LOGGING ---
def setup_logging():
    logger = logging.getLogger("RobotXM")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
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
DEFAULT_WORKERS = 3
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
#  GUI CLASSES (CustomDropdown, Helper Dialogs)
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

        self.entry = ttk.Entry(master, width=width, textvariable=self.textvariable)
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

        self.dropdown = ttk.Toplevel(self.master)
        self.dropdown.wm_overrideredirect(True)
        self.dropdown.attributes("-topmost", True)

        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        w_pixels = max(self.entry.winfo_width(), 150)
        self.dropdown.geometry(f"{w_pixels}x{self.dropdown_height}+{x}+{y}")

        frame_list = ttk.Frame(self.dropdown)
        frame_list.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(frame_list, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        chars_w = int(w_pixels / 7)
        # Listbox nativo de tk (ttk no tiene), estilizado manualmente si es posible, 
        # pero mantenemos defaults para compatibilidad simple.
        self.listbox = tk.Listbox(frame_list, width=chars_w, height=8, yscrollcommand=scrollbar.set,
                                  exportselection=False, font=("Segoe UI", 10), borderwidth=0)
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
        self.tooltip = ttk.Toplevel(self.master)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.attributes("-topmost", True)
        self.tooltip.geometry(f"+{x}+{y}")
        label = ttk.Label(self.tooltip, text=text, relief="solid", borderwidth=1, padding=5, bootstyle="info")
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


import calendar
from datetime import date, timedelta

class CalendarDialog(ttk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.title("Seleccionar Fecha")
        self.grab_set()
        
        try: self.attributes("-topmost", True)
        except: pass
        self.resizable(False, False)
        
        # Configurar icono
        try:
            ruta_icono = os.path.join(os.path.dirname(os.path.abspath(__file__)), ICON_WINDOW_FILENAME)
            if os.path.exists(ruta_icono):
                img_icon = tk.PhotoImage(file=ruta_icono)
                self.iconphoto(False, img_icon)
        except: pass

        self.current_date = date.today()
        self.year = self.current_date.year
        self.month = self.current_date.month
        
        self.setup_ui()
        self.build_calendar()
        
        # Centrar respecto al mouse o ventana con limites funcionales
        try:
            self.update_idletasks()
            req_w = self.winfo_reqwidth()
            req_h = self.winfo_reqheight()
            
            x = parent.winfo_pointerx()
            y = parent.winfo_pointery()
            
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            
            # Ajuste de posición mouse
            x += 10
            y += 10
            
            # Verificar limites para que no se salga
            if x + req_w > screen_w:
                x = screen_w - req_w - 20
            if y + req_h > screen_h:
                y = screen_h - req_h - 40
                
            if x < 0: x = 0
            if y < 0: y = 0
            
            self.geometry(f"+{int(x)}+{int(y)}")
        except:
            self.position_center()

    def setup_ui(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)

        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        
        btn_prev = ttk.Button(header_frame, text="<", command=self.prev_month, bootstyle="outline")
        btn_prev.pack(side="left")
        
        self.lbl_month_year = ttk.Label(header_frame, text="", font=("Segoe UI", 10, "bold"), anchor="center")
        self.lbl_month_year.pack(side="left", expand=True, fill="x")
        
        btn_next = ttk.Button(header_frame, text=">", command=self.next_month, bootstyle="outline")
        btn_next.pack(side="right")
        
        days_frame = ttk.Frame(main_frame)
        days_frame.pack()
        days_es = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]
        for i, d in enumerate(days_es):
            ttk.Label(days_frame, text=d, font=("Segoe UI", 8, "bold"), width=4, anchor="center").grid(row=0, column=i)
            
        self.calendar_frame = ttk.Frame(main_frame)
        self.calendar_frame.pack(pady=(5, 0))

    def build_calendar(self):
        for widget in self.calendar_frame.winfo_children(): widget.destroy()
        
        meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        self.lbl_month_year.config(text=f"{meses[self.month]} {self.year}")
        
        cal = calendar.monthcalendar(self.year, self.month)
        
        for r, week in enumerate(cal):
            for c, day in enumerate(week):
                if day == 0: continue
                
                style_btn = "light"
                if day == date.today().day and self.month == date.today().month and self.year == date.today().year:
                    style_btn = "primary" # Highlight today
                
                btn = ttk.Button(self.calendar_frame, text=str(day), width=3, bootstyle=style_btn,
                                command=lambda d=day: self.select_date(d))
                btn.grid(row=r, column=c, padx=1, pady=1)

    def prev_month(self):
        self.month -= 1
        if self.month < 1: self.month = 12; self.year -= 1
        self.build_calendar()

    def next_month(self):
        self.month += 1
        if self.month > 12: self.month = 1; self.year += 1
        self.build_calendar()

    def select_date(self, day):
        selected = date(self.year, self.month, day)
        self.callback(selected.strftime("%Y-%m-%d"))
        self.destroy()

# Reemplazamos Card manual con LabelFrame de bootstrap
class Card(ttk.Labelframe):
    def __init__(self, parent, title=None, icon=None, *args, **kwargs):
        text = ""
        if icon: text += f"{icon} "
        if title: text += title
        super().__init__(parent, text=text, padding=15, bootstyle="info", *args, **kwargs)
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True)

    def get_body(self): return self.body

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
        conn.execute("PRAGMA cache_size = -64000") 
        conn.execute("PRAGMA temp_store = MEMORY")
    except: pass
    return conn

def bulk_insert_fast(conn, ruta_csv, tabla, meta_cols, chunksize=50000):
    tabla = safe_identifier(tabla)
    total_rows = 0
    try:
        if str(ruta_csv).lower().endswith('.txt'):
            custom_names = ['descripcion'] + [str(i) for i in range(1, 25)]
            df_iter = pd.read_csv(ruta_csv, sep=',', header=None, names=custom_names,
                                  encoding='latin-1', chunksize=chunksize, dtype=str, 
                                  engine='c', skipinitialspace=True)
        else:
            df_iter = pd.read_csv(ruta_csv, sep=';', encoding='latin-1', 
                                  chunksize=chunksize, dtype=str, engine='c', 
                                  skipinitialspace=True)
    except Exception as e:
        log.error(f"Error leyendo CSV {ruta_csv}: {e}")
        raise e

    first_chunk = True
    INSERT_CHUNKSIZE = 500
    
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
            df_chunk.to_sql(tabla, conn, if_exists='append', index=False, 
                          chunksize=INSERT_CHUNKSIZE, method='multi')
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
                        if archivo: cache.add((str(archivo).lower(), str(anio)))
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

        if (nombre_archivo.lower(), anio_carpeta) in archivos_procesados_cache: continue
        es_valido = False
        carpeta_padre = os.path.basename(os.path.dirname(ruta_completa))
        
        if nombre_tabla in ARCHIVOS_MENSUALES:
            if f"{anio_carpeta}-{fecha_identificador}" in meses_permitidos: es_valido = True
        else:
            if fecha_identificador in dias_permitidos:
                 if carpeta_padre in meses_permitidos:
                     es_valido = True
                 elif carpeta_padre == anio_carpeta and len(fecha_identificador) == 4:
                     mes = fecha_identificador[:2]
                     if f"{anio_carpeta}-{mes}" in meses_permitidos: es_valido = True
                         
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
                    df = df.copy() 

                    cols_no_num = ['index', 'anio', 'mes_dia', 'version_dato', 'origen_archivo', 'fecha_carga']
                    for col in df.columns:
                        if col not in cols_no_num and df[col].dtype == 'object':
                            try:
                                nums = pd.to_numeric(df[col], errors='coerce')
                                if nums.notna().any():
                                    df[col] = nums.fillna(df[col])
                            except: pass
                    
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
                        df['max_peso'] = df.groupby('Fecha')['peso'].transform('max')
                        df = df[df['peso'] == df['max_peso']]
                        df = df.drop(columns=['peso', 'max_peso'])

                    cols_borrar = ['anio', 'mes_dia', 'origen_archivo', 'fecha_carga', 'index']
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
#  MÓDULO 4: VISUALIZADOR (INTEGRADO EN PESTAÑA)
# =============================================================================

class ModuloVisualizador:
    def __init__(self, parent_frame, config):
        self.frame_main = parent_frame 
        self.ruta_db = config.get('ruta_db_viz', "BaseDatosXM.db")
        self.datos_actuales = None 
        
        self.var_tabla = tk.StringVar(); self.var_version = tk.StringVar()
        self.var_campo_filtro1 = tk.StringVar(); self.var_valor_filtro1 = tk.StringVar()
        self.var_campo_filtro2 = tk.StringVar(); self.var_valor_filtro2 = tk.StringVar()
        self.var_campo_valor = tk.StringVar(); self.var_agregacion = tk.StringVar(value="Promedio")
        self.var_tipo_grafico = tk.StringVar(value="Línea")
        self.var_color_grafico = tk.StringVar(value="Verde Menta")
        self.var_fecha_ini = tk.StringVar(); self.var_fecha_fin = tk.StringVar()
        self.var_temporalidad = tk.StringVar(value="Diaria")

        frame_top = ttk.Frame(self.frame_main, padding=5)
        frame_top.pack(fill="x")
        ttk.Label(frame_top, text="BD Gráfica:").pack(side="left")
        self.lbl_db = ttk.Entry(frame_top, width=60)
        self.lbl_db.pack(side="left", padx=5)
        self.lbl_db.insert(0, os.path.abspath(self.ruta_db))
        ttk.Button(frame_top, text="📂", command=self.seleccionar_db, bootstyle="secondary-outline").pack(side="left")
        ttk.Button(frame_top, text="🔄 Leer Tablas", command=self.cargar_tablas, bootstyle="primary").pack(side="left", padx=5)

        frame_controls = ttk.Frame(self.frame_main)
        frame_controls.pack(fill="x", padx=5, pady=2)

        col1 = ttk.Labelframe(frame_controls, text="1. Fuente de Datos", padding=10)
        col1.pack(side="left", fill="both", expand=True, padx=5)
        
        ttk.Label(col1, text="Archivo:").grid(row=0, column=0, sticky="w", pady=2, padx=5)
        self.cb_tabla = ttk.Combobox(col1, textvariable=self.var_tabla, state="readonly", width=18)
        self.cb_tabla.grid(row=0, column=1, padx=2); self.cb_tabla.bind("<<ComboboxSelected>>", self.al_seleccionar_tabla)

        ttk.Label(col1, text="Versión:").grid(row=1, column=0, sticky="w", pady=1, padx=5)
        self.cb_version = ttk.Combobox(col1, textvariable=self.var_version, state="readonly", width=18)
        self.cb_version.grid(row=1, column=1, padx=2)

        ttk.Label(col1, text="Filtro 1:").grid(row=2, column=0, sticky="w", pady=1, padx=5)
        self.cb_campo_filtro1 = CustomDropdownWithTooltip(col1, textvariable=self.var_campo_filtro1, width=20, command=self.al_seleccionar_campo_filtro1)
        self.cb_campo_filtro1.entry.grid(row=2, column=1, padx=2, pady=1)
        self.cb_valor_filtro1 = CustomDropdownWithTooltip(col1, textvariable=self.var_valor_filtro1, width=20)
        self.cb_valor_filtro1.entry.grid(row=3, column=1, padx=2, pady=1)

        ttk.Label(col1, text="Filtro 2 (opc):").grid(row=4, column=0, sticky="w", pady=1, padx=5)
        self.cb_campo_filtro2 = CustomDropdownWithTooltip(col1, textvariable=self.var_campo_filtro2, width=20, command=self.al_seleccionar_campo_filtro2)
        self.cb_campo_filtro2.entry.grid(row=4, column=1, padx=2)
        self.cb_valor_filtro2 = CustomDropdownWithTooltip(col1, textvariable=self.var_valor_filtro2, width=20)
        self.cb_valor_filtro2.entry.grid(row=5, column=1, padx=2, pady=2)

        col2 = ttk.Labelframe(frame_controls, text="2. Configuración", padding=10)
        col2.pack(side="left", fill="both", expand=True, padx=5)

        ttk.Label(col2, text="Temporalidad:").grid(row=0, column=0, sticky="w", pady=2, padx=5)
        self.cb_temporalidad = ttk.Combobox(col2, textvariable=self.var_temporalidad, state="readonly", width=18)
        self.cb_temporalidad['values'] = ["Diaria", "Mensual", "Horaria (24h)"]
        self.cb_temporalidad.grid(row=0, column=1, padx=2)
        self.cb_temporalidad.bind("<<ComboboxSelected>>", self.toggle_campo_valor)

        self.lbl_valor = ttk.Label(col2, text="Variable:")
        self.lbl_valor.grid(row=1, column=0, sticky="w", pady=1, padx=5)
        self.cb_campo_valor = CustomDropdownWithTooltip(col2, textvariable=self.var_campo_valor, width=20)
        self.cb_campo_valor.entry.grid(row=1, column=1, padx=2)

        ttk.Label(col2, text="Operación:").grid(row=2, column=0, sticky="w", pady=1, padx=5)
        self.cb_agregacion = ttk.Combobox(col2, textvariable=self.var_agregacion, state="readonly", width=18)
        self.cb_agregacion['values'] = ["Valor", "Promedio", "Suma", "Máximo", "Mínimo"]; self.cb_agregacion.current(0)
        self.cb_agregacion.grid(row=2, column=1, padx=2)

        ttk.Label(col2, text="Tipo:").grid(row=3, column=0, sticky="w", pady=1, padx=5)
        self.cb_tipo = ttk.Combobox(col2, textvariable=self.var_tipo_grafico, state="readonly", width=18)
        self.cb_tipo['values'] = ["Línea", "Barras", "Área", "Dispersión"]; self.cb_tipo.current(0)
        self.cb_tipo.grid(row=3, column=1, padx=2)

        ttk.Label(col2, text="Color:").grid(row=4, column=0, sticky="w", pady=1, padx=5)
        self.cb_color = ttk.Combobox(col2, textvariable=self.var_color_grafico, state="readonly", width=18)
        self.cb_color['values'] = list(COLORES_GRAFICO.keys()); self.cb_color.current(0)
        self.cb_color.grid(row=4, column=1, padx=2)

        col3 = ttk.Labelframe(frame_controls, text="3. Periodo y Acción", padding=10)
        col3.pack(side="left", fill="both", expand=True, padx=5)

        self.var_dia_unico = tk.BooleanVar(value=False)

        def _sync_fechas(*args):
             if self.var_dia_unico.get():
                 self.var_fecha_fin.set(self.var_fecha_ini.get())

        self.var_fecha_ini.trace_add("write", _sync_fechas)

        def toggle_dia_unico():
            if self.var_dia_unico.get():
                _sync_fechas()
                self.frame_nav_fin.grid_remove() 
                self.lbl_fin.grid_remove()
            else:
                self.frame_nav_fin.grid()
                self.lbl_fin.grid()
                
        def mover_fecha(var_fecha, dias):
            try:
                dt = datetime.strptime(var_fecha.get(), "%Y-%m-%d")
                curr = dt + timedelta(days=dias)
                nue_fecha = curr.strftime("%Y-%m-%d")
                var_fecha.set(nue_fecha) 
                self.generar_grafico()
            except: pass

        def crear_navegador_fecha(parent, var_fecha, row_idx):
            f_nav = ttk.Frame(parent)
            f_nav.grid(row=row_idx, column=1, padx=2, sticky="w")
            
            ttk.Button(f_nav, text="<", width=2, bootstyle="outline", 
                                 command=lambda: mover_fecha(var_fecha, -1)).pack(side="left", padx=1)
            
            e = ttk.Entry(f_nav, textvariable=var_fecha, width=12)
            e.pack(side="left", padx=2)
            e.bind("<FocusOut>", self.actualizar_versiones)
            
            ttk.Button(f_nav, text=">", width=2, bootstyle="outline", 
                                 command=lambda: mover_fecha(var_fecha, 1)).pack(side="left", padx=1)
            
            ttk.Button(f_nav, text="📅", bootstyle="link",
                      command=lambda: CalendarDialog(self.frame_main, lambda d: [var_fecha.set(d), self.generar_grafico()])).pack(side="left", padx=2)
            return e, f_nav

        ttk.Label(col3, text="Inicio:").grid(row=0, column=0, sticky="w", pady=2, padx=5)
        self.ent_fecha_ini, self.frame_nav_ini = crear_navegador_fecha(col3, self.var_fecha_ini, 0)
        self.var_fecha_ini.set(config.get('viz_fecha_ini', '2025-01-01'))

        self.lbl_fin = ttk.Label(col3, text="Fin:")
        self.lbl_fin.grid(row=1, column=0, sticky="w", pady=1, padx=5)
        self.ent_fecha_fin, self.frame_nav_fin = crear_navegador_fecha(col3, self.var_fecha_fin, 1)
        self.var_fecha_fin.set(config.get('viz_fecha_fin', datetime.today().strftime('%Y-%m-%d')))
        
        fr_toggle = ttk.Frame(col3)
        fr_toggle.grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        
        ttk.Checkbutton(fr_toggle, text="Solo un día", variable=self.var_dia_unico, command=toggle_dia_unico, bootstyle="round-toggle").pack(side="left")

        ttk.Button(col3, text="📊 GRAFICAR", command=self.generar_grafico, bootstyle="primary").grid(row=3, column=0, pady=8, sticky="ew", padx=2)
        ttk.Button(col3, text="📥 EXCEL", command=self.exportar_datos_excel, bootstyle="success").grid(row=3, column=1, pady=8, sticky="ew", padx=2)

        self.frame_stats = ttk.Frame(self.frame_main)
        self.frame_stats.pack(fill="x", padx=10, pady=1)
        self.lbl_stat_prom = ttk.Label(self.frame_stats, text="Promedio: --", font=('Arial', 8, 'bold'))
        self.lbl_stat_prom.pack(side="left", padx=8)
        self.lbl_stat_max = ttk.Label(self.frame_stats, text="Max: --", font=('Arial', 8, 'bold'), bootstyle="success")
        self.lbl_stat_max.pack(side="left", padx=8)
        self.lbl_stat_min = ttk.Label(self.frame_stats, text="Min: --", font=('Arial', 8, 'bold'), bootstyle="danger")
        self.lbl_stat_min.pack(side="left", padx=8)
        self.lbl_stat_sum = ttk.Label(self.frame_stats, text="Suma: --", font=('Arial', 8, 'bold'), bootstyle="info")
        self.lbl_stat_sum.pack(side="left", padx=8)

        self.frame_plot = ttk.Frame(self.frame_main)
        self.frame_plot.config(height=400)
        self.frame_plot.pack_propagate(False)
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
        if not tabla or tabla == "Seleccione Archivo...": return
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
                query = f"SELECT DISTINCT version_dato FROM {tabla} WHERE (CAST(anio AS TEXT) || printf('%02d', CAST(mes_dia AS INTEGER))) BETWEEN ? AND ? ORDER BY version_dato"
                params = (f_ini_str[:6], f_fin_str[:6])
            else:
                query = f"SELECT DISTINCT version_dato FROM {tabla} WHERE (CAST(anio AS TEXT) || printf('%04d', CAST(mes_dia AS INTEGER))) BETWEEN ? AND ? ORDER BY version_dato"
                params = (f_ini_str, f_fin_str)

            versiones_df = pd.read_sql_query(query, conn, params=params)
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
        if not tabla or not campo or tabla == "Seleccione Archivo...": return
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
        tabla = self.var_tabla.get(); version = self.var_version.get()
        campo1 = self.var_campo_filtro1.get(); valor1 = self.var_valor_filtro1.get()
        campo2 = self.var_campo_filtro2.get(); valor2 = self.var_valor_filtro2.get()
        operacion = self.var_agregacion.get(); temporalidad = self.var_temporalidad.get()
        f_ini_str = self.var_fecha_ini.get(); f_fin_str = self.var_fecha_fin.get()
        
        tipo_grafico = self.var_tipo_grafico.get()
        nombre_color = self.var_color_grafico.get()
        color_hex = COLORES_GRAFICO.get(nombre_color, "#27ae60")

        if not tabla or tabla == "Seleccione Archivo...": return

        try:
            conn = self.conectar()
            where = ["1=1"]
            params = []
            
            if campo1 and valor1:
                where.append(f"CAST({campo1} AS TEXT) = ?")
                params.append(str(valor1))
            if campo2 and valor2:
                where.append(f"CAST({campo2} AS TEXT) = ?")
                params.append(str(valor2))
            
            if version and version not in ["N/A", "Última"]:
                where.append("version_dato = ?")
                params.append(str(version))
            
            es_mensual_graf = any(tabla.lower().startswith(x.lower()) for x in ARCHIVOS_MENSUALES)
            if es_mensual_graf:
                sql_date = f"CAST(anio AS TEXT) || '-' || printf('%02d', CAST(mes_dia AS INTEGER)) || '-01'"
            else:
                col_md = "printf('%04d', CAST(mes_dia AS INTEGER))"
                sql_date = f"CAST(anio AS TEXT) || '-' || substr({col_md}, 1, 2) || '-' || substr({col_md}, 3, 2)"
            
            where.append(f"date({sql_date}) BETWEEN date(?) AND date(?)")
            params.append(f_ini_str)
            params.append(f_fin_str)
            
            query = f"SELECT * FROM {tabla} WHERE {' AND '.join(where)}"
            
            df = pd.read_sql_query(query, conn, params=params); conn.close()
            if df.empty: messagebox.showinfo("Vacío", f"No hay datos para graficar."); return

            try:
                df['anio'] = pd.to_numeric(df['anio'], errors='coerce').fillna(0).astype(int)
                df['mes_dia'] = pd.to_numeric(df['mes_dia'], errors='coerce').fillna(0).astype(int)
                
                if es_mensual_graf:
                    df['day'] = 1
                    df['month'] = df['mes_dia']
                    df['year'] = df['anio']
                    df = df[(df['month'] >= 1) & (df['month'] <= 12)]
                    df['Fecha'] = pd.to_datetime(df[['year', 'month', 'day']], errors='coerce')
                else:
                    s_mes_dia = df['mes_dia'].astype(str).str.zfill(4)
                    s_anio = df['anio'].astype(str)
                    s_fecha = s_anio + "-" + s_mes_dia.str.slice(0, 2) + "-" + s_mes_dia.str.slice(2, 4)
                    df['Fecha'] = pd.to_datetime(s_fecha, format='%Y-%m-%d', errors='coerce')

                df = df.dropna(subset=['Fecha'])
            except Exception as e:
                print(f"Error vectorizando fechas: {e}")
                return

            if version == "Última":
                try:
                    s = df['version_dato'].astype(str).str.lower().str.strip().str.replace('.', '', regex=False)
                    df['peso'] = 0.0
                    nums = s.str.extract(r'tx(\d+)', expand=False).astype(float).fillna(0)
                    df['peso'] = nums * 100.0
                    df.loc[s == 'txr', 'peso'] = 250.0
                    df.loc[s == 'txf', 'peso'] = 290.0
                    df.loc[s == 'txa', 'peso'] = 290.0
                    df['max_peso'] = df.groupby('Fecha')['peso'].transform('max')
                    df = df[df['peso'] == df['max_peso']].copy()
                    df.drop(columns=['peso', 'max_peso'], inplace=True, errors='ignore')
                except Exception as e:
                    df['peso'] = df['version_dato'].apply(calcular_peso_version)
                    df['max_peso'] = df.groupby('Fecha')['peso'].transform('max')
                    df = df[df['peso'] == df['max_peso']].copy()
                    df.drop(columns=['peso', 'max_peso'], inplace=True, errors='ignore')

            serie_graficar = None
            if temporalidad == "Horaria (24h)":
                cols_range_0 = [str(i) for i in range(24)]
                cols_range_1 = [str(i) for i in range(1, 25)]
                
                has_24 = '24' in df.columns
                has_0 = '0' in df.columns
                
                cols_horas = []
                es_base_0 = True
                
                if has_24:
                    cols_horas = [c for c in df.columns if c in cols_range_1]
                    es_base_0 = False
                elif has_0:
                    cols_horas = [c for c in df.columns if c in cols_range_0]
                    es_base_0 = True
                else:
                    matches_0 = [c for c in df.columns if c in cols_range_0]
                    matches_1 = [c for c in df.columns if c in cols_range_1]
                    if len(matches_1) > len(matches_0):
                        cols_horas = matches_1; es_base_0 = False
                    else:
                        cols_horas = matches_0; es_base_0 = True
                
                if not cols_horas: cols_horas = [c for c in df.columns if 'hora' in c.lower()]
                for c in cols_horas: df[c] = pd.to_numeric(df[c], errors='coerce')
                
                if operacion == "Valor":
                    df_melted = df.melt(id_vars=['Fecha'], value_vars=cols_horas, var_name='HoraStr', value_name='Res')
                    df_melted['Hora'] = pd.to_numeric(
                        df_melted['HoraStr'].astype(str).str.extract(r'(\d+)')[0], 
                        errors='coerce'
                    ).fillna(0).astype(int)
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
                    excl = {'anio', 'mes_dia', 'version_dato', 'fecha'}
                    for c in df.columns:
                        if c.lower() not in excl and pd.to_numeric(df[c], errors='coerce').notna().any():
                            col_val = c; self.var_campo_valor.set(col_val); break
                    if not col_val: messagebox.showwarning("Info", "Selecciona variable."); return
                
                df[col_val] = pd.to_numeric(df[col_val], errors='coerce')
                if temporalidad == "Mensual": df['Fecha'] = df['Fecha'].apply(lambda x: x.replace(day=1))
                
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
                
            if operacion != "Valor":
                titulo_grafico += f" ({operacion})"
            self.titulo_actual = titulo_grafico.replace("\n", " ")
            self.dibujar_plot(self.datos_actuales, titulo_grafico, tipo_grafico, color_hex, temporalidad)

        except Exception as e: messagebox.showerror("Error", f"{e}")

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
        
        # Ajustamos colores de fondo a transparente para que tome el tema
        fig = Figure(figsize=(8, 4.1), dpi=100) # Sin facecolor hardcoded
        ax = fig.add_subplot(111)
        
        # Tema claro por defecto en matplotlib, intentar ajustar
        ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
        ax.grid(True, axis='y', linestyle=':', linewidth=1.5, alpha=0.5)
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

        ax.set_title(titulo, fontsize=12, weight='bold', pad=15)
        
        tooltip_fmt = "%Y-%m-%d"
        
        if temporalidad == "Mensual":
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.MonthLocator())
            tooltip_fmt = "%Y-%m"
        elif temporalidad == "Horaria (24h)":
            has_time = False
            try:
                times = serie.index.time
                has_time = any(t.hour != 0 or t.minute != 0 for t in times)
            except: pass

            if len(serie) > 0 and (serie.index[-1] - serie.index[0]).days < 2 and has_time:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:00'))
                tooltip_fmt = "%H:00"
            elif has_time:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %Hh'))
                tooltip_fmt = "%Y-%m-%d %H:%M"
            else:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                fig.autofmt_xdate(rotation=45)
                tooltip_fmt = "%Y-%m-%d"
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            if len(serie) > 30: fig.autofmt_xdate(rotation=45)
            tooltip_fmt = "%Y-%m-%d"
        
        ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}')) 

        annot = ax.annotate("", xy=(0,0), xytext=(10,10),textcoords="offset points",
                            bbox=dict(boxstyle="round4,pad=0.5", fc="#ffffff", ec="#bdc3c7", alpha=0.95, lw=1),
                            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.1", color="#7f8c8d"))
        annot.set_visible(False)

        def update_annot(ind):
            x, y = line_ghost.get_data()
            idx = ind["ind"][0]
            val_x = x[idx]; annot.xy = (val_x, y[idx])
            fecha_dt = None
            if idx < len(serie.index):
                fecha_dt = serie.index[idx]
            else:
                 try: fecha_dt = mdates.num2date(val_x)
                 except: pass

            f_str = "?"
            if fecha_dt is not None:
                try: f_str = fecha_dt.strftime(tooltip_fmt)
                except: pass
                
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
        try: fig.tight_layout(rect=[0, 0.05, 1, 0.95], pad=1.5)
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
        self.root.title("Suite XM Inteligente - Enerconsult (v14.1)")
        screen_width = self.root.winfo_screenwidth(); screen_height = self.root.winfo_screenheight()
        w_app = int(screen_width * 0.85); h_app = int(screen_height * 0.85)
        x_pos = (screen_width - w_app) // 2; y_pos = (screen_height - h_app) // 2
        self.root.geometry(f"{w_app}x{h_app}+{x_pos}+{y_pos}")

        # Configurar icono de ventana
        try:
            ruta_icono = os.path.join(os.path.dirname(os.path.abspath(__file__)), ICON_WINDOW_FILENAME)
            if os.path.exists(ruta_icono):
                img_icon = tk.PhotoImage(file=ruta_icono)
                self.root.iconphoto(False, img_icon)
        except Exception: pass
        
        self.config = self.cargar_config()
        self.stop_event = threading.Event()
        
        self.construir_encabezado_logo()

        console_container = ttk.Frame(root)
        console_container.pack(side="bottom", fill="x", expand=False, padx=10, pady=5)
        
        # Log console estilizado
        self.txt_console = ScrolledText(console_container, height=6, state='disabled', bootstyle="success-round", font=('Consolas', 10))
        self.txt_console.pack(fill="x", expand=False, padx=0, pady=0)
        
        # Redirigir stdout
        sys.stdout = PrintRedirector(self.txt_console.text) # ScrolledText tiene .text como widget interno

        # Notebook estilizado
        tab_control = ttk.Notebook(root, bootstyle="primary")
        self.tab_general = ttk.Frame(tab_control, padding=10)
        self.tab_archivos = ttk.Frame(tab_control, padding=10)
        self.tab_filtros = ttk.Frame(tab_control, padding=10)
        self.tab_visualizador = ttk.Frame(tab_control, padding=10)
        
        tab_control.add(self.tab_general, text='🔧 Configuración')
        tab_control.add(self.tab_archivos, text='📥 Descargas')
        tab_control.add(self.tab_filtros, text='📋 Filtros Reporte')
        tab_control.add(self.tab_visualizador, text='📈 Visualizador')
        tab_control.pack(expand=True, fill="both", padx=10, pady=5)

        self.crear_tab_general(); self.crear_tab_archivos(); self.crear_tab_filtros()
        self.app_visualizador = ModuloVisualizador(self.tab_visualizador, self.config)
        self.actualizar_dashboard()
        self.update_logger_output()

    def update_logger_output(self):
        logger = logging.getLogger("RobotXM")
        # Remover handlers de stream viejos
        for h in logger.handlers[:]:
            if type(h) is logging.StreamHandler: logger.removeHandler(h)
        # Re-agregar stdout (que ahora apunta a consola Tk)
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

    def construir_encabezado_logo(self):
        frame_header = ttk.Frame(self.root, padding=10, bootstyle="light")
        frame_header.pack(fill="x", side="top")
        
        # Contenedor para Logo + Titulo + Selector Tema
        frame_content = ttk.Frame(frame_header)
        frame_content.pack(fill="x")
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ruta_logo = os.path.join(script_dir, LOGO_FILENAME)
        
        if TIENE_PILLOW and os.path.exists(ruta_logo):
            try:
                pil_img = Image.open(ruta_logo)
                base_height = 40 
                w_percent = (base_height / float(pil_img.size[1]))
                w_size = int((float(pil_img.size[0]) * float(w_percent)))
                pil_img = pil_img.resize((w_size, base_height), RESAMPLE_LANCZOS)
                self.logo_img = ImageTk.PhotoImage(pil_img)
                lbl_logo = ttk.Label(frame_content, image=self.logo_img)
                lbl_logo.pack(side="left", padx=10)
            except: pass
        
        lbl_title = ttk.Label(frame_content, text="Suite Inteligente XM", font=("Segoe UI", 16, "bold"), bootstyle="primary")
        lbl_title.pack(side="left", padx=10)
        
        # Selector de Tema
        frame_theme = ttk.Frame(frame_content)
        frame_theme.pack(side="right")
        ttk.Label(frame_theme, text="Tema:").pack(side="left", padx=5)
        self.cb_theme = ttk.Combobox(frame_theme, values=self.root.style.theme_names(), state="readonly", width=10)
        self.cb_theme.set(self.root.style.theme.name)
        self.cb_theme.pack(side="left")
        self.cb_theme.bind("<<ComboboxSelected>>", self.cambiar_tema)

    def cambiar_tema(self, event):
        t = self.cb_theme.get()
        self.root.style.theme_use(t)

    def crear_tab_general(self):
        main_container = ttk.Frame(self.tab_general)
        main_container.pack(fill="both", expand=True, padx=20, pady=10)
        
        card_main = Card(main_container, title="Credenciales y Rutas", icon="⚙️")
        card_main.pack(fill="x", pady=(0, 10))
        c_content = card_main.get_body()
        c_content.columnconfigure(0, weight=1); c_content.columnconfigure(1, weight=1)

        ttk.Label(c_content, text="Usuario FTP").grid(row=0, column=0, sticky="w", pady=(2, 2), padx=(0, 10))
        self.ent_user = ttk.Entry(c_content)
        self.ent_user.grid(row=1, column=0, sticky="ew", padx=(0, 20), pady=(0, 10))
        self.ent_user.insert(0, self.config.get('usuario', ''))

        ttk.Label(c_content, text="Password FTP").grid(row=0, column=1, sticky="w", pady=(2, 2), padx=(0, 10))
        self.ent_pass = ttk.Entry(c_content, show="*")
        self.ent_pass.grid(row=1, column=1, sticky="ew", pady=(0, 10))
        self.ent_pass.insert(0, self.config.get('password', ''))

        ttk.Label(c_content, text="Ruta Local").grid(row=2, column=0, sticky="w", pady=(2, 2), padx=(0, 10))
        fr_ruta = ttk.Frame(c_content)
        fr_ruta.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 10)) 
        self.ent_ruta = ttk.Entry(fr_ruta)
        self.ent_ruta.pack(side="left", fill="x", expand=True)
        self.ent_ruta.insert(0, self.config.get('ruta_local', ''))
        self.btn_fold = ttk.Button(fr_ruta, text="📂", bootstyle="info-outline", command=self.seleccionar_carpeta)
        self.btn_fold.pack(side="left", padx=(5, 0))

        ttk.Separator(c_content, orient="horizontal").grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 10))
        
        ttk.Label(c_content, text="Fecha Inicio").grid(row=5, column=0, sticky="w", pady=(2, 2), padx=(0, 10))
        f_ini = ttk.Frame(c_content)
        f_ini.grid(row=6, column=0, sticky="ew", padx=(0, 20))
        self.ent_ini = ttk.Entry(f_ini)
        self.ent_ini.pack(side="left", fill="x", expand=True)
        ttk.Button(f_ini, text="📅", bootstyle="link",
                  command=lambda: CalendarDialog(self.root, lambda d: [self.ent_ini.delete(0, tk.END), self.ent_ini.insert(0, d)])).pack(side="left")
        self.ent_ini.insert(0, self.config.get('fecha_ini', '2025-01-01'))
        
        ttk.Label(c_content, text="Fecha Fin").grid(row=5, column=1, sticky="w", pady=(2, 2), padx=(0, 10))
        f_fin = ttk.Frame(c_content)
        f_fin.grid(row=6, column=1, sticky="ew")
        self.ent_fin = ttk.Entry(f_fin)
        self.ent_fin.pack(side="left", fill="x", expand=True)
        ttk.Button(f_fin, text="📅", bootstyle="link",
                  command=lambda: CalendarDialog(self.root, lambda d: [self.ent_fin.delete(0, tk.END), self.ent_fin.insert(0, d)])).pack(side="left")
        self.ent_fin.insert(0, self.config.get('fecha_fin', '2025-01-31'))

        row_actions = ttk.Frame(main_container)
        row_actions.pack(pady=(10, 10))
        
        self.btn_guardar = ttk.Button(row_actions, text=" GUARDAR CONFIG", bootstyle="success", command=self.guardar_config, width=20)
        self.btn_guardar.grid(row=0, column=0, padx=5)
        self.btn_descargar = ttk.Button(row_actions, text=" EJECUTAR DESCARGA", bootstyle="primary", command=self.run_descarga, width=20)
        self.btn_descargar.grid(row=0, column=1, padx=5)
        self.btn_reporte = ttk.Button(row_actions, text=" GENERAR REPORTE", bootstyle="info", command=self.run_reporte, width=20)
        self.btn_reporte.grid(row=0, column=2, padx=5)
        self.btn_reset = ttk.Button(row_actions, text=" DETENER", bootstyle="danger", command=self.reset_process)
        self.btn_reset.grid(row=0, column=3, padx=5)

        self.frame_dashboard = ttk.Frame(main_container)
        self.frame_dashboard.pack(fill="both", expand=True, pady=10)
        self.actualizar_dashboard()

    def crear_tab_archivos(self):
        main_container = ttk.Frame(self.tab_archivos)
        main_container.pack(fill="both", expand=True, padx=20, pady=10)

        card_input = Card(main_container, title="Agregar Archivo")
        card_input.pack(fill="x", pady=(0, 10))
        c1 = card_input.get_body()
        c1.columnconfigure(0, weight=1); c1.columnconfigure(1, weight=2); c1.columnconfigure(2, weight=0)

        ttk.Label(c1, text="Nombre Archivo (Base)").grid(row=0, column=0, sticky="w", pady=(0, 5), padx=5)
        self.ent_f_nom = ttk.Entry(c1); self.ent_f_nom.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 2))
        
        ttk.Label(c1, text="Ruta FTP").grid(row=0, column=1, sticky="w", pady=(0, 5), padx=5)
        self.ent_f_rut = ttk.Entry(c1); self.ent_f_rut.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 2))
        
        self.btn_add_file = ttk.Button(c1, text="✚", command=self.add_file, bootstyle="success")
        self.btn_add_file.grid(row=1, column=2, padx=5)

        card_list = Card(main_container, title="Archivos Configurados")
        card_list.pack(fill="both", expand=True, pady=(0, 10))
        c2 = card_list.get_body()
        
        self.tree_files = ttk.Treeview(c2, columns=("nombre", "ruta", "acciones"), show="headings", height=8, bootstyle="info")
        self.tree_files.heading("nombre", text="Nombre Archivo", anchor="w")
        self.tree_files.heading("ruta", text="Ruta FTP", anchor="w")
        self.tree_files.heading("acciones", text="Acciones", anchor="center") 
        self.tree_files.column("nombre", width=150); self.tree_files.column("ruta", width=400, stretch=True); self.tree_files.column("acciones", width=80, anchor="center")
        
        scrollbar = ttk.Scrollbar(c2, orient="vertical", command=self.tree_files.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree_files.configure(yscrollcommand=scrollbar.set)
        self.tree_files.pack(side="left", fill="both", expand=True)
        
        for idx, i in enumerate(self.config.get('archivos_descarga', [])):
            self.tree_files.insert("", "end", values=(i['nombre_base'], i['ruta_remota'], "🗑️"))

        self.tree_files.bind("<Button-1>", lambda e: self.del_file() if self.tree_files.identify_column(e.x) == "#3" else None)

    def crear_tab_filtros(self):
        main_container = ttk.Frame(self.tab_filtros)
        main_container.pack(fill="both", expand=True, padx=20, pady=10)

        fr_card_input = ttk.Frame(main_container)
        fr_card_input.pack(fill="x", pady=(0, 10))
        card_input = Card(fr_card_input, title="Nuevo Filtro"); card_input.pack(fill="both", expand=True)
        c1 = card_input.get_body()

        c1.columnconfigure(0, weight=1); c1.columnconfigure(1, weight=1); c1.columnconfigure(2, weight=1); c1.columnconfigure(3, weight=0, minsize=80); c1.columnconfigure(4, weight=0)

        ttk.Label(c1, text="Tabla").grid(row=0, column=0, sticky="w", pady=(0, 5), padx=5)
        self.ent_r_tab = ttk.Entry(c1); self.ent_r_tab.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 2))

        ttk.Label(c1, text="Campo").grid(row=0, column=1, sticky="w", pady=(0, 5), padx=5)
        self.ent_r_cam = ttk.Entry(c1); self.ent_r_cam.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 2))

        ttk.Label(c1, text="Valor").grid(row=0, column=2, sticky="w", pady=(0, 5), padx=5)
        self.ent_r_val = ttk.Entry(c1); self.ent_r_val.grid(row=1, column=2, sticky="ew", padx=5, pady=(0, 2))

        ttk.Label(c1, text="Versión").grid(row=0, column=3, sticky="w", pady=(0, 5), padx=5)
        self.cb_r_ver = ttk.Combobox(c1, values=["Última", "tx1", "tx2", "tx3", "txR", "txF"], state="readonly", width=10)
        self.cb_r_ver.set("Última"); self.cb_r_ver.grid(row=1, column=3, sticky="ew", padx=5, ipady=3)
        self.cb_r_ver.bind("<<ComboboxSelected>>", self.actualizar_todas_versiones_filtro)

        fr_btns = ttk.Frame(c1); fr_btns.grid(row=1, column=4, padx=5)
        
        ttk.Button(fr_btns, text="✚", bootstyle="success", width=4, command=self.add_filtro).pack(side="left", padx=2)
        ttk.Button(fr_btns, text="▲", bootstyle="secondary-outline", width=4, command=self.move_up).pack(side="left", padx=2)
        ttk.Button(fr_btns, text="▼", bootstyle="secondary-outline", width=4, command=self.move_down).pack(side="left", padx=2)

        fr_card_list = ttk.Frame(main_container)
        fr_card_list.pack(fill="both", expand=True, pady=(0, 10))
        card_list = Card(fr_card_list, title="Lista de Reportes")
        card_list.pack(fill="both", expand=True)
        c2 = card_list.get_body()
        
        self.tree_filtros = ttk.Treeview(c2, columns=("tabla", "campo", "valor", "version", "acciones"), show="headings", height=8, bootstyle="info")
        self.tree_filtros.heading("tabla", text="Tabla", anchor="w"); self.tree_filtros.heading("campo", text="Campo", anchor="w")
        self.tree_filtros.heading("valor", text="Valor", anchor="w"); self.tree_filtros.heading("version", text="Versión", anchor="center")
        self.tree_filtros.heading("acciones", text="Acciones", anchor="center")
        self.tree_filtros.column("tabla", width=120); self.tree_filtros.column("campo", width=150)
        self.tree_filtros.column("valor", width=200, stretch=True); self.tree_filtros.column("version", width=100, anchor="center")
        self.tree_filtros.column("acciones", width=80, anchor="center")
        
        scrollbar = ttk.Scrollbar(c2, orient="vertical", command=self.tree_filtros.yview)
        scrollbar.pack(side="right", fill="y"); self.tree_filtros.configure(yscrollcommand=scrollbar.set)
        self.tree_filtros.pack(side="left", fill="both", expand=True)
        
        for idx, i in enumerate(self.config.get('filtros_reporte', [])):
            self.tree_filtros.insert("", "end", values=(i['tabla'], i.get('campo',''), i.get('valor',''), i.get('version',''), "🗑️"))
        self.tree_filtros.bind("<Button-1>", lambda e: self.del_filtro() if self.tree_filtros.identify_column(e.x) == "#5" else None)

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
        if nom and rut:
            self.tree_files.insert("", "end", values=(nom, rut, "🗑️"))
            self.ent_f_nom.delete(0, tk.END)
            self.ent_f_rut.delete(0, tk.END)

    def del_file(self):
        for s in self.tree_files.selection(): self.tree_files.delete(s)

    def add_filtro(self):
        t, c, v = self.ent_r_tab.get(), self.ent_r_cam.get(), self.ent_r_val.get()
        if t:
            self.tree_filtros.insert("", "end", values=(t, c, v, self.cb_r_ver.get(), "🗑️"))
            self.ent_r_tab.delete(0, tk.END)
            self.ent_r_cam.delete(0, tk.END)
            self.ent_r_val.delete(0, tk.END)

    def actualizar_todas_versiones_filtro(self, event=None):
        nueva = self.cb_r_ver.get()
        if not nueva: return
        for item_id in self.tree_filtros.get_children():
            vals = list(self.tree_filtros.item(item_id, 'values'))
            if len(vals) >= 4: vals[3] = nueva; self.tree_filtros.item(item_id, values=vals)

    def del_filtro(self):
        for s in self.tree_filtros.selection(): self.tree_filtros.delete(s)

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
            ToastNotification(title="Configuración", message="Guardada correctamente", duration=3000, bootstyle="success").show_toast()
            self.actualizar_dashboard()
        except Exception as e: print(f"❌ Error guardando: {e}")

    def crear_metric_card(self, parent, icon, value, label, bootstyle="primary"):
        card = ttk.Frame(parent, bootstyle=bootstyle, padding=2)
        inner = ttk.Frame(card, style="Card.TFrame", padding=15)
        inner.pack(fill="both", expand=True)
        
        ttk.Label(inner, text=icon, font=("Segoe UI", 24)).pack(side="left", padx=(0, 15))
        text_frame = ttk.Frame(inner)
        text_frame.pack(side="left", fill="both", expand=True)
        ttk.Label(text_frame, text=str(value), font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(text_frame, text=label, font=("Segoe UI", 9)).pack(anchor="w")
        return card

    def actualizar_dashboard(self):
        for w in self.frame_dashboard.winfo_children(): w.destroy()
        ruta = self.ent_ruta.get(); db_path = os.path.join(ruta, NOMBRE_DB_FILE)
        n_files = len(self.tree_files.get_children()) if hasattr(self, 'tree_files') else 0
        n_filters = len(self.tree_filtros.get_children()) if hasattr(self, 'tree_filtros') else 0
        db_exists = os.path.exists(db_path)
        db_size = f"{os.path.getsize(db_path)/(1024*1024):.2f} MB" if db_exists else "0 MB"
        
        grid_container = ttk.Frame(self.frame_dashboard)
        grid_container.pack(fill="both", expand=True, padx=20, pady=5)
        for i in range(3): grid_container.columnconfigure(i, weight=1, uniform="metric")
        
        self.crear_metric_card(grid_container, "💾", db_size, "Base de Datos", "info" if db_exists else "danger").grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.crear_metric_card(grid_container, "📥", n_files, "Archivos", "success").grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.crear_metric_card(grid_container, "📋", n_filters, "Filtros", "warning").grid(row=0, column=2, padx=10, pady=10, sticky="nsew")

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
    # Usamos ttkbootstrap Window en lugar de tk.Tk
    app_window = ttk.Window(themename="minty") 
    app = AplicacionXM(app_window)
    app_window.mainloop()
