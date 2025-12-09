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
from datetime import datetime, timedelta
import time
import warnings

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
except ImportError:
    TIENE_PILLOW = False

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
    "Verde Corporativo": "#8cc63f",
    "Azul Corporativo": "#0093d0",
    "Rojo Intenso": "#e74c3c",
    "Naranja": "#f39c12",
    "Morado": "#9b59b6",
    "Gris Oscuro": "#34495e",
    "Negro": "#000000"
}

# =============================================================================
#  CLASE PARA REDIRIGIR LA CONSOLA
# =============================================================================
class PrintRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, str_val):
        try:
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, str_val)
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
            self.text_widget.update_idletasks()
        except: pass

    def flush(self): pass

# =============================================================================
#  NUEVA CLASE: DROPDOWN CON TOOLTIP (Integración solicitada)
# =============================================================================
class CustomDropdownWithTooltip:
    def __init__(self, master, textvariable=None, width=18, command=None):
        self.master = master
        self.items = []
        self.filtered_items = []
        self.textvariable = textvariable
        self.command = command # Callback opcional al seleccionar
        
        # Usamos ttk.Entry para mantener el estilo del resto de la app
        self.entry = ttk.Entry(master, width=width, textvariable=self.textvariable)
        # Nota: No hacemos pack/grid aquí, dejamos que el padre lo haga
        
        # Bindings
        self.entry.bind("<Button-1>", self.show_dropdown)
        self.entry.bind("<KeyRelease>", self.filter_items) 
        self.entry.bind("<Down>", self.focus_listbox)

        self.dropdown = None
        self.tooltip = None
        self.current_index = None

    def focus_listbox(self, event):
        if not self.dropdown: self.show_dropdown()
        if self.listbox: self.listbox.focus_set()

    def update_items(self, new_items):
        """Actualiza la lista de items dinámicamente desde la BD"""
        self.items = [str(x) for x in new_items] # Asegurar strings
        self.filtered_items = self.items[:]


    def show_dropdown(self, event=None):
        if self.dropdown:
            self.dropdown.destroy()
            self.dropdown = None
            return

        self.dropdown = tk.Toplevel(self.master)
        self.dropdown.wm_overrideredirect(True)
        
        # Calcular posición
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        
        # Ancho del dropdown igual al del entry
        w = self.entry.winfo_width()
        self.dropdown.geometry(f"{w}x150+{x}+{y}") # Altura fija o dinámica

        # Scrollbar y Listbox
        frame_list = tk.Frame(self.dropdown)
        frame_list.pack(fill="both", expand=True)
        
        scrollbar = tk.Scrollbar(frame_list, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        # Color corporate match
        self.listbox = tk.Listbox(frame_list, width=width_chars(w), height=8, yscrollcommand=scrollbar.set, exportselection=False,
                                  bg="#ffffff", fg="#2c3e50", selectbackground="#0093d0", selectforeground="#ffffff", font=("Segoe UI", 10), borderwidth=0)
        self.listbox.pack(side="left", fill="both", expand=True)

        for item in self.filtered_items:
            self.listbox.insert(tk.END, item)

        self.listbox.bind("<Motion>", self.on_motion)
        self.listbox.bind("<Leave>", self.hide_tooltip)
        self.listbox.bind("<ButtonRelease-1>", self.select_item)
        self.dropdown.bind("<FocusOut>", lambda e: self.close_dropdown())

    def on_motion(self, event):
        index = self.listbox.nearest(event.y)
        # Verificar que el índice sea válido
        if index >= 0 and index < self.listbox.size():
            if index != self.current_index:
                self.current_index = index
                self.show_tooltip(index, event)

    def show_tooltip(self, index, event):
        self.hide_tooltip()
        text = self.listbox.get(index)
        
        # Solo mostrar tooltip si el texto es largo
        if len(text) < 15: return 

        x = event.x_root + 20
        y = event.y_root + 10
        
        self.tooltip = tk.Toplevel(self.master)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        self.tooltip.attributes("-topmost", True) # Asegurar que esté encima
        
        label = tk.Label(self.tooltip, text=text, background="#ffffe0",
                         relief="solid", borderwidth=1,
                         font=("Arial", "9", "normal"), padx=5, pady=2)
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

    def select_item(self, event):
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
        if self.command: # Ejecutar callback si existe
            try: self.command(None)
            except: pass

    def close_dropdown(self):
        self.hide_tooltip()
        if self.dropdown:
            self.dropdown.destroy()
            self.dropdown = None
            self.current_index = None

    def filter_items(self, event):
        # Filtrar items basado en lo escrito
        if event.keysym in ['Down', 'Up', 'Return']: return # Ignorar navegación
        
        query = self.entry.get().lower()
        self.filtered_items = [item for item in self.items if query in item.lower()]
        
        # Si el dropdown ya está abierto, actualizarlo
        if self.dropdown:
            self.listbox.delete(0, tk.END)
            for item in self.filtered_items:
                self.listbox.insert(tk.END, item)
        else:
            # Si no está abierto y hay texto, abrirlo
            self.show_dropdown()

def width_chars(pixels):
    # Estimación aproximada de caracteres basado en pixeles (depende de la fuente)
    return int(pixels / 7)


# =============================================================================
#  MÓDULO 1: LÓGICA DE NEGOCIO
# =============================================================================

def generar_fechas_permitidas(fecha_ini, fecha_fin):
    dias_validos = set()
    meses_validos = set()
    delta = fecha_fin - fecha_ini
    for i in range(delta.days + 1):
        dia = fecha_ini + timedelta(days=i)
        dias_validos.add(dia.strftime("%m%d"))
        meses_validos.add(dia.strftime("%Y-%m"))
    return dias_validos, meses_validos

def conectar_ftps(usuario, password):
    context = ssl.create_default_context()
    context.set_ciphers('DEFAULT:@SECLEVEL=1') 
    ftps = ftplib.FTP_TLS(context=context)
    try:
        ftps.connect('xmftps.xm.com.co', 210)
        ftps.login(usuario, password)
        ftps.prot_p()
    except Exception as e:
        raise Exception(f"Fallo conexión FTP: {e}")
    return ftps

def proceso_descarga(config, es_reintento=False):
    if es_reintento: print("\n--- 🔄 INICIANDO FASE DE RECUPERACIÓN (RE-DESCARGA) ---")
    else: print("\n--- INICIANDO FASE 1: DESCARGA DE ARCHIVOS ---")
    
    usuario = config['usuario']
    password = config['password']
    ruta_local_base = config['ruta_local']
    
    try:
        fecha_ini = datetime.strptime(config['fecha_ini'], "%Y-%m-%d")
        fecha_fin = datetime.strptime(config['fecha_fin'], "%Y-%m-%d")
    except ValueError:
        print("❌ Error: Formato de fecha inválido. Use YYYY-MM-DD")
        return

    lista_archivos = config['archivos_descarga'] 
    dias_permitidos, meses_permitidos = generar_fechas_permitidas(fecha_ini, fecha_fin)

    try:
        ftps = conectar_ftps(usuario, password)
        if not es_reintento: print("✅ ¡Conexión FTP Exitosa!")
    except Exception as e:
        print(f"❌ No se pudo conectar: {e}")
        return

    archivos_bajados = 0
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
                        if os.path.basename(f).lower().startswith(patron_esperado): coincidencias.append(f)
                else:
                    for f in archivos_en_servidor:
                        nombre_archivo = os.path.basename(f).lower()
                        if not nombre_archivo.startswith(nombre_base_lower): continue
                        for dia in dias_permitidos:
                            if dia in nombre_archivo:
                                coincidencias.append(f)
                                break 
                for archivo in coincidencias:
                    nombre_limpio = os.path.basename(archivo)
                    ruta_destino = os.path.join(ruta_local_mes, nombre_limpio)
                    if os.path.exists(ruta_destino) and os.path.getsize(ruta_destino) > 0: continue 
                    
                    if es_reintento: print(f"   🔄 Restaurando: {nombre_limpio}")
                    else: print(f"   ⬇️ Descargando: {nombre_limpio}")
                    try:
                        with open(ruta_destino, "wb") as local_file:
                            ftps.retrbinary(f"RETR {archivo}", local_file.write)
                        if os.path.getsize(ruta_destino) == 0:
                            os.remove(ruta_destino)
                        else: archivos_bajados += 1
                    except Exception as e:
                        if os.path.exists(ruta_destino):
                            try: os.remove(ruta_destino)
                            except: pass
    try: ftps.quit()
    except: pass
    if es_reintento: print(f"✅ RECUPERACIÓN TERMINADA: {archivos_bajados} archivos.")
    else: print(f"✅ FASE 1 TERMINADA.")

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
    print("   🧠 Cargando memoria de archivos procesados...")
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
    print(f"   🧠 Memoria lista: {len(cache)} archivos.")
    return cache

def proceso_base_datos(config, es_reintento=False):
    if es_reintento: print("\n--- 🔄 INICIANDO FASE DE PROCESAMIENTO (INTENTO #2) ---")
    else: print("\n--- INICIANDO FASE 2: ACTUALIZACIÓN DE BASE DE DATOS ---")
    ruta_descargas = config['ruta_local']
    ruta_db_completa = os.path.join(ruta_descargas, NOMBRE_DB_FILE)
    try:
        fecha_ini = datetime.strptime(config['fecha_ini'], "%Y-%m-%d")
        fecha_fin = datetime.strptime(config['fecha_fin'], "%Y-%m-%d")
    except: return False
    dias_permitidos, meses_permitidos = generar_fechas_permitidas(fecha_ini, fecha_fin)
    
    print(f"🔌 Conectando a BD: {ruta_db_completa}")
    conn = sqlite3.connect(ruta_db_completa)
    cursor = conn.cursor()
    archivos_procesados_cache = cargar_cache_archivos_existentes(cursor)
    
    print(f"📂 Escaneando archivos locales...")
    patron = os.path.join(ruta_descargas, "**", "*.tx*")
    archivos = glob.glob(patron, recursive=True)
    print(f"   🔍 Se encontraron {len(archivos)} archivos. Filtrando...")

    corruptos_eliminados = 0
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

        archivo_corrupto = False
        razon = ""
        if os.path.getsize(ruta_completa) == 0:
            archivo_corrupto = True; razon = "0 bytes"
        if not archivo_corrupto:
            try: pd.read_csv(ruta_completa, sep=';', nrows=1, encoding='latin-1', on_bad_lines='skip', engine='python')
            except pd.errors.EmptyDataError: archivo_corrupto = True; razon = "Vacío"
            except: pass

        if archivo_corrupto:
            print(f"   🗑️ Corrupto ({razon}): {nombre_archivo} -> ELIMINADO")
            try: os.remove(ruta_completa)
            except: pass
            time.sleep(0.1)
            corruptos_eliminados += 1
            continue
            
        try:
            df = pd.read_csv(ruta_completa, sep=';', decimal='.', encoding='latin-1', on_bad_lines='skip', engine='python')
            if df.empty: raise Exception("DF Vacío")
            df.columns = df.columns.str.strip().str.replace(' ', '_').str.lower()
            df['origen_archivo'] = nombre_archivo
            df['anio'] = anio_carpeta
            df['mes_dia'] = fecha_identificador
            df['version_dato'] = version
            df['fecha_carga'] = pd.Timestamp.now()
            df.to_sql(nombre_tabla, conn, if_exists='append', index=False)
            archivos_procesados_cache.add(nombre_archivo) 
            print(f"   💾 Guardado: {nombre_archivo}")
        except Exception as e:
            if "DF Vacío" in str(e):
                try: os.remove(ruta_completa)
                except: pass
                corruptos_eliminados += 1
            else: print(f"   ⚠️ Error leyendo {nombre_archivo}: {e}")
    conn.close()
    print(f"✅ FASE {'2' if not es_reintento else 'RECUPERACIÓN'} TERMINADA.")
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
    print("\n🚀 INICIANDO GENERADOR HORIZONTAL XM")
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
        print(f"❌ No existe la BD en: {ruta_db_completa}")
        return

    conn = sqlite3.connect(ruta_db_completa)
    cursor = conn.cursor()
    print(f"⚙️ Generando reporte en: {ruta_reporte_completa}")
    
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
                query = f"SELECT * FROM {nombre_real_bd} WHERE 1=1"
                titulo_texto = f"ARCHIVO: {tabla_solicitada.upper()}"

                if col_filtro_usuario and val_filtro_usuario:
                    cursor.execute(f"PRAGMA table_info({nombre_real_bd})")
                    columnas_bd = cursor.fetchall()
                    nombre_columna_real = None
                    for col_info in columnas_bd:
                        if col_info[1].lower() == col_filtro_usuario.lower():
                            nombre_columna_real = col_info[1]
                            break
                    if nombre_columna_real:
                        query += f" AND CAST({nombre_columna_real} AS TEXT) = '{val_filtro_usuario}'"
                        titulo_texto += f" ({val_filtro_usuario})"
                    else: print(f"   ⚠️ Campo '{col_filtro_usuario}' no existe.")

                if ver_filtro_usuario and ver_filtro_usuario != "Última":
                    query += f" AND version_dato = '{ver_filtro_usuario}'"
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
                except Exception as e: print(f"      ❌ Error interno: {e}")
        conn.close()
        if tablas_escritas > 0: print(f"\n✅ REPORTE LISTO: {ruta_reporte_completa}")
        else: print("\n⚠️ Reporte vacío.")
    except Exception as e: print(f"❌ Error guardando Excel: {e}")

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

        frame_top = ttk.Frame(self.frame_main, padding=5)
        frame_top.pack(fill="x")
        ttk.Label(frame_top, text="BD Gráfica:").pack(side="left")
        self.lbl_db = ttk.Entry(frame_top, width=60)
        self.lbl_db.pack(side="left", padx=5)
        self.lbl_db.insert(0, os.path.abspath(self.ruta_db))
        ttk.Button(frame_top, text="📂", command=self.seleccionar_db).pack(side="left")
        ttk.Button(frame_top, text="🔄 Leer Tablas", command=self.cargar_tablas, style="Primary.TButton").pack(side="left", padx=5)

        # --- LAYOUT OPTIMIZADO (3 COLUMNAS) ---
        frame_controls = ttk.Frame(self.frame_main)
        frame_controls.pack(fill="x", padx=5, pady=5)

        # COLUMNA 1: FUENTE DE DATOS
        col1 = ttk.LabelFrame(frame_controls, text="1. Fuente de Datos")
        col1.pack(side="left", fill="both", expand=True, padx=5)
        
        ttk.Label(col1, text="Archivo:").grid(row=0, column=0, sticky="w", pady=2)
        self.cb_tabla = ttk.Combobox(col1, textvariable=self.var_tabla, state="readonly", width=18)
        self.cb_tabla.grid(row=0, column=1, padx=2); self.cb_tabla.bind("<<ComboboxSelected>>", self.al_seleccionar_tabla)

        ttk.Label(col1, text="Versión:").grid(row=1, column=0, sticky="w", pady=2)
        self.cb_version = ttk.Combobox(col1, textvariable=self.var_version, state="readonly", width=18)
        self.cb_version.grid(row=1, column=1, padx=2)

        ttk.Label(col1, text="Filtro 1:").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(col1, text="Filtro 1:").grid(row=2, column=0, sticky="w", pady=2)
        # REEMPLAZO COMBOBOX POR CUSTOM SEARCHABLE
        self.cb_campo_filtro1 = CustomDropdownWithTooltip(col1, textvariable=self.var_campo_filtro1, width=25, command=self.al_seleccionar_campo_filtro1)
        self.cb_campo_filtro1.entry.grid(row=2, column=1, padx=2)
        # self.cb_campo_filtro1.bind("<<ComboboxSelected>>", self.al_seleccionar_campo_filtro1) # YA NO SE USA BIND, SE USA COMMAND
        
        # --- CAMBIO: INTEGRACIÓN DE TOOLTIP CUSTOM DROPDOWN ---
        # Reemplazamos el Combobox de Valor 1 por la clase custom
        self.cb_valor_filtro1 = CustomDropdownWithTooltip(col1, textvariable=self.var_valor_filtro1, width=25)
        self.cb_valor_filtro1.entry.grid(row=3, column=1, padx=2) 
        # --------------------------------------------------------

        ttk.Label(col1, text="Filtro 2 (opc):").grid(row=4, column=0, sticky="w", pady=2)
        ttk.Label(col1, text="Filtro 2 (opc):").grid(row=4, column=0, sticky="w", pady=2)
        # REEMPLAZO COMBOBOX POR CUSTOM SEARCHABLE
        self.cb_campo_filtro2 = CustomDropdownWithTooltip(col1, textvariable=self.var_campo_filtro2, width=25, command=self.al_seleccionar_campo_filtro2)
        self.cb_campo_filtro2.entry.grid(row=4, column=1, padx=2)
        # self.cb_campo_filtro2.bind("<<ComboboxSelected>>", self.al_seleccionar_campo_filtro2) # YA NO SE USA BIND
        
        # --- CAMBIO: INTEGRACIÓN DE TOOLTIP CUSTOM DROPDOWN ---
        # Reemplazamos el Combobox de Valor 2 por la clase custom
        self.cb_valor_filtro2 = CustomDropdownWithTooltip(col1, textvariable=self.var_valor_filtro2, width=25)
        self.cb_valor_filtro2.entry.grid(row=5, column=1, padx=2)
        # --------------------------------------------------------

        # COLUMNA 2: CONFIGURACIÓN
        col2 = ttk.LabelFrame(frame_controls, text="2. Configuración")
        col2.pack(side="left", fill="both", expand=True, padx=5)

        ttk.Label(col2, text="Temporalidad:").grid(row=0, column=0, sticky="w", pady=2)
        self.cb_temporalidad = ttk.Combobox(col2, textvariable=self.var_temporalidad, state="readonly", width=18)
        self.cb_temporalidad['values'] = ["Diaria", "Mensual", "Horaria (24h)"]
        self.cb_temporalidad.grid(row=0, column=1, padx=2)
        self.cb_temporalidad.bind("<<ComboboxSelected>>", self.toggle_campo_valor)

        self.lbl_valor = ttk.Label(col2, text="Variable:")
        self.lbl_valor.grid(row=1, column=0, sticky="w", pady=2)
        # REEMPLAZO COMBOBOX POR CUSTOM SEARCHABLE
        self.cb_campo_valor = CustomDropdownWithTooltip(col2, textvariable=self.var_campo_valor, width=25)
        self.cb_campo_valor.entry.grid(row=1, column=1, padx=2)

        ttk.Label(col2, text="Operación:").grid(row=2, column=0, sticky="w", pady=2)
        self.cb_agregacion = ttk.Combobox(col2, textvariable=self.var_agregacion, state="readonly", width=18)
        self.cb_agregacion['values'] = ["Valor", "Promedio", "Suma", "Máximo", "Mínimo"]; self.cb_agregacion.current(0)
        self.cb_agregacion.grid(row=2, column=1, padx=2)

        ttk.Label(col2, text="Tipo:").grid(row=3, column=0, sticky="w", pady=2)
        self.cb_tipo = ttk.Combobox(col2, textvariable=self.var_tipo_grafico, state="readonly", width=18)
        self.cb_tipo['values'] = ["Línea", "Barras", "Área", "Dispersión"]; self.cb_tipo.current(0)
        self.cb_tipo.grid(row=3, column=1, padx=2)

        ttk.Label(col2, text="Color:").grid(row=4, column=0, sticky="w", pady=2)
        self.cb_color = ttk.Combobox(col2, textvariable=self.var_color_grafico, state="readonly", width=18)
        self.cb_color['values'] = list(COLORES_GRAFICO.keys()); self.cb_color.current(0)
        self.cb_color.grid(row=4, column=1, padx=2)

        # COLUMNA 3: TIEMPO Y ACCIÓN
        col3 = ttk.LabelFrame(frame_controls, text="3. Periodo y Acción")
        col3.pack(side="left", fill="both", expand=True, padx=5)

        ttk.Label(col3, text="Inicio:").grid(row=0, column=0, sticky="w", pady=5)
        self.ent_fecha_ini = ttk.Entry(col3, textvariable=self.var_fecha_ini, width=12)
        self.ent_fecha_ini.grid(row=0, column=1, padx=2)
        self.ent_fecha_ini.insert(0, config.get('viz_fecha_ini', '2025-01-01')) 

        ttk.Label(col3, text="Fin:").grid(row=1, column=0, sticky="w", pady=5)
        self.ent_fecha_fin = ttk.Entry(col3, textvariable=self.var_fecha_fin, width=12)
        self.ent_fecha_fin.grid(row=1, column=1, padx=2)
        self.ent_fecha_fin.insert(0, config.get('viz_fecha_fin', datetime.today().strftime('%Y-%m-%d')))
        
        # Bindings para actualizar versiones al cambiar fechas
        self.ent_fecha_ini.bind("<FocusOut>", self.actualizar_versiones)
        self.ent_fecha_fin.bind("<FocusOut>", self.actualizar_versiones) 

        ttk.Button(col3, text="📊 GRAFICAR", command=self.generar_grafico, style="Primary.TButton").grid(row=3, column=0, columnspan=2, pady=15, sticky="ew", padx=10)
        ttk.Button(col3, text="📥 EXCEL", command=self.exportar_datos_excel, style="Success.TButton").grid(row=4, column=0, columnspan=2, pady=5, sticky="ew", padx=10)

        # PANEL ESTADÍSTICAS
        self.frame_stats = ttk.Frame(self.frame_main)
        self.frame_stats.pack(fill="x", padx=10, pady=2)
        self.lbl_stat_prom = ttk.Label(self.frame_stats, text="Promedio: --", font=('Arial', 8, 'bold'))
        self.lbl_stat_prom.pack(side="left", padx=10)
        self.lbl_stat_max = ttk.Label(self.frame_stats, text="Max: --", font=('Arial', 8, 'bold'), foreground="green")
        self.lbl_stat_max.pack(side="left", padx=10)
        self.lbl_stat_min = ttk.Label(self.frame_stats, text="Min: --", font=('Arial', 8, 'bold'), foreground="red")
        self.lbl_stat_min.pack(side="left", padx=10)
        self.lbl_stat_sum = ttk.Label(self.frame_stats, text="Suma: --", font=('Arial', 8, 'bold'), foreground="blue")
        self.lbl_stat_sum.pack(side="left", padx=10)

        self.frame_plot = ttk.Frame(self.frame_main)
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
                col_val = self.var_campo_valor.get(); 
                if not col_val: return
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
        fig = Figure(figsize=(8, 4), dpi=100, facecolor='#ffffff')
        # Ajuste de margenes para evitar recorte de titulo
        fig.subplots_adjust(top=0.85, bottom=0.15, left=0.10, right=0.95)
        
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
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        toolbar = NavigationToolbar2Tk(canvas, self.frame_plot)
        toolbar.update()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

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

        tab_control = ttk.Notebook(root)
        self.tab_general = ttk.Frame(tab_control)
        self.tab_archivos = ttk.Frame(tab_control)
        self.tab_filtros = ttk.Frame(tab_control)
        self.tab_visualizador = ttk.Frame(tab_control)
        
        tab_control.add(self.tab_general, text='⚙️ Configuración')
        tab_control.add(self.tab_archivos, text='📥 Descargas')
        tab_control.add(self.tab_filtros, text='📋 Filtros Reporte')
        tab_control.add(self.tab_visualizador, text='📈 Visualizador')
        
        tab_control.pack(expand=1, fill="both", padx=10, pady=5)

        self.crear_tab_general()
        self.crear_tab_archivos()
        self.crear_tab_filtros()
        
        # --- PASAMOS LA CONFIG AL VISUALIZADOR ---
        self.app_visualizador = ModuloVisualizador(self.tab_visualizador, self.config)

        lbl_consola = ttk.Label(root, text="Monitor de Ejecución:")
        lbl_consola.pack(anchor="w", padx=10)
        self.txt_console = scrolledtext.ScrolledText(root, height=8, state='disabled', bg='black', fg='#00FF00', font=('Consolas', 9))
        self.txt_console.pack(fill="both", expand=False, padx=10, pady=5)
        sys.stdout = PrintRedirector(self.txt_console)
        
        # Cargar valores iniciales en dashboard (al final de todo)
        self.actualizar_dashboard()

    def configurar_estilos_modernos(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # --- PALETA DE COLORES ENERCONSULT ---
        c_azul_corp = "#0093d0"
        c_verde_corp = "#8cc63f"
        c_fondo = "#f4f6f7"
        c_blanco = "#ffffff"
        c_texto = "#2c3e50"
        c_gris_claro = "#ecf0f1"

        self.root.configure(bg=c_fondo)

        # --- FUENTES ---
        f_main = ("Segoe UI", 10)
        f_head = ("Segoe UI Semibold", 11)
        f_title = ("Segoe UI", 12, "bold")

        # --- CONFIG GENERAL ---
        style.configure(".", background=c_fondo, foreground=c_texto, font=f_main)
        style.configure("TFrame", background=c_fondo)
        style.configure("TLabelframe", background=c_fondo, borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background=c_fondo, foreground=c_azul_corp, font=f_title)
        
        # --- PESTAÑAS (NOTEBOOK) MODERNAS ---
        style.configure("TNotebook", background=c_fondo, borderwidth=0)
        style.configure("TNotebook.Tab", padding=[15, 8], font=f_head, background=c_gris_claro, foreground="#7f8c8d", borderwidth=0)
        style.map("TNotebook.Tab", 
            background=[("selected", c_blanco), ("active", "#dfe6e9")],
            foreground=[("selected", c_azul_corp), ("active", c_azul_corp)],
            expand=[("selected", [1, 1, 1, 0])] # Efecto "conectado" con el contenido
        )

        # --- BOTONES MODERNOS ---
        # Botón Primario (Azul)
        style.configure("Primary.TButton", font=f_head, background=c_azul_corp, foreground="white", borderwidth=0, focuscolor=c_azul_corp)
        style.map("Primary.TButton", background=[("active", "#007bb5"), ("disabled", "#bdc3c7")])
        
        # Botón Success (Verde)
        style.configure("Success.TButton", font=f_head, background=c_verde_corp, foreground="white", borderwidth=0, focuscolor=c_verde_corp)
        style.map("Success.TButton", background=[("active", "#7ab828"), ("disabled", "#bdc3c7")])

        # Botón Danger (Rojo - Nuevo)
        style.configure("Danger.TButton", font=f_head, background="#e74c3c", foreground="white", borderwidth=0, focuscolor="#e74c3c")
        style.map("Danger.TButton", background=[("active", "#c0392b"), ("disabled", "#bdc3c7")])

        # Botón Neutro (Gris/Default)
        style.configure("TButton", font=f_main, padding=5)

        # --- TREEVIEW (TABLAS) ---
        style.configure("Treeview", 
            background=c_blanco, 
            foreground=c_texto, 
            fieldbackground=c_blanco, 
            rowheight=25, 
            font=f_main,
            borderwidth=1, relief="solid"
        )
        style.configure("Treeview.Heading", font=f_head, background="#dfe6e9", foreground=c_texto, padding=5)
        style.map("Treeview", background=[("selected", c_azul_corp)], foreground=[("selected", "white")])

        # --- ENTRADAS ---
        style.configure("TEntry", padding=5, relief="flat", borderwidth=1)
        
        # --- SCROLLBAR ---
        style.configure("Vertical.TScrollbar", background=c_gris_claro, troughcolor=c_fondo, borderwidth=0, arrowsize=12)

    def construir_encabezado_logo(self):
        frame_header = tk.Frame(self.root, bg="white", height=100)
        frame_header.pack(fill="x", side="top")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ruta_logo = os.path.join(script_dir, LOGO_FILENAME)
        
        if TIENE_PILLOW and os.path.exists(ruta_logo):
            try:
                pil_img = Image.open(ruta_logo)
                base_height = 60
                w_percent = (base_height / float(pil_img.size[1]))
                w_size = int((float(pil_img.size[0]) * float(w_percent)))
                pil_img = pil_img.resize((w_size, base_height), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(pil_img)
                lbl_logo = tk.Label(frame_header, image=self.logo_img, bg="white")
                lbl_logo.pack(pady=10)
            except Exception as e: print(f"⚠️ Error logo: {e}")

    def crear_tab_general(self):
        fr = ttk.LabelFrame(self.tab_general, text="Credenciales FTP y Rutas")
        fr.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(fr, text="Usuario FTP:").grid(row=0, column=0, padx=5, pady=5)
        self.ent_user = ttk.Entry(fr); self.ent_user.grid(row=0, column=1, padx=5)
        self.ent_user.insert(0, self.config.get('usuario', ''))
        
        ttk.Label(fr, text="Password FTP:").grid(row=0, column=2, padx=5)
        self.ent_pass = ttk.Entry(fr, show="*"); self.ent_pass.grid(row=0, column=3, padx=5)
        self.ent_pass.insert(0, self.config.get('password', ''))
        
        ttk.Label(fr, text="Ruta Local:").grid(row=1, column=0, padx=5)
        self.ent_ruta = ttk.Entry(fr, width=50); self.ent_ruta.grid(row=1, column=1, columnspan=2, padx=5)
        self.ent_ruta.insert(0, self.config.get('ruta_local', ''))
        ttk.Button(fr, text="📂", command=self.seleccionar_carpeta).grid(row=1, column=3, padx=5)

        fr_f = ttk.LabelFrame(self.tab_general, text="Rango de Fechas (YYYY-MM-DD)")
        fr_f.pack(fill="x", padx=10, pady=5)
        ttk.Label(fr_f, text="Inicio:").grid(row=0, column=0, padx=5)
        self.ent_ini = ttk.Entry(fr_f); self.ent_ini.grid(row=0, column=1, padx=5)
        self.ent_ini.insert(0, self.config.get('fecha_ini', '2025-01-01'))
        ttk.Label(fr_f, text="Fin:").grid(row=0, column=2, padx=5)
        self.ent_fin = ttk.Entry(fr_f); self.ent_fin.grid(row=0, column=3, padx=5)
        self.ent_fin.insert(0, self.config.get('fecha_fin', '2025-01-31'))

        fr_btn = ttk.Frame(self.tab_general)
        fr_btn.pack(fill="x", padx=10, pady=15)
        ttk.Button(fr_btn, text="💾 Guardar Config", command=self.guardar_config, style="Success.TButton").pack(side="left", padx=5)
        ttk.Button(fr_btn, text="🚀 EJECUTAR DESCARGA + BD", command=self.run_descarga, style="Primary.TButton").pack(side="left", padx=20)
        ttk.Button(fr_btn, text="📈 GENERAR REPORTE", command=self.run_reporte, style="Primary.TButton").pack(side="left", padx=5)

        # --- DASHBOARD INFORMATIVO ---
        fr_dash = tk.Frame(self.tab_general, bg="#f4f6f7")
        fr_dash.pack(fill="both", expand=True, padx=10, pady=10)

        # Panel Izquierdo: Métricas
        self.fr_metrics = ttk.LabelFrame(fr_dash, text="Estado del Sistema")
        self.fr_metrics.pack(side="left", fill="both", expand=True, padx=5)
        
        self.lbl_info_db = ttk.Label(self.fr_metrics, text="💾 Base de Datos: --", font=("Segoe UI", 9))
        self.lbl_info_db.pack(anchor="w", padx=10, pady=5)
        self.lbl_info_upd = ttk.Label(self.fr_metrics, text="📅 Última Modificación: --", font=("Segoe UI", 9))
        self.lbl_info_upd.pack(anchor="w", padx=10, pady=5)
        self.lbl_info_files = ttk.Label(self.fr_metrics, text="📥 Archivos Configurados: --", font=("Segoe UI", 9))
        self.lbl_info_files.pack(anchor="w", padx=10, pady=5)
        self.lbl_info_filters = ttk.Label(self.fr_metrics, text="📋 Filtros Reporte: --", font=("Segoe UI", 9))
        self.lbl_info_filters.pack(anchor="w", padx=10, pady=5)

        # Panel Derecho: Flujo de Trabajo
        fr_flow = ttk.LabelFrame(fr_dash, text="Flujo de Trabajo")
        fr_flow.pack(side="left", fill="both", expand=True, padx=5)
        
        lbl_flow_icon = ttk.Label(fr_flow, text="☁️ XM  ➔  ⬇️ Descarga  ➔  💾 BD  ➔  📈 Visualizador", font=("Segoe UI", 11, "bold"), foreground="#0093d0")
        lbl_flow_icon.pack(fill="x", padx=10, pady=15)
        
        txt_guide = ("1. Configura tus credenciales y rutas.\n"
                     "2. Ejecuta 'Descarga + BD' para actualizar datos.\n"
                     "3. Usa el Visualizador o Genera Reportes Excel.")
        ttk.Label(fr_flow, text=txt_guide, justify="left", foreground="#7f8c8d").pack(anchor="w", padx=10)



        # self.actualizar_dashboard() # MOVIDO A __INIT__ PARA EVITAR ERROR

    def crear_tab_archivos(self):
        fr_in = ttk.Frame(self.tab_archivos)
        fr_in.pack(fill="x", padx=5, pady=5)
        ttk.Label(fr_in, text="Nombre:").pack(side="left")
        self.ent_f_nom = ttk.Entry(fr_in, width=15); self.ent_f_nom.pack(side="left", padx=2)
        ttk.Label(fr_in, text="Ruta FTP:").pack(side="left")
        self.ent_f_rut = ttk.Entry(fr_in, width=30); self.ent_f_rut.pack(side="left", padx=2)
        ttk.Button(fr_in, text="✚", width=3, command=self.add_file, style="Success.TButton").pack(side="left", padx=5)
        ttk.Button(fr_in, text="✖", width=3, command=self.del_file, style="Danger.TButton").pack(side="left")

        self.tree_files = ttk.Treeview(self.tab_archivos, columns=("N","R"), show="headings", height=10)
        self.tree_files.heading("N", text="Nombre Archivo"); self.tree_files.heading("R", text="Ruta FTP")
        self.tree_files.pack(fill="both", expand=True, padx=5, pady=5)
        for i in self.config.get('archivos_descarga', []): self.tree_files.insert("", "end", values=(i['nombre_base'], i['ruta_remota']))

    def crear_tab_filtros(self):
        fr_in = ttk.Frame(self.tab_filtros)
        fr_in.pack(fill="x", padx=5, pady=5)
        ttk.Label(fr_in, text="Tabla:").pack(side="left")
        self.ent_r_tab = ttk.Entry(fr_in, width=8); self.ent_r_tab.pack(side="left", padx=2)
        ttk.Label(fr_in, text="Campo:").pack(side="left")
        self.ent_r_cam = ttk.Entry(fr_in, width=8); self.ent_r_cam.pack(side="left", padx=2)
        ttk.Label(fr_in, text="Valor:").pack(side="left")
        self.ent_r_val = ttk.Entry(fr_in, width=8); self.ent_r_val.pack(side="left", padx=2)
        ttk.Label(fr_in, text="Versión:").pack(side="left")
        self.cb_r_ver = ttk.Combobox(fr_in, width=7, state="readonly")
        self.cb_r_ver['values'] = ["Última", "tx1", "tx2", "txf", "txr", "txa", "def"]
        self.cb_r_ver.set("Última")
        self.cb_r_ver.pack(side="left", padx=2)
        # BINDING para actualización masiva
        self.cb_r_ver.bind("<<ComboboxSelected>>", self.actualizar_todas_versiones_filtro)
        
        ttk.Button(fr_in, text="✚", width=3, command=self.add_filtro, style="Success.TButton").pack(side="left", padx=2)
        ttk.Button(fr_in, text="✖", width=3, command=self.del_filtro, style="Danger.TButton").pack(side="left", padx=2)
        ttk.Separator(fr_in, orient="vertical").pack(side="left", padx=5, fill="y")
        ttk.Button(fr_in, text="▲", width=3, command=self.move_up, style="Primary.TButton").pack(side="left", padx=2)
        ttk.Button(fr_in, text="▼", width=3, command=self.move_down, style="Primary.TButton").pack(side="left", padx=2)

        self.tree_filtros = ttk.Treeview(self.tab_filtros, columns=("T","C","V","Ver"), show="headings", height=10)
        self.tree_filtros.heading("T", text="Tabla"); self.tree_filtros.column("T", width=100)
        self.tree_filtros.heading("C", text="Campo"); self.tree_filtros.column("C", width=100)
        self.tree_filtros.heading("V", text="Valor"); self.tree_filtros.column("V", width=100)
        self.tree_filtros.heading("Ver", text="Versión"); self.tree_filtros.column("Ver", width=60) 
        self.tree_filtros.pack(fill="both", expand=True, padx=5, pady=5)
        
        for i in self.config.get('filtros_reporte', []): 
            self.tree_filtros.insert("", "end", values=(i['tabla'], i.get('campo',''), i.get('valor',''), i.get('version','')))

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
        if self.ent_f_nom.get(): self.tree_files.insert("", "end", values=(self.ent_f_nom.get(), self.ent_f_rut.get()))
        self.ent_f_nom.delete(0, tk.END)

    def del_file(self):
        for s in self.tree_files.selection(): self.tree_files.delete(s)

    def add_filtro(self):
        if self.ent_r_tab.get():
            self.tree_filtros.insert("", "end", values=(self.ent_r_tab.get(), self.ent_r_cam.get(), self.ent_r_val.get(), self.cb_r_ver.get()))
            self.ent_r_tab.delete(0, tk.END); self.ent_r_cam.delete(0, tk.END); self.ent_r_val.delete(0, tk.END)
            # self.cb_r_ver.set("Última") # Opcional: reiniciar o mantener

    def actualizar_todas_versiones_filtro(self, event=None):
        nueva_version = self.cb_r_ver.get()
        if not nueva_version: return
        # Recorrer todos los items del treeview y actualizar columna versión (índice 3)
        for item_id in self.tree_filtros.get_children():
            vals = list(self.tree_filtros.item(item_id, 'values'))
            # vals es una tupla, convertimos a lista, modificamos y seteamos
            vals[3] = nueva_version
            self.tree_filtros.item(item_id, values=vals)

    def del_filtro(self):
        for s in self.tree_filtros.selection(): self.tree_filtros.delete(s)

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

    def actualizar_dashboard(self):
        # 1. Info DB
        ruta = self.ent_ruta.get()
        db_path = os.path.join(ruta, NOMBRE_DB_FILE)
        if os.path.exists(db_path):
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            mtime = datetime.fromtimestamp(os.path.getmtime(db_path)).strftime('%Y-%m-%d %H:%M')
            self.lbl_info_db.config(text=f"💾 Base de Datos: {size_mb:.2f} MB", foreground="#27ae60")
            self.lbl_info_upd.config(text=f"📅 Actualizado: {mtime}")
        else:
            self.lbl_info_db.config(text="💾 Base de Datos: No encontrada", foreground="#e74c3c")
            self.lbl_info_upd.config(text="📅 Actualizado: --")

        # 2. Conteos (Safeguard)
        n_files = 0
        if hasattr(self, 'tree_files'): n_files = len(self.tree_files.get_children())
        
        n_filters = 0
        if hasattr(self, 'tree_filtros'): n_filters = len(self.tree_filtros.get_children())

        self.lbl_info_files.config(text=f"📥 Archivos Configurados: {n_files}")
        self.lbl_info_filters.config(text=f"📋 Filtros Reporte: {n_filters}")

    def cargar_config(self):
        if os.path.exists(ARCHIVO_CONFIG):
            try:
                with open(ARCHIVO_CONFIG, 'r') as f: return json.load(f)
            except: pass
        return {}

    def run_descarga(self):
        threading.Thread(target=self._exec_descarga, args=(self.get_config(),)).start()
    
    def _exec_descarga(self, cfg):
        proceso_descarga(cfg)
        necesita_fix = proceso_base_datos(cfg)
        if necesita_fix:
            print("\n⚠️ DETECTADOS ARCHIVOS CORRUPTOS. AUTORREPARANDO...")
            time.sleep(1)
            proceso_descarga(cfg, es_reintento=True)
            proceso_base_datos(cfg, es_reintento=True)
        print("\n🏁 PROCESO FINALIZADO.")

    def run_reporte(self):
        threading.Thread(target=generar_reporte_logica, args=(self.get_config(),)).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = AplicacionXM(root)
    root.mainloop()
