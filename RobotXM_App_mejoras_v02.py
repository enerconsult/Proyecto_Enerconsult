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
except ImportError:
    TIENE_PILLOW = False

# Import UI helpers (new module in this PR)
from RobotXM_ui_improvements import Card, RoundedButtonWrapper

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
    "Verde Corporativo": "#6E9D2F",
    "Azul Corporativo": "#0088C2",
    "Rojo Intenso": "#e74c3c",
    "Naranja": "#f39c12",
    "Morado": "#9b59b6",
    "Negro": "#000000"
}

import logging
import logging.handlers

# --- CONFIGURACIÓN DE LOGGING ---
def setup_logging():
    logger = logging.getLogger("RobotXM")
    logger.setLevel(logging.INFO)
    
    # Formato
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    
    # Handler Archivo (Rotativo 5MB x 3 backups)
    fh = logging.handlers.RotatingFileHandler("robot_xm.log", maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    # Handler Consola (Para que PrintRedirector lo capture)
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
        try:
            str_val = str(str_val) # Enforce string
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, str_val)
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
            self.text_widget.update_idletasks()
        except tk.TclError:
            pass # Widget destroyed
        except Exception:
            pass # Ignorar otros errores de UI logging

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

# --- IMPORTS ADICIONALES PARA RED ---
# (Ya importados al inicio)

# =============================================================================
#  MÓDULO DE OPTIMIZACIÓN Y HELPER FUNCTIONS
# =============================================================================

def safe_identifier(name: str) -> str:
    """Valida que el nombre de tabla/columna sea seguro (alfanumérico + guiones bajos)."""
    if not re.match(r'^[A-Za-z0-9_]+$', str(name)):
        raise ValueError(f"Identificador inválido (posible inyección SQL): {name}")
    return name

# (rest of file is unchanged...)
