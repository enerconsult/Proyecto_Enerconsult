# =============================================================================
#  ROBOT XM - VERSIÓN DE PRODUCCIÓN (FINAL + CORRECCIÓN EXCEL NUMÉRICO)
#  Incluye: GUI, Descarga FTP, Auto-reparación, Reportes Multi-filtro
#  Corrección 1: BD y Reportes se guardan en la Ruta Local del usuario.
#  Corrección 2: Los reportes de Excel ahora guardan los números como números y no texto.
# =============================================================================

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
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

# Silenciar advertencias de Excel
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# --- CONSTANTES DE NOMBRES DE ARCHIVO ---
NOMBRE_DB_FILE = "BaseDatosXM.db"
NOMBRE_REPORTE_FILE = "Reporte_Horizontal_XM.xlsx"
ARCHIVO_CONFIG = "config_app.json"
ARCHIVOS_MENSUALES = ['PEI', 'PME140', 'tserv', 'afac']

# =============================================================================
#  CLASE PARA REDIRIGIR LA CONSOLA (GUI)
# =============================================================================
class PrintRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, str_val):
        self.text_widget.configure(state='normal')
        self.text_widget.insert(tk.END, str_val)
        self.text_widget.see(tk.END)
        self.text_widget.configure(state='disabled')
        self.text_widget.update_idletasks()

    def flush(self):
        pass

# =============================================================================
#  MÓDULO 1: DESCARGA FTP Y AUTO-REPARACIÓN
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
    if es_reintento:
        print("\n--- 🔄 INICIANDO FASE DE RECUPERACIÓN (RE-DESCARGA) ---")
    else:
        print("\n--- INICIANDO FASE 1: DESCARGA DE ARCHIVOS ---")
    
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
    
    # Agrupación por rutas para no reconectar innecesariamente
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
            except:
                continue

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
                        if os.path.basename(f).lower().startswith(patron_esperado):
                            coincidencias.append(f)
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

                    if os.path.exists(ruta_destino) and os.path.getsize(ruta_destino) > 0:
                        continue 
                    
                    if es_reintento: print(f"   🔄 Restaurando: {nombre_limpio}")
                    else: print(f"   ⬇️ Descargando: {nombre_limpio}")

                    try:
                        with open(ruta_destino, "wb") as local_file:
                            ftps.retrbinary(f"RETR {archivo}", local_file.write)
                        
                        if os.path.getsize(ruta_destino) == 0:
                            print(f"      ⚠️ Fallida (0 bytes). Borrando...")
                            os.remove(ruta_destino)
                        else:
                            archivos_bajados += 1
                    except Exception as e:
                        print(f"      ❌ Error descarga: {e}")
                        if os.path.exists(ruta_destino):
                            try: os.remove(ruta_destino)
                            except: pass

    try: ftps.quit()
    except: pass
    
    if es_reintento: print(f"✅ RECUPERACIÓN TERMINADA: {archivos_bajados} archivos.")
    else: print(f"✅ FASE 1 TERMINADA.")


# =============================================================================
#  MÓDULO 2: BASE DE DATOS E INGESTA
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

    guardados = 0
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
            print(f"   🗑️ Corrupto ({razon}): {nombre_archivo} -> ELIMINADO PARA RE-DESCARGA")
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
            guardados += 1
            
        except Exception as e:
            if "DF Vacío" in str(e):
                print(f"   🗑️ Corrupto (DF Vacío): {nombre_archivo} -> ELIMINADO")
                try: os.remove(ruta_completa)
                except: pass
                corruptos_eliminados += 1
            else:
                print(f"   ⚠️ Error leyendo {nombre_archivo}: {e}")

    conn.close()
    
    print(f"✅ FASE {'2' if not es_reintento else 'RECUPERACIÓN'} TERMINADA.")
    if corruptos_eliminados > 0: return True 
    return False

