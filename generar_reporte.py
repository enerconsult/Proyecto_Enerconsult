import sqlite3
import pandas as pd
import os
import sys
import re

# --- CONFIGURACIÓN ---
if getattr(sys, 'frozen', False):
    app_path = os.path.dirname(sys.executable)
else:
    app_path = os.path.dirname(os.path.abspath(__file__))

NOMBRE_DB = os.path.join(app_path, "BaseDatosXM.db")
CONFIG_EXCEL = os.path.join(app_path, "GeneradorDeReportes.xlsm")
REPORTE_SALIDA = os.path.join(app_path, "Reporte_Horizontal_XM.xlsx")
NOMBRE_HOJA_UNICA = "Datos_Consolidados"

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

def generar_reporte():
    print("🚀 INICIANDO GENERADOR HORIZONTAL XM (Multi-Filtro Corregido)")
    
    # 1. Leer Configuración
    try:
        print(f"📖 Leyendo configuración: {CONFIG_EXCEL}")
        df_params = pd.read_excel(CONFIG_EXCEL, header=None, engine='openpyxl', sheet_name=0)
        
        if df_params.empty or df_params.shape[0] < 2:
            print("\n❌ ERROR: Excel de configuración vacío.")
            return

        try:
            val_ini = df_params.iloc[1, 1] 
            val_fin = df_params.iloc[1, 2] 
            fecha_ini = pd.to_datetime(val_ini)
            fecha_fin = pd.to_datetime(val_fin)
        except:
            print("\n❌ ERROR: No se pudieron leer las fechas en B2 y C2.")
            return

        print(f"📅 Rango detectado: {fecha_ini.date()} al {fecha_fin.date()}")

        filtros_raw = df_params.iloc[5:, [0, 1, 2]]
        filtros_raw.columns = ['tabla', 'campo', 'valor']
        filtros_raw = filtros_raw.dropna(subset=['tabla']) 
        
        # --- CAMBIO IMPORTANTE AQUÍ ---
        # En lugar de un diccionario que sobrescribe, usamos una lista de tareas.
        tareas_a_procesar = []
        
        for _, row in filtros_raw.iterrows():
            tbl = str(row['tabla']).strip()
            campo_raw = row['campo']
            valor_raw = row['valor']
            
            # Creamos un "paquete de tarea" con toda la info necesaria para esa fila
            tarea = {
                'tabla_solicitada': tbl,
                'filtro_campo': str(campo_raw).strip() if pd.notna(campo_raw) else None,
                'filtro_valor': str(valor_raw).strip() if pd.notna(valor_raw) else None
            }
            tareas_a_procesar.append(tarea)
        # ------------------------------
                
    except Exception as e:
        print(f"      ❌ ERROR LEYENDO EXCEL: {e}")
        return

    # 2. Conectar a BD
    if not os.path.exists(NOMBRE_DB):
        print(f"❌ No existe la BD: {NOMBRE_DB}")
        return

    conn = sqlite3.connect(NOMBRE_DB)
    cursor = conn.cursor()

    # 3. Procesar
    print(f"\n⚙️ Generando reporte horizontal...")
    
    try:
        with pd.ExcelWriter(REPORTE_SALIDA, engine='openpyxl') as writer:
            
            columna_actual = 0  
            tablas_escritas = 0
            
            # --- CAMBIO: Iteramos sobre la lista de tareas ---
            for tarea in tareas_a_procesar:
                tabla_solicitada = tarea['tabla_solicitada']
                col_filtro_usuario = tarea['filtro_campo']
                val_filtro_usuario = tarea['filtro_valor']
                
                # --- BÚSQUEDA INTELIGENTE DE NOMBRE ---
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND lower(name)='{tabla_solicitada.lower()}'")
                resultado = cursor.fetchone()
                
                if not resultado:
                    print(f"   ⚠️ Tabla '{tabla_solicitada}' no encontrada en BD.")
                    continue
                
                nombre_real_bd = resultado[0]
                
                # --- CONSTRUCCIÓN DE CONSULTA SQL OPTIMIZADA ---
                query = f"SELECT * FROM {nombre_real_bd}"
                
                # Verificamos si ESTA tarea específica tiene filtro
                if col_filtro_usuario and val_filtro_usuario:
                    
                    # Verificamos si la columna existe en la BD
                    cursor.execute(f"PRAGMA table_info({nombre_real_bd})")
                    columnas_bd = cursor.fetchall()
                    
                    nombre_columna_real = None
                    for col_info in columnas_bd:
                        if col_info[1].lower() == col_filtro_usuario.lower():
                            nombre_columna_real = col_info[1]
                            break
                    
                    if nombre_columna_real:
                        print(f"   🔹 Procesando: {nombre_real_bd} (Filtrando por {nombre_columna_real}={val_filtro_usuario})")
                        # Aplicamos el filtro SQL para esta tarea única
                        query += f" WHERE CAST({nombre_columna_real} AS TEXT) = '{val_filtro_usuario}'"
                    else:
                        print(f"   🔹 Procesando: {nombre_real_bd} (⚠️ Campo '{col_filtro_usuario}' no existe, descargando todo...)")
                else:
                    print(f"   🔹 Procesando: {nombre_real_bd} (Sin filtro SQL)...")

                try:
                    df = pd.read_sql_query(query, conn)
                    
                    if df.empty:
                        print(f"      (Sin datos tras el filtro SQL)")
                        continue

                    # Construir Fecha
                    def armar_fecha(row):
                        try:
                            anio = str(row['anio'])
                            md = str(row['mes_dia']).zfill(4)
                            if len(str(row['mes_dia'])) <= 2: 
                                 return pd.to_datetime(f"{anio}-{str(row['mes_dia']).zfill(2)}-01")
                            else:
                                 mes = md[:2]
                                 dia = md[2:]
                                 return pd.to_datetime(f"{anio}-{mes}-{dia}")
                        except:
                            return pd.NaT

                    df['Fecha'] = df.apply(armar_fecha, axis=1)
                    # Mover fecha al principio de forma segura
                    cols = ['Fecha'] + [c for c in df.columns if c != 'Fecha']
                    df = df[cols]

                    # Filtro Rango de Fechas
                    df = df[(df['Fecha'] >= fecha_ini) & (df['Fecha'] <= fecha_fin)]
                    
                    if df.empty:
                        print(f"      (Sin datos en rango de fechas)")
                        continue

                    # Ranking Versiones
                    df['peso_version'] = df['version_dato'].apply(calcular_peso_version)
                    df['max_peso_dia'] = df.groupby('Fecha')['peso_version'].transform('max')
                    df_final = df[df['peso_version'] == df['max_peso_dia']].copy()
                    
                    # Ordenar y Limpiar
                    df_final = df_final.sort_values(by='Fecha', ascending=True)
                    cols_borrar = ['peso_version', 'max_peso_dia', 'origen_archivo', 'anio', 'mes_dia', 'fecha_carga']
                    df_final = df_final.drop(columns=[c for c in cols_borrar if c in df_final.columns], errors='ignore')
                    
                    # --- ESCRITURA HORIZONTAL ---
                    # Creamos un título dinámico que muestre el filtro si existe
                    titulo_texto = f"ARCHIVO: {tabla_solicitada.upper()}"
                    if col_filtro_usuario and val_filtro_usuario:
                        titulo_texto += f" (Filtro: {val_filtro_usuario})"
                        
                    titulo = pd.DataFrame({titulo_texto: []})
                    titulo.to_excel(writer, sheet_name=NOMBRE_HOJA_UNICA, 
                                    startrow=0, startcol=columna_actual, index=False)
                    
                    df_final.to_excel(writer, sheet_name=NOMBRE_HOJA_UNICA, 
                                      startrow=1, startcol=columna_actual, index=False)
                    
                    ancho_tabla = len(df_final.columns)
                    columna_actual += ancho_tabla + 1 
                    
                    tablas_escritas += 1
                    
                except Exception as e:
                    print(f"      ❌ Error interno procesando tabla: {e}")

        conn.close()
        
        if tablas_escritas > 0:
            print(f"\n✅ REPORTE HORIZONTAL LISTO: {REPORTE_SALIDA}")
        else:
            print("\n⚠️ No se generaron datos. (Verifica filtros o descargas)")

    except Exception as e:
        print(f"❌ Error guardando Excel general: {e}")
        if "Permission denied" in str(e):
            print("💡 Cierra el archivo Excel si lo tienes abierto.")
            
    input("Presiona Enter para cerrar...")

if __name__ == "__main__":
    generar_reporte()
