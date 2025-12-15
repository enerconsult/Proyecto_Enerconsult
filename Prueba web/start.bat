@echo off
REM =============================================================================
REM Script de inicio rápido para Suite XM - Backend Python (Windows)
REM =============================================================================

echo.
echo ========================================
echo   Suite XM Backend - Iniciando...
echo ========================================
echo.

REM Verificar que Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado
    echo         Instala Python 3.8+ desde https://www.python.org/
    pause
    exit /b 1
)

echo [OK] Python encontrado
python --version

REM Verificar si existe un entorno virtual
if not exist "venv" (
    echo.
    echo [INFO] Creando entorno virtual...
    python -m venv venv
    
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual
        pause
        exit /b 1
    )
    
    echo [OK] Entorno virtual creado
)

REM Activar entorno virtual
echo.
echo [INFO] Activando entorno virtual...
call venv\Scripts\activate.bat

REM Instalar dependencias
if not exist "venv\.dependencies_installed" (
    echo.
    echo [INFO] Instalando dependencias...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    
    if not errorlevel 1 (
        echo. > venv\.dependencies_installed
        echo [OK] Dependencias instaladas
    ) else (
        echo [ERROR] Error instalando dependencias
        pause
        exit /b 1
    )
) else (
    echo [OK] Dependencias ya instaladas
)

REM Verificar archivos necesarios
echo.
echo [INFO] Verificando archivos...

if not exist "server.py" (
    echo [ERROR] server.py no encontrado
    pause
    exit /b 1
)

if not exist "config_app.json" (
    echo [WARN] config_app.json no encontrado. Creando valores por defecto...
    (
        echo {
        echo   "usuario": "",
        echo   "password": "",
        echo   "ruta_local": "./datos",
        echo   "fecha_ini": "2025-01-01",
        echo   "fecha_fin": "2025-01-31",
        echo   "archivos_descarga": [],
        echo   "filtros_reporte": []
        echo }
    ) > config_app.json
    echo [OK] config_app.json creado
)

REM Crear directorio de datos si no existe
if not exist "datos" (
    mkdir datos
    echo [OK] Directorio de datos creado
)

echo.
echo ========================================
echo   Suite XM Backend - LISTO
echo ========================================
echo.
echo Servidor disponible en:
echo   http://localhost:5000
echo.
echo Endpoints disponibles:
echo   GET  /api/config
echo   POST /api/config
echo   POST /api/download
echo   POST /api/report
echo   POST /api/visualizer/data
echo.
echo Para detener: Ctrl+C
echo.
echo ========================================
echo.

REM Iniciar servidor
python server.py

pause