# =============================================================================
#  MÓDULO 3: GENERACIÓN DE REPORTES (CON CORRECCIÓN NUMÉRICA EXCEL)
# =============================================================================

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
    except:
        print("❌ Error en fechas.")
        return

    tareas_a_procesar = []
    for item in config['filtros_reporte']:
        tareas_a_procesar.append({
            'tabla_solicitada': item['tabla'],
            'filtro_campo': item['campo'] if item['campo'] else None,
            'filtro_valor': item['valor'] if item['valor'] else None
        })

    if not os.path.exists(ruta_db_completa):
        print(f"❌ No existe la BD en la ruta local: {ruta_db_completa}")
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
                
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND lower(name)='{tabla_solicitada.lower()}'")
                resultado = cursor.fetchone()
                
                if not resultado:
                    print(f"   ⚠️ Tabla '{tabla_solicitada}' no encontrada en BD.")
                    continue
                
                nombre_real_bd = resultado[0]
                query = f"SELECT * FROM {nombre_real_bd}"
                
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
                        print(f"   🔹 Procesando: {nombre_real_bd} (Filtro: {val_filtro_usuario})")
                        query += f" WHERE CAST({nombre_columna_real} AS TEXT) = '{val_filtro_usuario}'"
                        titulo_texto += f" ({val_filtro_usuario})"
                    else:
                        print(f"   🔹 Procesando: {nombre_real_bd} (⚠️ Campo '{col_filtro_usuario}' no existe, descargando todo...)")
                else:
                    print(f"   🔹 Procesando: {nombre_real_bd} (Sin filtro)...")

                try:
                    df = pd.read_sql_query(query, conn)
                    if df.empty: continue

                    # --- CORRECCIÓN DE TIPO DE DATO NUMÉRICO ---
                    # Columnas que sabemos que NO son métricas y no deben convertirse
                    cols_no_numericas = ['index', 'anio', 'mes_dia', 'version_dato', 'origen_archivo', 'fecha_carga']

                    for col in df.columns:
                        # Si la columna no es administrativa y es detectada como objeto (texto)
                        if col not in cols_no_numericas and df[col].dtype == 'object':
                            try:
                                # Intentamos convertir a numérico. Si tiene texto real, fallará y pasará al except.
                                df[col] = pd.to_numeric(df[col])
                            except (ValueError, TypeError):
                                # Es texto real, la dejamos como está.
                                pass
                    # -------------------------------------------

                    def armar_fecha(row):
                        try:
                            anio = str(row['anio'])
                            md = str(row['mes_dia']).zfill(4)
                            if len(str(row['mes_dia'])) <= 2: 
                                 return pd.to_datetime(f"{anio}-{str(row['mes_dia']).zfill(2)}-01")
                            else:
                                 mes = md[:2]; dia = md[2:]
                                 return pd.to_datetime(f"{anio}-{mes}-{dia}")
                        except: return pd.NaT

                    df['Fecha'] = df.apply(armar_fecha, axis=1)
                    cols = ['Fecha'] + [c for c in df.columns if c != 'Fecha']
                    df = df[cols]
                    df = df[(df['Fecha'] >= fecha_ini) & (df['Fecha'] <= fecha_fin)]
                    
                    if df.empty: continue

                    df['peso_version'] = df['version_dato'].apply(calcular_peso_version)
                    df['max_peso_dia'] = df.groupby('Fecha')['peso_version'].transform('max')
                    df_final = df[df['peso_version'] == df['max_peso_dia']].copy()
                    
                    df_final = df_final.sort_values(by='Fecha', ascending=True)
                    cols_borrar = ['peso_version', 'max_peso_dia', 'origen_archivo', 'anio', 'mes_dia', 'fecha_carga']
                    df_final = df_final.drop(columns=[c for c in cols_borrar if c in df_final.columns], errors='ignore')
                    
                    pd.DataFrame({titulo_texto: []}).to_excel(writer, sheet_name="Datos", 
                                    startrow=0, startcol=columna_actual, index=False)
                    df_final.to_excel(writer, sheet_name="Datos", 
                                      startrow=1, startcol=columna_actual, index=False)
                    
                    columna_actual += len(df_final.columns) + 1 
                    tablas_escritas += 1
                    
                except Exception as e:
                    print(f"      ❌ Error interno: {e}")

        conn.close()
        if tablas_escritas > 0: print(f"\n✅ REPORTE LISTO: {ruta_reporte_completa}")
        else: print("\n⚠️ Reporte vacío.")

    except Exception as e:
        print(f"❌ Error guardando Excel: {e}")
        if "Permission denied" in str(e):
             print("💡 ¡Cierra el archivo Excel si lo tienes abierto!")

# =============================================================================
#  INTERFAZ GRÁFICA (GUI)
# =============================================================================

