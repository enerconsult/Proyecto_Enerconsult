import sys
import subprocess
import importlib

# --- BLOQUE DE AUTO-INSTALACIÓN ---
def verificar_e_instalar(paquete, nombre_import=None):
    """
    Intenta importar un paquete. Si falla, lo instala automáticamente
    usando pip y luego lo importa.
    """
    if nombre_import is None:
        nombre_import = paquete
        
    try:
        importlib.import_module(nombre_import)
    except ImportError:
        print(f"📦 Instalando librería faltante: {paquete}...")
        try:
            # Usamos sys.executable para asegurar que instalamos en ESTE Python
            subprocess.check_call([sys.executable, "-m", "pip", "install", paquete])
            print(f"✅ {paquete} instalado correctamente.")
        except Exception as e:
            print(f"❌ Error instalando {paquete}: {e}")
            input("Presiona Enter para salir...")
            sys.exit(1)

# Lista de librerías que tu código necesita (nombre en pip, nombre en import)
verificar_e_instalar("pandas")
verificar_e_instalar("openpyxl")

#-----------------------------------------------------------------------

import ftplib
import ssl
import os
import pandas as pd
from datetime import timedelta
import sys
import sqlite3
import glob
import re
import warnings
import time

# Silenciar advertencias
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# --- CONFIGURACIÓN DE RUTAS ---
if getattr(sys, 'frozen', False):
    app_path = os.path.dirname(sys.executable)
else:
    app_path = os.path.dirname(os.path.abspath(__file__))

NOMBRE_ARCHIVO = "DescargasXM.xlsm" 
ARCHIVO_EXCEL = os.path.join(app_path, NOMBRE_ARCHIVO)
HOJA_NOMBRE = "Hoja1"
NOMBRE_DB = os.path.join(app_path, "BaseDatosXM.db")

ARCHIVOS_MENSUALES = ['PEI', 'PME140', 'tserv','afac']

# ==========================================
#  UTILIDADES DE FECHAS
# ==========================================

def generar_fechas_permitidas(fecha_ini, fecha_fin):
    dias_validos = set()
    meses_validos = set()
    delta = fecha_fin - fecha_ini
    for i in range(delta.days + 1):
        dia = fecha_ini + timedelta(days=i)
        dias_validos.add(dia.strftime("%m%d"))
        meses_validos.add(dia.strftime("%Y-%m"))
    return dias_validos, meses_validos

# ==========================================
#  MÓDULO 1: DESCARGA FTP
# ==========================================

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

def proceso_descarga(df_config, es_reintento=False):
    if es_reintento:
        print("\n--- 🔄 INICIANDO FASE DE RECUPERACIÓN (RE-DESCARGA) ---")
    else:
        print("\n--- INICIANDO FASE 1: DESCARGA DE ARCHIVOS ---")
    
    usuario = df_config.iloc[1, 0] 
    password = df_config.iloc[1, 1] 
    ruta_local_base = df_config.iloc[1, 3] 
    fecha_ini = df_config.iloc[1, 4] 
    fecha_fin = df_config.iloc[1, 5] 
    
    lista_archivos = df_config.iloc[5:, [0, 1]].dropna() 
    lista_archivos.columns = ['NombreBase', 'RutaRemota']

    dias_permitidos, meses_permitidos = generar_fechas_permitidas(fecha_ini, fecha_fin)

    try:
        ftps = conectar_ftps(usuario, password)
        if not es_reintento: print("✅ ¡Conexión FTP Exitosa!")
    except Exception as e:
        print(f"❌ No se pudo conectar: {e}")
        return

    archivos_bajados = 0

    for anio_mes in sorted(list(meses_permitidos)):
        mes_actual_str = anio_mes.split("-")[1] 
        
        ruta_local_mes = os.path.join(ruta_local_base, anio_mes)
        if not os.path.exists(ruta_local_mes):
            os.makedirs(ruta_local_mes)

        grupos = lista_archivos.groupby('RutaRemota')

        for ruta_remota_base, grupo in grupos:
            ruta_remota_base = str(ruta_remota_base).strip()
            
            # Construcción ruta remota
            if ruta_remota_base.endswith("/"):
                ruta_remota_final = f"{ruta_remota_base}{anio_mes}"
            elif ruta_remota_base.endswith(anio_mes):
                ruta_remota_final = ruta_remota_base
            else:
                ruta_remota_final = f"{ruta_remota_base}/{anio_mes}"

            try:
                ftps.cwd(ruta_remota_final)
                archivos_en_servidor = ftps.nlst()
            except:
                # Si falla entrar a la carpeta, saltamos
                continue

            for _, row in grupo.iterrows():
                nombre_base = str(row['NombreBase']).strip()
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
                        if not nombre_archivo.startswith(nombre_base_lower):
                            continue
                        for dia in dias_permitidos:
                            if dia in nombre_archivo:
                                coincidencias.append(f)
                                break 

                for archivo in coincidencias:
                    nombre_limpio = os.path.basename(archivo)
                    ruta_destino = os.path.join(ruta_local_mes, nombre_limpio)

                    # Si existe y tiene datos, NO bajamos (Caching básico)
                    if os.path.exists(ruta_destino) and os.path.getsize(ruta_destino) > 0:
                        continue 
                    
                    if es_reintento:
                        print(f"   🔄 Restaurando: {nombre_limpio}")
                    else:
                        print(f"   ⬇️ Descargando: {nombre_limpio}")

                    try:
                        with open(ruta_destino, "wb") as local_file:
                            ftps.retrbinary(f"RETR {archivo}", local_file.write)
                        
                        if os.path.getsize(ruta_destino) == 0:
                            print(f"      ⚠️ Descarga fallida (0 bytes). Borrando...")
                            os.remove(ruta_destino)
                        else:
                            archivos_bajados += 1
                            
                    except Exception as e:
                        print(f"      ❌ Error descarga: {e}")
                        if os.path.exists(ruta_destino):
                            try: os.remove(ruta_destino)
                            except: pass

    try:
        ftps.quit()
    except:
        pass
    
    if es_reintento:
        print(f"✅ RECUPERACIÓN TERMINADA: Se descargaron {archivos_bajados} archivos.")
    else:
        print(f"✅ FASE 1 TERMINADA.")


