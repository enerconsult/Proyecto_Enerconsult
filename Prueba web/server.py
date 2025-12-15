"""
API REST para Suite XM - Backend Python
Conecta la aplicación web React con la lógica de negocio Python
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import os
import sqlite3
import pandas as pd
from datetime import datetime
import threading

app = Flask(__name__)
CORS(app)  # Permitir requests desde el frontend React

# Configuración
CONFIG_FILE = "config_app.json"
DB_FILE = "BaseDatosXM.db"
REPORT_FILE = "Reporte_Horizontal_XM.xlsx"

# ============================================================================
# ENDPOINTS DE CONFIGURACIÓN
# ============================================================================

@app.route('/api/config', methods=['GET'])
def get_config():
    """Obtiene la configuración actual"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        else:
            config = {
                'usuario': '',
                'password': '',
                'ruta_local': '/datos/xm',
                'fecha_ini': '2025-01-01',
                'fecha_fin': '2025-01-31',
                'archivos_descarga': [],
                'filtros_reporte': []
            }
        
        # Agregar stats de la BD
        db_stats = get_database_stats(config.get('ruta_local', '.'))
        
        return jsonify({
            'success': True,
            'config': config,
            'dbStats': db_stats
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config', methods=['POST'])
def save_config():
    """Guarda la configuración"""
    try:
        data = request.json
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        
        return jsonify({
            'success': True,
            'message': 'Configuración guardada exitosamente'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def get_database_stats(ruta_local):
    """Obtiene estadísticas de la base de datos"""
    db_path = os.path.join(ruta_local, DB_FILE)
    
    if os.path.exists(db_path):
        size_mb = os.path.getsize(db_path) / (1024 * 1024)
        mtime = datetime.fromtimestamp(os.path.getmtime(db_path))
        
        return {
            'exists': True,
            'size': f'{size_mb:.2f} MB',
            'lastUpdate': mtime.strftime('%Y-%m-%d %H:%M')
        }
    else:
        return {
            'exists': False,
            'size': '0 MB',
            'lastUpdate': '--'
        }


# ============================================================================
# ENDPOINTS DE ARCHIVOS
# ============================================================================

@app.route('/api/files', methods=['GET'])
def get_files():
    """Obtiene la lista de archivos configurados"""
    try:
        config = load_config()
        return jsonify({
            'success': True,
            'files': config.get('archivos_descarga', [])
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/files', methods=['POST'])
def add_file():
    """Agrega un archivo a la configuración"""
    try:
        config = load_config()
        new_file = request.json
        
        if 'archivos_descarga' not in config:
            config['archivos_descarga'] = []
        
        config['archivos_descarga'].append(new_file)
        save_config_data(config)
        
        return jsonify({
            'success': True,
            'message': 'Archivo agregado'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/files/<int:index>', methods=['DELETE'])
def delete_file(index):
    """Elimina un archivo de la configuración"""
    try:
        config = load_config()
        
        if 0 <= index < len(config.get('archivos_descarga', [])):
            del config['archivos_descarga'][index]
            save_config_data(config)
            
            return jsonify({
                'success': True,
                'message': 'Archivo eliminado'
            })
        else:
            return jsonify({'success': False, 'error': 'Índice inválido'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ENDPOINTS DE FILTROS
# ============================================================================

@app.route('/api/filters', methods=['GET'])
def get_filters():
    """Obtiene la lista de filtros configurados"""
    try:
        config = load_config()
        return jsonify({
            'success': True,
            'filters': config.get('filtros_reporte', [])
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/filters', methods=['POST'])
def add_filter():
    """Agrega un filtro a la configuración"""
    try:
        config = load_config()
        new_filter = request.json
        
        if 'filtros_reporte' not in config:
            config['filtros_reporte'] = []
        
        config['filtros_reporte'].append(new_filter)
        save_config_data(config)
        
        return jsonify({
            'success': True,
            'message': 'Filtro agregado'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/filters/<int:index>', methods=['DELETE'])
def delete_filter(index):
    """Elimina un filtro de la configuración"""
    try:
        config = load_config()
        
        if 0 <= index < len(config.get('filtros_reporte', [])):
            del config['filtros_reporte'][index]
            save_config_data(config)
            
            return jsonify({
                'success': True,
                'message': 'Filtro eliminado'
            })
        else:
            return jsonify({'success': False, 'error': 'Índice inválido'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/filters/reorder', methods=['POST'])
def reorder_filters():
    """Reordena los filtros"""
    try:
        config = load_config()
        new_order = request.json.get('filters', [])
        
        config['filtros_reporte'] = new_order
        save_config_data(config)
        
        return jsonify({
            'success': True,
            'message': 'Filtros reordenados'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ENDPOINTS DE PROCESAMIENTO
# ============================================================================

@app.route('/api/download', methods=['POST'])
def execute_download():
    """Ejecuta el proceso de descarga y actualización de BD"""
    try:
        # Aquí importarías y ejecutarías tu lógica existente
         from robot_xm import proceso_descarga, proceso_base_datos
        
        # Por ahora, simular el proceso en background
        def run_download():
            import time
             config = load_config()
             proceso_descarga(config)
             proceso_base_datos(config)
            time.sleep(2)  # Simular procesamiento
        
        # Ejecutar en thread separado para no bloquear
        thread = threading.Thread(target=run_download)
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Proceso de descarga iniciado'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/report', methods=['POST'])
def generate_report():
    """Genera el reporte Excel"""
    try:
        # Aquí importarías y ejecutarías tu lógica existente
         from robot_xm import generar_reporte_logica
        
         config = load_config()
         generar_reporte_logica(config)
        
        return jsonify({
            'success': True,
            'message': 'Reporte generado exitosamente',
            'file': REPORT_FILE
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ENDPOINTS DEL VISUALIZADOR
# ============================================================================

@app.route('/api/visualizer/tables', methods=['GET'])
def get_tables():
    """Obtiene la lista de tablas disponibles en la BD"""
    try:
        config = load_config()
        db_path = os.path.join(config.get('ruta_local', '.'), DB_FILE)
        
        if not os.path.exists(db_path):
            return jsonify({'success': False, 'error': 'Base de datos no encontrada'}), 404
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'tables': sorted(tables)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/visualizer/columns/<table>', methods=['GET'])
def get_table_columns(table):
    """Obtiene las columnas de una tabla"""
    try:
        config = load_config()
        db_path = os.path.join(config.get('ruta_local', '.'), DB_FILE)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        
        # Filtrar columnas meta
        ignored = ['index', 'anio', 'mes_dia', 'version_dato', 'origen_archivo', 'fecha_carga']
        columns = [c for c in columns if c not in ignored]
        
        return jsonify({
            'success': True,
            'columns': columns
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/visualizer/values/<table>/<column>', methods=['GET'])
def get_column_values(table, column):
    """Obtiene los valores únicos de una columna"""
    try:
        config = load_config()
        db_path = os.path.join(config.get('ruta_local', '.'), DB_FILE)
        
        conn = sqlite3.connect(db_path)
        query = f"SELECT DISTINCT {column} FROM {table} ORDER BY {column} LIMIT 1000"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        values = df[column].astype(str).tolist()
        
        return jsonify({
            'success': True,
            'values': values
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/visualizer/data', methods=['POST'])
def get_chart_data():
    """Obtiene los datos para graficar"""
    try:
        params = request.json
        config = load_config()
        db_path = os.path.join(config.get('ruta_local', '.'), DB_FILE)
        
        if not os.path.exists(db_path):
            return jsonify({'success': False, 'error': 'Base de datos no encontrada'}), 404
        
        # Construir query
        tabla = params.get('tabla')
        campo_filtro1 = params.get('filtro1Campo')
        valor_filtro1 = params.get('filtro1Valor')
        fecha_ini = params.get('fechaInicio')
        fecha_fin = params.get('fechaFin')
        variable = params.get('variable')
        
        query = f"SELECT * FROM {tabla} WHERE 1=1"
        
        if campo_filtro1 and valor_filtro1:
            query += f" AND {campo_filtro1} = '{valor_filtro1}'"
        
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return jsonify({'success': False, 'error': 'No hay datos'}), 404
        
        # Procesar fechas
        df['Fecha'] = pd.to_datetime(
            df['anio'].astype(str) + '-' + 
            df['mes_dia'].astype(str).str.zfill(4).str[:2] + '-' +
            df['mes_dia'].astype(str).str.zfill(4).str[2:],
            errors='coerce'
        )
        
        df = df.dropna(subset=['Fecha'])
        
        # Filtrar por rango
        if fecha_ini:
            df = df[df['Fecha'] >= fecha_ini]
        if fecha_fin:
            df = df[df['Fecha'] <= fecha_fin]
        
        # Agrupar y calcular
        if variable and variable in df.columns:
            df[variable] = pd.to_numeric(df[variable], errors='coerce')
            result = df.groupby('Fecha')[variable].mean().reset_index()
            result.columns = ['date', 'value']
            result['date'] = result['date'].dt.strftime('%Y-%m-%d')
            
            data = result.to_dict('records')
            
            # Calcular estadísticas
            stats = {
                'promedio': float(result['value'].mean()),
                'max': float(result['value'].max()),
                'min': float(result['value'].min()),
                'suma': float(result['value'].sum())
            }
            
            return jsonify({
                'success': True,
                'data': data,
                'stats': stats
            })
        else:
            return jsonify({'success': False, 'error': 'Variable no encontrada'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# UTILIDADES
# ============================================================================

def load_config():
    """Carga la configuración desde el archivo"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_config_data(config):
    """Guarda la configuración en el archivo"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)


# ============================================================================
# EJECUTAR SERVIDOR
# ============================================================================

if __name__ == '__main__':
    print("🚀 Servidor API iniciado en http://localhost:5000")
    print("📡 Endpoints disponibles:")
    print("   - GET  /api/config")
    print("   - POST /api/config")
    print("   - GET  /api/files")
    print("   - POST /api/download")
    print("   - POST /api/report")
    print("   - POST /api/visualizer/data")
    print("")
    app.run(debug=True, port=5000)