class AplicacionXM:
    def __init__(self, root):
        self.root = root
        self.root.title("Robot XM - Gestor de Energía")
        self.root.geometry("900x700")
        
        self.config = self.cargar_config()

        style = ttk.Style()
        style.theme_use('clam')

        tab_control = ttk.Notebook(root)
        self.tab_general = ttk.Frame(tab_control)
        self.tab_archivos = ttk.Frame(tab_control)
        self.tab_filtros = ttk.Frame(tab_control)
        
        tab_control.add(self.tab_general, text='⚙️ Configuración')
        tab_control.add(self.tab_archivos, text='📥 Lista de Descargas')
        tab_control.add(self.tab_filtros, text='📊 Filtros Reporte')
        tab_control.pack(expand=1, fill="both", padx=10, pady=5)

        self.crear_tab_general()
        self.crear_tab_archivos()
        self.crear_tab_filtros()

        lbl_consola = ttk.Label(root, text="Monitor de Ejecución:")
        lbl_consola.pack(anchor="w", padx=10)
        self.txt_console = scrolledtext.ScrolledText(root, height=12, state='disabled', bg='black', fg='#00FF00', font=('Consolas', 9))
        self.txt_console.pack(fill="both", expand=True, padx=10, pady=5)
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
        self.ent_r_tab = ttk.Entry(fr_in, width=10); self.ent_r_tab.pack(side="left", padx=2)
        ttk.Label(fr_in, text="Campo:").pack(side="left")
        self.ent_r_cam = ttk.Entry(fr_in, width=10); self.ent_r_cam.pack(side="left", padx=2)
        ttk.Label(fr_in, text="Valor:").pack(side="left")
        self.ent_r_val = ttk.Entry(fr_in, width=10); self.ent_r_val.pack(side="left", padx=2)
        ttk.Button(fr_in, text="+", command=self.add_filtro).pack(side="left", padx=5)
        ttk.Button(fr_in, text="-", command=self.del_filtro).pack(side="left")

        self.tree_filtros = ttk.Treeview(self.tab_filtros, columns=("T","C","V"), show="headings", height=10)
        self.tree_filtros.heading("T", text="Tabla"); self.tree_filtros.heading("C", text="Campo"); self.tree_filtros.heading("V", text="Valor")
        self.tree_filtros.pack(fill="both", expand=True, padx=5, pady=5)
        for i in self.config.get('filtros_reporte', []): self.tree_filtros.insert("", "end", values=(i['tabla'], i.get('campo',''), i.get('valor','')))

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
            self.tree_filtros.insert("", "end", values=(self.ent_r_tab.get(), self.ent_r_cam.get(), self.ent_r_val.get()))
            self.ent_r_tab.delete(0, tk.END); self.ent_r_cam.delete(0, tk.END); self.ent_r_val.delete(0, tk.END)

    def del_filtro(self):
        for s in self.tree_filtros.selection(): self.tree_filtros.delete(s)

    def get_config(self):
        return {
            'usuario': self.ent_user.get(), 'password': self.ent_pass.get(), 'ruta_local': self.ent_ruta.get(),
            'fecha_ini': self.ent_ini.get(), 'fecha_fin': self.ent_fin.get(),
            'archivos_descarga': [{'nombre_base': str(self.tree_files.item(i)['values'][0]), 'ruta_remota': str(self.tree_files.item(i)['values'][1])} for i in self.tree_files.get_children()],
            'filtros_reporte': [{'tabla': str(self.tree_filtros.item(i)['values'][0]), 'campo': str(self.tree_filtros.item(i)['values'][1]), 'valor': str(self.tree_filtros.item(i)['values'][2])} for i in self.tree_filtros.get_children()]
        }

    def guardar_config(self):
        try:
            with open(ARCHIVO_CONFIG, 'w') as f: json.dump(self.get_config(), f, indent=4)
            print("✅ Configuración guardada.")
        except Exception as e: print(f"❌ Error guardando: {e}")

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
            print("\n⚠️ SE DETECTARON ARCHIVOS CORRUPTOS EN RANGO. AUTORREPARANDO...")
            time.sleep(1)
            proceso_descarga(cfg, es_reintento=True)
            proceso_base_datos(cfg, es_reintento=True)
        print("\n🏁 PROCESO DE ACTUALIZACIÓN FINALIZADO.")

    def run_reporte(self):
        threading.Thread(target=generar_reporte_logica, args=(self.get_config(),)).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = AplicacionXM(root)
    root.mainloop()