# ==========================================
#  MÓDULO 2: BASE DE DATOS (LÓGICA CORREGIDA)
# ==========================================

def extraer_info_nombre(nombre_archivo):
    nombre_base, extension = os.path.splitext(nombre_archivo)
    extension = extension.replace(".", "")
    for especial in ARCHIVOS_MENSUALES:
        if nombre_base.upper().startswith(especial.upper()):
            nombre_tabla = especial
            fecha_resto = nombre_base[len(especial):] 
            return nombre_tabla, fecha_resto, extension
    match = re.search(r"\d", nombre_base)
    if match:
        nombre_tabla = nombre_base[:match.start()]
        fecha_mmdd = nombre_base[match.start():]
    else:
        nombre_tabla = nombre_base
        fecha_mmdd = "0000"
    return nombre_tabla, fecha_mmdd, extension

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
        tablas = cursor.fetchall()
        for (tabla,) in tablas:
            try:
                cursor.execute(f"PRAGMA table_info({tabla})")
                cols = [info[1] for info in cursor.fetchall()]
                if 'origen_archivo' in cols:
                    cursor.execute(f"SELECT DISTINCT origen_archivo FROM {tabla}")
                    archivos = cursor.fetchall()
                    for (archivo,) in archivos:
                        if archivo: cache.add(archivo)
            except: pass
    except Exception as e:
        print(f"   ⚠️ Error cargando caché: {e}")
    print(f"   🧠 Memoria lista: {len(cache)} archivos ya conocidos.")
    return cache

