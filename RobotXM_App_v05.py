# =============================================================================
#  ROBOT XM - SUITE INTEGRADA (v06 - FINAL + FORMATO FECHA CORREGIDO)
#  Funcionalidades:
#  1. Descarga FTP Automática y Autoreparación.
#  2. Base de Datos SQLite Incremental.
#  3. Reportes Excel (Números ok, Filtro Versión ok, FECHAS SIN HORA).
#  4. VISUALIZADOR GRÁFICO INTEGRADO.
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

# --- LIBRERÍAS GRÁFICAS (MATPLOTLIB) ---
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.dates as mdates
import matplotlib.ticker as ticker

# Silenciar advertencias
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# --- CONSTANTES ---
NOMBRE_DB_FILE = "BaseDatosXM.db"
NOMBRE_REPORTE_FILE = "Reporte_Horizontal_XM.xlsx"
ARCHIVO_CONFIG = "config_app.json"
ARCHIVOS_MENSUALES = ['PEI', 'PME140', 'tserv', 'afac']

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

    def flush(self):
        pass

# =============================================================================
#  MÓDULO 1: LÓGICA DE NEGOCIO (DESCARGA, BD, REPORTES)
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

                if ver_filtro_usuario:
                    query += f" AND version_dato = '{ver_filtro_usuario}'"
                    titulo_texto += f" [Ver: {ver_filtro_usuario}]"
                    print(f"   🔹 Procesando: {nombre_real_bd} (Filtro Ver: {ver_filtro_usuario})")
                else: print(f"   🔹 Procesando: {nombre_real_bd} (Versión Automática)")

                try:
                    df = pd.read_sql_query(query, conn)
                    if df.empty: continue
                    
                    # Fix numérico
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

                    # --- AJUSTE: QUITAR HORAS DE LA FECHA PARA EXCEL ---
                    df['Fecha'] = df['Fecha'].dt.date
                    # ---------------------------------------------------

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
    def __init__(self, parent_frame):
        self.frame_main = parent_frame 
        self.ruta_db = "BaseDatosXM.db"
        
        self.var_tabla = tk.StringVar()
        self.var_version = tk.StringVar()
        self.var_campo_filtro1 = tk.StringVar()
        self.var_valor_filtro1 = tk.StringVar()
        self.var_campo_filtro2 = tk.StringVar()
        self.var_valor_filtro2 = tk.StringVar()
        self.var_campo_valor = tk.StringVar()
        self.var_agregacion = tk.StringVar(value="Promedio")
        self.var_fecha_ini = tk.StringVar()
        self.var_fecha_fin = tk.StringVar()
        self.var_es_horario = tk.BooleanVar(value=False)

        frame_top = ttk.Frame(self.frame_main, padding=5)
        frame_top.pack(fill="x")
        ttk.Label(frame_top, text="BD Gráfica:").pack(side="left")
        self.lbl_db = ttk.Entry(frame_top, width=60)
        self.lbl_db.pack(side="left", padx=5)
        self.lbl_db.insert(0, os.path.abspath(self.ruta_db))
        ttk.Button(frame_top, text="📂", command=self.seleccionar_db).pack(side="left")
        ttk.Button(frame_top, text="🔄 Leer Tablas", command=self.cargar_tablas).pack(side="left", padx=5)

        frame_cfg = ttk.LabelFrame(self.frame_main, text="Parámetros del Gráfico", padding=5)
        frame_cfg.pack(fill="x", padx=10, pady=5)

        ttk.Label(frame_cfg, text="1. Archivo:").grid(row=0, column=0, sticky="w", pady=2)
        self.cb_tabla = ttk.Combobox(frame_cfg, textvariable=self.var_tabla, state="readonly", width=22)
        self.cb_tabla.grid(row=0, column=1, padx=5)
        self.cb_tabla.bind("<<ComboboxSelected>>", self.al_seleccionar_tabla)

        ttk.Label(frame_cfg, text="2. Versión:").grid(row=0, column=2, sticky="w", padx=5)
        self.cb_version = ttk.Combobox(frame_cfg, textvariable=self.var_version, state="readonly", width=15)
        self.cb_version.grid(row=0, column=3, padx=5)

        ttk.Label(frame_cfg, text="3. Filtro 1:").grid(row=1, column=0, sticky="w", pady=2)
        self.cb_campo_filtro1 = ttk.Combobox(frame_cfg, textvariable=self.var_campo_filtro1, state="readonly", width=22)
        self.cb_campo_filtro1.grid(row=1, column=1, padx=5)
        self.cb_campo_filtro1.bind("<<ComboboxSelected>>", self.al_seleccionar_campo_filtro1)

        ttk.Label(frame_cfg, text="Valor 1:").grid(row=1, column=2, sticky="w", padx=5)
        self.cb_valor_filtro1 = ttk.Combobox(frame_cfg, textvariable=self.var_valor_filtro1, width=22) 
        self.cb_valor_filtro1.grid(row=1, column=3, padx=5)

        ttk.Label(frame_cfg, text="4. Filtro 2 (Opc):").grid(row=2, column=0, sticky="w", pady=2)
        self.cb_campo_filtro2 = ttk.Combobox(frame_cfg, textvariable=self.var_campo_filtro2, state="readonly", width=22)
        self.cb_campo_filtro2.grid(row=2, column=1, padx=5)
        self.cb_campo_filtro2.bind("<<ComboboxSelected>>", self.al_seleccionar_campo_filtro2)

        ttk.Label(frame_cfg, text="Valor 2:").grid(row=2, column=2, sticky="w", padx=5)
        self.cb_valor_filtro2 = ttk.Combobox(frame_cfg, textvariable=self.var_valor_filtro2, width=22) 
        self.cb_valor_filtro2.grid(row=2, column=3, padx=5)

        self.chk_horario = ttk.Checkbutton(frame_cfg, text="5. Es Horaria (24h)", variable=self.var_es_horario, command=self.toggle_campo_valor)
        self.chk_horario.grid(row=3, column=0, columnspan=2, sticky="w", pady=5)

        self.lbl_valor = ttk.Label(frame_cfg, text="6. Variable a Graficar:")
        self.lbl_valor.grid(row=3, column=2, sticky="w", padx=5)
        self.cb_campo_valor = ttk.Combobox(frame_cfg, textvariable=self.var_campo_valor, state="readonly", width=22)
        self.cb_campo_valor.grid(row=3, column=3, padx=5)

        ttk.Label(frame_cfg, text="Operación:").grid(row=4, column=0, sticky="w")
        self.cb_agregacion = ttk.Combobox(frame_cfg, textvariable=self.var_agregacion, state="readonly", width=15)
        self.cb_agregacion['values'] = ["Promedio", "Suma", "Máximo", "Mínimo"]
        self.cb_agregacion.current(0)
        self.cb_agregacion.grid(row=4, column=1, sticky="w", padx=5)

        ttk.Label(frame_cfg, text="Inicio:").grid(row=5, column=0, sticky="w")
        self.ent_fecha_ini = ttk.Entry(frame_cfg, textvariable=self.var_fecha_ini, width=12)
        self.ent_fecha_ini.grid(row=5, column=1, sticky="w", padx=5)
        self.ent_fecha_ini.insert(0, "2020-01-01") 

        ttk.Label(frame_cfg, text="Fin:").grid(row=5, column=2, sticky="w")
        self.ent_fecha_fin = ttk.Entry(frame_cfg, textvariable=self.var_fecha_fin, width=12)
        self.ent_fecha_fin.grid(row=5, column=3, sticky="w", padx=5)
        self.ent_fecha_fin.insert(0, datetime.today().strftime('%Y-%m-%d')) 

        ttk.Button(frame_cfg, text="📊 GENERAR GRÁFICO", command=self.generar_grafico).grid(row=6, column=0, columnspan=4, pady=10, sticky="ew")

        self.frame_plot = ttk.Frame(self.frame_main)
        self.frame_plot.pack(fill="both", expand=True, padx=10, pady=5)
        
        if os.path.exists(self.ruta_db):
            self.cargar_tablas()

    def toggle_campo_valor(self):
        if self.var_es_horario.get():
            self.cb_campo_valor.configure(state="disabled")
            self.lbl_valor.configure(text="6. (Modo 24 Horas)")
        else:
            self.cb_campo_valor.configure(state="readonly")
            self.lbl_valor.configure(text="6. Variable a Graficar:")

    def seleccionar_db(self):
        f = filedialog.askopenfilename(filetypes=[("SQLite DB", "*.db")])
        if f:
            self.ruta_db = f
            self.lbl_db.delete(0, tk.END)
            self.lbl_db.insert(0, f)
            self.cargar_tablas()

    def conectar(self):
        return sqlite3.connect(self.ruta_db)

    def cargar_tablas(self):
        if not os.path.exists(self.ruta_db): return
        try:
            conn = self.conectar()
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tablas = [t[0] for t in cur.fetchall()]
            conn.close()
            self.cb_tabla['values'] = sorted(tablas)
            if tablas: self.cb_tabla.set("Seleccione Archivo...")
        except Exception as e: messagebox.showerror("Error", str(e))

    def al_seleccionar_tabla(self, event):
        tabla = self.var_tabla.get()
        if not tabla: return
        conn = self.conectar()
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({tabla})")
        info = cur.fetchall()
        cols = [c[1] for c in info]
        
        if 'version_dato' in cols:
            try:
                versiones_df = pd.read_sql_query(f"SELECT DISTINCT version_dato FROM {tabla} ORDER BY version_dato", conn)
                lista_versiones = versiones_df['version_dato'].astype(str).tolist()
                self.cb_version['values'] = lista_versiones
                if 'txr' in lista_versiones: self.cb_version.set('txr')
                elif lista_versiones: self.cb_version.current(0)
            except: self.cb_version['values'] = []
        else:
            self.cb_version.set("N/A")
            self.cb_version['values'] = []
        conn.close()
        
        cols_horarias = [str(i) for i in range(24)]
        es_horario = all(h in cols for h in cols_horarias)
        self.var_es_horario.set(es_horario)
        self.toggle_campo_valor()
        
        ignorar = ['index', 'anio', 'mes_dia', 'version_dato', 'origen_archivo', 'fecha_carga'] + cols_horarias
        candidatos = [c for c in cols if c.lower() not in ignorar]
        self.cb_campo_filtro1['values'] = candidatos
        self.cb_campo_filtro2['values'] = candidatos
        self.cb_campo_valor['values'] = candidatos
        self.cb_campo_filtro1.set(''); self.cb_valor_filtro1.set('')
        self.cb_campo_filtro2.set(''); self.cb_valor_filtro2.set('')

    def al_seleccionar_campo_filtro1(self, event):
        self._cargar_valores_filtro(self.var_campo_filtro1, self.cb_valor_filtro1)

    def al_seleccionar_campo_filtro2(self, event):
        self._cargar_valores_filtro(self.var_campo_filtro2, self.cb_valor_filtro2)

    def _cargar_valores_filtro(self, var_campo, widget_cb):
        tabla = self.var_tabla.get()
        campo = var_campo.get()
        if not tabla or not campo: return
        try:
            conn = self.conectar()
            df = pd.read_sql_query(f"SELECT DISTINCT {campo} FROM {tabla} ORDER BY {campo}", conn)
            conn.close()
            vals = df[campo].astype(str).tolist()
            widget_cb['values'] = vals
            widget_cb.set('') 
        except: pass

    def generar_grafico(self):
        tabla = self.var_tabla.get()
        version = self.var_version.get()
        campo1 = self.var_campo_filtro1.get(); valor1 = self.var_valor_filtro1.get()
        campo2 = self.var_campo_filtro2.get(); valor2 = self.var_valor_filtro2.get()
        operacion = self.var_agregacion.get()
        es_24h = self.var_es_horario.get()
        f_ini_str = self.var_fecha_ini.get(); f_fin_str = self.var_fecha_fin.get()
        if not tabla: return

        try:
            conn = self.conectar()
            query = f"SELECT * FROM {tabla} WHERE 1=1"
            if campo1 and valor1: query += f" AND CAST({campo1} AS TEXT) = '{valor1}'"
            if campo2 and valor2: query += f" AND CAST({campo2} AS TEXT) = '{valor2}'"
            if version and version != "N/A": query += f" AND version_dato = '{version}'"
            
            print(f"Graficador SQL: {query}")
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                messagebox.showinfo("Vacío", f"No hay datos para graficar.")
                return

            def armar_fecha(row):
                try:
                    anio = str(row['anio']); md = str(row['mes_dia']).zfill(4)
                    if len(str(row['mes_dia'])) <= 2: return pd.to_datetime(f"{anio}-{str(row['mes_dia']).zfill(2)}-01")
                    else: return pd.to_datetime(f"{anio}-{md[:2]}-{md[2:]}")
                except: return pd.NaT

            df['Fecha'] = df.apply(armar_fecha, axis=1)
            df = df.dropna(subset=['Fecha'])

            try:
                if f_ini_str: df = df[df['Fecha'] >= pd.to_datetime(f_ini_str)]
                if f_fin_str: df = df[df['Fecha'] <= pd.to_datetime(f_fin_str)]
                if df.empty: return
            except: return
            
            serie_graficar = None
            if es_24h:
                cols_horas = [c for c in df.columns if c in [str(i) for i in range(24)]]
                if not cols_horas: cols_horas = [c for c in df.columns if 'hora' in c.lower()]
                for c in cols_horas: df[c] = pd.to_numeric(df[c], errors='coerce')
                
                if operacion == "Promedio": df['Res'] = df[cols_horas].mean(axis=1)
                elif operacion == "Suma": df['Res'] = df[cols_horas].sum(axis=1)
                elif operacion == "Máximo": df['Res'] = df[cols_horas].max(axis=1)
                elif operacion == "Mínimo": df['Res'] = df[cols_horas].min(axis=1)
                serie_graficar = df.groupby('Fecha')['Res'].mean()
            else:
                col_val = self.var_campo_valor.get()
                if not col_val: return
                df[col_val] = pd.to_numeric(df[col_val], errors='coerce')
                grupo = df.groupby('Fecha')[col_val]
                if operacion == "Promedio": serie_graficar = grupo.mean()
                elif operacion == "Suma": serie_graficar = grupo.sum()
                elif operacion == "Máximo": serie_graficar = grupo.max()
                elif operacion == "Mínimo": serie_graficar = grupo.min()

            titulo_grafico = f"{tabla.upper()}"
            if valor1: titulo_grafico += f"\n{valor1}"
            if valor2: titulo_grafico += f" - {valor2}"
            titulo_grafico += f" ({operacion})"
            self.dibujar_plot(serie_graficar.sort_index(), titulo_grafico)

        except Exception as e:
            messagebox.showerror("Error", f"{e}")

    def dibujar_plot(self, serie, titulo):
        for widget in self.frame_plot.winfo_children(): widget.destroy()
        fig = Figure(figsize=(8, 4), dpi=100)
        ax = fig.add_subplot(111)
        line, = ax.plot(serie.index, serie.values, marker='o', linestyle='-', markersize=4, color='#27ae60') 
        ax.set_title(titulo, fontsize=10, fontweight='bold')
        ax.grid(True, linestyle=':', alpha=0.6)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}')) 
        fig.autofmt_xdate()

        annot = ax.annotate("", xy=(0,0), xytext=(10,10),textcoords="offset points",
                            bbox=dict(boxstyle="round", fc="w", ec="gray", alpha=0.9), arrowprops=dict(arrowstyle="->"))
        annot.set_visible(False)

        def update_annot(ind):
            x, y = line.get_data()
            idx = ind["ind"][0]
            val_x = x[idx]
            annot.xy = (val_x, y[idx])
            try: fecha_dt = mdates.num2date(val_x)
            except: fecha_dt = val_x
            try:
                if hasattr(fecha_dt, 'strftime'): f_str = fecha_dt.strftime("%Y-%m-%d")
                else: f_str = pd.to_datetime(fecha_dt).strftime("%Y-%m-%d")
            except: f_str = "?"
            annot.set_text(f"{f_str}\n{y[idx]:,.2f}")

        def hover(event):
            vis = annot.get_visible()
            if event.inaxes == ax:
                cont, ind = line.contains(event)
                if cont:
                    update_annot(ind)
                    annot.set_visible(True)
                    fig.canvas.draw_idle()
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
        self.root.title("Suite XM Inteligente - Robot & Visualizador")
        self.root.geometry("1100x850") 
        
        self.config = self.cargar_config()

        style = ttk.Style()
        style.theme_use('clam')

        # --- SISTEMA DE PESTAÑAS PRINCIPAL ---
        tab_control = ttk.Notebook(root)
        
        self.tab_general = ttk.Frame(tab_control)
        self.tab_archivos = ttk.Frame(tab_control)
        self.tab_filtros = ttk.Frame(tab_control)
        self.tab_visualizador = ttk.Frame(tab_control)
        
        tab_control.add(self.tab_general, text='⚙️ Configuración Robot')
        tab_control.add(self.tab_archivos, text='📥 Descargas')
        tab_control.add(self.tab_filtros, text='📋 Filtros Reporte')
        tab_control.add(self.tab_visualizador, text='📈 Visualizador Interactivo')
        
        tab_control.pack(expand=1, fill="both", padx=10, pady=5)

        # Inicializar Pestañas del Robot
        self.crear_tab_general()
        self.crear_tab_archivos()
        self.crear_tab_filtros()
        
        # Inicializar Pestaña del Visualizador
        self.app_visualizador = ModuloVisualizador(self.tab_visualizador)

        # Consola Inferior
        lbl_consola = ttk.Label(root, text="Monitor de Ejecución:")
        lbl_consola.pack(anchor="w", padx=10)
        self.txt_console = scrolledtext.ScrolledText(root, height=8, state='disabled', bg='black', fg='#00FF00', font=('Consolas', 9))
        self.txt_console.pack(fill="both", expand=False, padx=10, pady=5)
        sys.stdout = PrintRedirector(self.txt_console)

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
        ttk.Button(fr_btn, text="💾 Guardar Config", command=self.guardar_config).pack(side="left", padx=5)
        ttk.Button(fr_btn, text="🚀 EJECUTAR DESCARGA + BD", command=self.run_descarga).pack(side="left", padx=20)
        ttk.Button(fr_btn, text="📈 GENERAR REPORTE", command=self.run_reporte).pack(side="left", padx=5)

    def crear_tab_archivos(self):
        fr_in = ttk.Frame(self.tab_archivos)
        fr_in.pack(fill="x", padx=5, pady=5)
        ttk.Label(fr_in, text="Nombre:").pack(side="left")
        self.ent_f_nom = ttk.Entry(fr_in, width=15); self.ent_f_nom.pack(side="left", padx=2)
        ttk.Label(fr_in, text="Ruta FTP:").pack(side="left")
        self.ent_f_rut = ttk.Entry(fr_in, width=30); self.ent_f_rut.pack(side="left", padx=2)
        ttk.Button(fr_in, text="+", command=self.add_file).pack(side="left", padx=5)
        ttk.Button(fr_in, text="-", command=self.del_file).pack(side="left")

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
        self.ent_r_ver = ttk.Entry(fr_in, width=5); self.ent_r_ver.pack(side="left", padx=2)
        ttk.Button(fr_in, text="+", command=self.add_filtro).pack(side="left", padx=5)
        ttk.Button(fr_in, text="-", command=self.del_filtro).pack(side="left")

        self.tree_filtros = ttk.Treeview(self.tab_filtros, columns=("T","C","V","Ver"), show="headings", height=10)
        self.tree_filtros.heading("T", text="Tabla"); self.tree_filtros.column("T", width=100)
        self.tree_filtros.heading("C", text="Campo"); self.tree_filtros.column("C", width=100)
        self.tree_filtros.heading("V", text="Valor"); self.tree_filtros.column("V", width=100)
        self.tree_filtros.heading("Ver", text="Versión"); self.tree_filtros.column("Ver", width=60) 
        self.tree_filtros.pack(fill="both", expand=True, padx=5, pady=5)
        
        for i in self.config.get('filtros_reporte', []): 
            self.tree_filtros.insert("", "end", values=(i['tabla'], i.get('campo',''), i.get('valor',''), i.get('version','')))

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
            self.tree_filtros.insert("", "end", values=(self.ent_r_tab.get(), self.ent_r_cam.get(), self.ent_r_val.get(), self.ent_r_ver.get()))
            self.ent_r_tab.delete(0, tk.END); self.ent_r_cam.delete(0, tk.END); self.ent_r_val.delete(0, tk.END); self.ent_r_ver.delete(0, tk.END)

    def del_filtro(self):
        for s in self.tree_filtros.selection(): self.tree_filtros.delete(s)

    def get_config(self):
        return {
            'usuario': self.ent_user.get(), 'password': self.ent_pass.get(), 'ruta_local': self.ent_ruta.get(),
            'fecha_ini': self.ent_ini.get(), 'fecha_fin': self.ent_fin.get(),
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
            print("✅ Configuración guardada.")
        except Exception as e: print(f"❌ Error guardando: {e}")

    def cargar_config(self):
        if os.path.exists(ARCHIVO_CONFIG):
            try:
                with open(ARCHIVO_CONFIG, 'r') as f:
                    return json.load(f)
            except:
                pass
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
