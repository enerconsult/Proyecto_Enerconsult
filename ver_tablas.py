import sqlite3
import os
import sys
import pandas as pd

# Detectar la ruta correcta si se ejecuta como script o como ejecutable congelado
if getattr(sys, 'frozen', False):
    app_path = os.path.dirname(sys.executable)
else:
    app_path = os.path.dirname(os.path.abspath(__file__))

NOMBRE_DB = os.path.join(app_path, "BaseDatosXM.db")

def analizar_estructura():
    print(f"🕵️  AUDITOR DE ESTRUCTURA DE BASE DE DATOS: {NOMBRE_DB}")
    print("=" * 60)
    
    if not os.path.exists(NOMBRE_DB):
        print("❌ Error: No encuentro el archivo BaseDatosXM.db")
        return

    conn = sqlite3.connect(NOMBRE_DB)
    cursor = conn.cursor()
    
    # 1. Obtener lista de todas las tablas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tablas = cursor.fetchall()
    
    if not tablas:
        print("⚠️  La base de datos está vacía (no tiene tablas).")
        conn.close()
        return

    print(f"📊  Se encontraron {len(tablas)} tablas. Analizando detalle...\n")

    # 2. Iterar sobre cada tabla para ver sus columnas y filas
    for i, t in enumerate(tablas, 1):
        nombre_tabla = t[0]
        
        # Obtener información de las columnas (PRAGMA table_info devuelve: id, nombre, tipo, notnull, dflt_value, pk)
        cursor.execute(f"PRAGMA table_info('{nombre_tabla}')")
        info_columnas = cursor.fetchall()
        
        # Contar filas totales
        cursor.execute(f"SELECT COUNT(*) FROM '{nombre_tabla}'")
        num_filas = cursor.fetchone()[0]
        
        num_columnas = len(info_columnas)
        nombres_columnas = [col[1] for col in info_columnas] # La posición 1 es el nombre

        # 3. Imprimir reporte de la tabla
        print(f"🔹 TABLA {i}: [{nombre_tabla}]")
        print(f"   • Dimensiones: {num_filas} filas x {num_columnas} columnas")
        print(f"   • Columnas detectadas:")
        
        # Imprimir columnas en formato de lista compacta
        print(f"     {nombres_columnas}")
        
        # Validación rápida para tu reporte (Ej: ¿Tiene estructura estándar?)
        # Esto te ayuda a ver si alguna tabla "rara" se coló
        if num_columnas < 5: 
            print("   ⚠️  ADVERTENCIA: Esta tabla tiene muy pocas columnas, verificar.")
        
        print("-" * 60)

    conn.close()
    input("\n✅ Análisis finalizado. Presiona Enter para cerrar...")

if __name__ == "__main__":
    analizar_estructura()