def proceso_base_datos(df_config, es_reintento=False):
    if es_reintento:
        print("\n--- 🔄 INICIANDO FASE DE PROCESAMIENTO (INTENTO #2) ---")
    else:
        print("\n--- INICIANDO FASE 2: ACTUALIZACIÓN DE BASE DE DATOS (MODO TURBO) ---")
    
    ruta_descargas = df_config.iloc[1, 3] 
    fecha_ini = df_config.iloc[1, 4] 
    fecha_fin = df_config.iloc[1, 5] 
    
    dias_permitidos, meses_permitidos = generar_fechas_permitidas(fecha_ini, fecha_fin)
    
    print(f"🔌 Conectando a BD: {NOMBRE_DB}")
    conn = sqlite3.connect(NOMBRE_DB)
    cursor = conn.cursor()
    
    archivos_procesados_cache = cargar_cache_archivos_existentes(cursor)
    
    print(f"📂 Escaneando archivos locales...")
    patron = os.path.join(ruta_descargas, "**", "*.tx*")
    archivos = glob.glob(patron, recursive=True)
    
    print(f"   🔍 Se encontraron {len(archivos)} archivos en disco. Filtrando...")

    guardados = 0
    corruptos_eliminados = 0
    
    for ruta_completa in archivos:
        nombre_archivo = os.path.basename(ruta_completa)
        
        # 1. Caché Check (Si ya está en BD, no nos importa si está corrupto o no, ya tenemos el dato)
        if nombre_archivo in archivos_procesados_cache:
            continue

        # 2. EXTRACT INFO & DATE CHECK (ESTO VA ANTES DE BORRAR NADA)
        #    Solo tocamos archivos que están en el rango solicitado en el Excel
        nombre_tabla, fecha_identificador, version = extraer_info_nombre(nombre_archivo)
        anio_carpeta = obtener_anio_de_carpeta(ruta_completa)
        
        es_valido = False
        if nombre_tabla in ARCHIVOS_MENSUALES:
            if f"{anio_carpeta}-{fecha_identificador}" in meses_permitidos: es_valido = True
        else:
            if fecha_identificador in dias_permitidos: es_valido = True

        # SI NO ES VÁLIDO (FUERA DE RANGO), LO IGNORAMOS (AUNQUE ESTÉ VACÍO)
        if not es_valido:
            continue

        # 3. VALIDACIÓN DE INTEGRIDAD (Ahora solo revisamos los válidos)
        archivo_corrupto = False
        razon_corrupcion = ""

        if os.path.getsize(ruta_completa) == 0:
            archivo_corrupto = True
            razon_corrupcion = "0 bytes"
        
        if not archivo_corrupto:
            try:
                # Leemos cabecera para ver si tiene datos reales
                pd.read_csv(ruta_completa, sep=';', nrows=1, encoding='latin-1', on_bad_lines='skip', engine='python')
            except pd.errors.EmptyDataError:
                archivo_corrupto = True
                razon_corrupcion = "Sin datos/columnas"
            except Exception:
                pass

        if archivo_corrupto:
            # --- AUTORREPARACIÓN ---
            print(f"   🗑️ Corrupto detectado ({razon_corrupcion}): {nombre_archivo} -> ELIMINADO PARA RE-DESCARGA")
            try:
                os.remove(ruta_completa)
                time.sleep(0.5) # Pequeña pausa para Box Sync/Windows
                corruptos_eliminados += 1
            except Exception as e:
                print(f"      ❌ No se pudo eliminar: {e}")
            continue
            
        # 4. Ingesta Real
        try:
            df = pd.read_csv(ruta_completa, sep=';', decimal='.', encoding='latin-1', on_bad_lines='skip', engine='python')
            
            if df.empty:
                print(f"   🗑️ DataFrame vacío: {nombre_archivo} -> ELIMINADO PARA RE-DESCARGA")
                os.remove(ruta_completa)
                corruptos_eliminados += 1
                continue

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
            print(f"   ⚠️ Error leyendo {nombre_archivo}: {e}")

    conn.close()
    
    print(f"✅ FASE {'2' if not es_reintento else 'RECUPERACIÓN'} TERMINADA.")
    print(f"   📥 Insertados: {guardados}")
    
    if corruptos_eliminados > 0:
        print(f"   🧹 Se eliminaron {corruptos_eliminados} archivos corruptos DENTRO DEL RANGO.")
        return True 
    else:
        return False

def main():
    print(f"🚀 INICIANDO SISTEMA XM (Versión Auto-Reparable Segura)")
    try:
        df_config = pd.read_excel(ARCHIVO_EXCEL, sheet_name=HOJA_NOMBRE, header=None, engine='openpyxl')
    except Exception as e:
        print(f"❌ Error crítico leyendo Excel: {e}")
        input("Enter para salir...")
        return

    # 1. Primera Pasada Normal
    try:
        proceso_descarga(df_config)
    except Exception as e: print(f"❌ Error en Descarga: {e}")

    try:
        necesita_reparacion = proceso_base_datos(df_config)
        
        # 2. Lógica de Auto-Reparación
        if necesita_reparacion:
            print("\n" + "="*60)
            print("⚠️ ALERTA: SE DETECTARON ARCHIVOS CORRUPTOS EN EL RANGO.")
            print("🤖 INTENTANDO RECUPERARLOS...")
            print("="*60)
            time.sleep(2) 
            
            # Reintentar Descarga
            proceso_descarga(df_config, es_reintento=True)
            
            # Reintentar Base de Datos
            proceso_base_datos(df_config, es_reintento=True)
            
            print("\n✨ CICLO DE AUTORREPARACIÓN FINALIZADO.")

    except Exception as e:
        print(f"❌ Error en Base de Datos: {e}")

    print("\n🏁 PROCESO FINALIZADO.")
    input("Presiona Enter para cerrar...")

if __name__ == "__main__":
    main()
