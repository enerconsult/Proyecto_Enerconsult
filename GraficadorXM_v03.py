import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sqlite3
import pandas as pd
import os
import matplotlib
import re
from datetime import datetime

# Configurar matplotlib para incrustarse en Tkinter
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.dates as mdates

class ModuloVisualizador:
    def __init__(self, root):
        self.root = root
        self.root.title("Módulo de Inteligencia Visual XM - Soporte 24 Horas")
        self.root.geometry("1100x850") 
        
        # Ruta de la BD
        self.ruta_db = "BaseDatosXM.db"
        
        # --- VARIABLES DE CONTROL ---
        self.var_tabla = tk.StringVar()
        self.var_campo_filtro = tk.StringVar()
        self.var_valor_filtro = tk.StringVar()
        self.var_campo_valor = tk.StringVar()
        self.var_agregacion = tk.StringVar(value="Promedio")
        
        # Variables para fechas
        self.var_fecha_ini = tk.StringVar()
        self.var_fecha_fin = tk.StringVar()
        
        # Variable para controlar el modo 24h
        self.var_es_horario = tk.BooleanVar(value=False)

        # --- LAYOUT PRINCIPAL ---
        # 1. Panel Superior
        frame_top = ttk.Frame(root, padding=10)
        frame_top.pack(fill="x")
        ttk.Label(frame_top, text="Base de Datos:").pack(side="left")
        self.lbl_db = ttk.Entry(frame_top, width=60)
        self.lbl_db.pack(side="left", padx=5)
        self.lbl_db.insert(0, os.path.abspath(self.ruta_db))
        ttk.Button(frame_top, text="📂 Cambiar", command=self.seleccionar_db).pack(side="left")
        ttk.Button(frame_top, text="🔄 Conectar", command=self.cargar_tablas).pack(side="left", padx=5)

        # 2. Panel de Configuración
        frame_cfg = ttk.LabelFrame(root, text="Configuración de Variables", padding=10)
        frame_cfg.pack(fill="x", padx=10, pady=5)

        # Fila 0
        ttk.Label(frame_cfg, text="1. Archivo (Tabla):").grid(row=0, column=0, sticky="w", pady=5)
        self.cb_tabla = ttk.Combobox(frame_cfg, textvariable=self.var_tabla, state="readonly", width=25)
        self.cb_tabla.grid(row=0, column=1, padx=5, pady=5)
        self.cb_tabla.bind("<<ComboboxSelected>>", self.al_seleccionar_tabla)

        ttk.Label(frame_cfg, text="2. Campo Clasificador:").grid(row=0, column=2, sticky="w", padx=10)
        self.cb_campo_filtro = ttk.Combobox(frame_cfg, textvariable=self.var_campo_filtro, state="readonly", width=25)
        self.cb_campo_filtro.grid(row=0, column=3, padx=5)
        self.cb_campo_filtro.bind("<<ComboboxSelected>>", self.al_seleccionar_campo_filtro)

        # Fila 1
        ttk.Label(frame_cfg, text="3. Variable Específica:").grid(row=1, column=0, sticky="w", pady=5)
        self.cb_valor_filtro = ttk.Combobox(frame_cfg, textvariable=self.var_valor_filtro, state="readonly", width=25)
        self.cb_valor_filtro.grid(row=1, column=1, padx=5, pady=5)

        # CHECKBOX 24 HORAS
        self.chk_horario = ttk.Checkbutton(frame_cfg, text="Es Variable Horaria (24 cols)", variable=self.var_es_horario, command=self.toggle_campo_valor)
        self.chk_horario.grid(row=1, column=2, columnspan=2, sticky="w", padx=10)

        # Fila 2
        self.lbl_valor = ttk.Label(frame_cfg, text="4. Columna Valor Único:")
        self.lbl_valor.grid(row=2, column=0, sticky="w", pady=5)
        
        self.cb_campo_valor = ttk.Combobox(frame_cfg, textvariable=self.var_campo_valor, state="readonly", width=25)
        self.cb_campo_valor.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(frame_cfg, text="5. Operación Matemática:").grid(row=2, column=2, sticky="w", padx=10)
        self.cb_agregacion = ttk.Combobox(frame_cfg, textvariable=self.var_agregacion, state="readonly", width=25)
        self.cb_agregacion['values'] = ["Promedio", "Suma", "Máximo", "Mínimo"]
        self.cb_agregacion.current(0)
        self.cb_agregacion.grid(row=2, column=3, padx=5)

        # Fila 3: Filtros de Fecha
        ttk.Label(frame_cfg, text="Fecha Inicio (YYYY-MM-DD):").grid(row=3, column=0, sticky="w", pady=5)
        self.ent_fecha_ini = ttk.Entry(frame_cfg, textvariable=self.var_fecha_ini, width=25)
        self.ent_fecha_ini.grid(row=3, column=1, padx=5)
        self.ent_fecha_ini.insert(0, "2020-01-01") 

        ttk.Label(frame_cfg, text="Fecha Fin (YYYY-MM-DD):").grid(row=3, column=2, sticky="w", padx=10)
        self.ent_fecha_fin = ttk.Entry(frame_cfg, textvariable=self.var_fecha_fin, width=25)
        self.ent_fecha_fin.grid(row=3, column=3, padx=5)
        self.ent_fecha_fin.insert(0, datetime.today().strftime('%Y-%m-%d')) 

        # Botón Graficar
        ttk.Button(frame_cfg, text="📊 GENERAR VISUALIZACIÓN", command=self.generar_grafico).grid(row=4, column=0, columnspan=4, pady=15, sticky="ew")

        # 3. Área de Gráfico
        self.frame_plot = ttk.Frame(root)
        self.frame_plot.pack(fill="both", expand=True, padx=10, pady=10)
        
        if os.path.exists(self.ruta_db):
            self.cargar_tablas()

    # --- LÓGICA DE INTERFAZ ---
    def toggle_campo_valor(self):
        if self.var_es_horario.get():
            self.cb_campo_valor.configure(state="disabled")
            self.lbl_valor.configure(text="4. (Modo 24 Horas Activo)")
        else:
            self.cb_campo_valor.configure(state="readonly")
            self.lbl_valor.configure(text="4. Columna Valor Único:")

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
        conn.close()
        
        cols = [c[1] for c in info]
        
        cols_horarias = [str(i) for i in range(24)]
        es_horario = all(h in cols for h in cols_horarias)
        
        self.var_es_horario.set(es_horario)
        self.toggle_campo_valor()
        
        ignorar = ['index', 'anio', 'mes_dia', 'version_dato', 'origen_archivo', 'fecha_carga'] + cols_horarias
        candidatos = [c for c in cols if c.lower() not in ignorar]
        
        self.cb_campo_filtro['values'] = candidatos
        self.cb_campo_valor['values'] = candidatos
        
        if 'codigo' in candidatos: self.cb_campo_filtro.set('codigo')
        elif 'tipo' in candidatos: self.cb_campo_filtro.set('tipo')
        else: self.cb_campo_filtro.set('')
        
        if self.cb_campo_filtro.get(): self.al_seleccionar_campo_filtro(None)

    def al_seleccionar_campo_filtro(self, event):
        tabla = self.var_tabla.get()
        campo = self.var_campo_filtro.get()
        if not tabla or not campo: return
        try:
            conn = self.conectar()
            df = pd.read_sql_query(f"SELECT DISTINCT {campo} FROM {tabla} ORDER BY {campo}", conn)
            conn.close()
            vals = df[campo].astype(str).tolist()
            self.cb_valor_filtro['values'] = vals
            if vals: self.cb_valor_filtro.current(0)
        except: pass

    # --- LÓGICA CORE DE GRAFICACIÓN ---
    def generar_grafico(self):
        tabla = self.var_tabla.get()
        campo_filtro = self.var_campo_filtro.get()
        valor_filtro = self.var_valor_filtro.get()
        operacion = self.var_agregacion.get()
        es_24h = self.var_es_horario.get()
        
        # Obtener Fechas
        f_ini_str = self.var_fecha_ini.get()
        f_fin_str = self.var_fecha_fin.get()
        
        if not tabla: return

        try:
            conn = self.conectar()
            query = f"SELECT * FROM {tabla}"
            if campo_filtro and valor_filtro:
                query += f" WHERE CAST({campo_filtro} AS TEXT) = '{valor_filtro}'"
            
            print(f"Leyendo datos: {query}")
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                messagebox.showinfo("Vacío", "No hay datos con esos filtros.")
                return

            # Procesar Fechas
            def armar_fecha(row):
                try:
                    anio = str(row['anio'])
                    md = str(row['mes_dia']).zfill(4)
                    if len(str(row['mes_dia'])) <= 2: 
                         return pd.to_datetime(f"{anio}-{str(row['mes_dia']).zfill(2)}-01")
                    else:
                         return pd.to_datetime(f"{anio}-{md[:2]}-{md[2:]}")
                except: return pd.NaT

            df['Fecha'] = df.apply(armar_fecha, axis=1)
            df = df.dropna(subset=['Fecha'])

            # Filtros de Fecha
            try:
                if f_ini_str:
                    f_ini = pd.to_datetime(f_ini_str)
                    df = df[df['Fecha'] >= f_ini]
                if f_fin_str:
                    f_fin = pd.to_datetime(f_fin_str)
                    df = df[df['Fecha'] <= f_fin]
                
                if df.empty:
                    messagebox.showwarning("Fechas", "No hay datos en el rango de fechas seleccionado.")
                    return
            except Exception as e:
                messagebox.showerror("Error Fechas", f"Formato de fecha inválido. Use YYYY-MM-DD.\n{e}")
                return
            
            # Cálculo
            serie_graficar = None
            
            if es_24h:
                cols_horas = [c for c in df.columns if c in [str(i) for i in range(24)]]
                if not cols_horas:
                    cols_horas = [c for c in df.columns if 'hora' in c.lower()]
                
                if not cols_horas:
                    messagebox.showerror("Error", "No encontré columnas horarias (0-23).")
                    return

                for c in cols_horas:
                    df[c] = pd.to_numeric(df[c], errors='coerce')
                
                if operacion == "Promedio": df['Resultado_Dia'] = df[cols_horas].mean(axis=1)
                elif operacion == "Suma": df['Resultado_Dia'] = df[cols_horas].sum(axis=1)
                elif operacion == "Máximo": df['Resultado_Dia'] = df[cols_horas].max(axis=1)
                elif operacion == "Mínimo": df['Resultado_Dia'] = df[cols_horas].min(axis=1)
                    
                serie_graficar = df.groupby('Fecha')['Resultado_Dia'].mean()

            else:
                col_val = self.var_campo_valor.get()
                if not col_val:
                    messagebox.showwarning("Falta dato", "Selecciona la Columna de Valor.")
                    return
                
                df[col_val] = pd.to_numeric(df[col_val], errors='coerce')
                grupo = df.groupby('Fecha')[col_val]
                if operacion == "Promedio": serie_graficar = grupo.mean()
                elif operacion == "Suma": serie_graficar = grupo.sum()
                elif operacion == "Máximo": serie_graficar = grupo.max()
                elif operacion == "Mínimo": serie_graficar = grupo.min()

            self.dibujar_plot(serie_graficar.sort_index(), f"{tabla.upper()} - {valor_filtro} ({operacion})")

        except Exception as e:
            messagebox.showerror("Error", f"Detalle: {e}")
            print(e)

    def dibujar_plot(self, serie, titulo):
        for widget in self.frame_plot.winfo_children(): widget.destroy()

        fig = Figure(figsize=(8, 5), dpi=100)
        ax = fig.add_subplot(111)
        
        line, = ax.plot(serie.index, serie.values, marker='o', linestyle='-', markersize=4, color='#e67e22') 
        
        ax.set_title(titulo, fontsize=11, fontweight='bold')
        ax.grid(True, linestyle=':', alpha=0.6)
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate()

        annot = ax.annotate("", xy=(0,0), xytext=(10,10),textcoords="offset points",
                            bbox=dict(boxstyle="round", fc="w", ec="gray", alpha=0.9),
                            arrowprops=dict(arrowstyle="->"))
        annot.set_visible(False)

        def update_annot(ind):
            x, y = line.get_data()
            idx = ind["ind"][0]
            annot.xy = (x[idx], y[idx])
            
            # --- CORRECCIÓN CRÍTICA DE FECHAS ---
            val_x = x[idx]
            
            # Intentamos convertir asumiendo que es un float de matplotlib
            try:
                fecha_dt = mdates.num2date(val_x)
            except:
                # Si falla, asumimos que ya es un objeto datetime o similar
                fecha_dt = val_x

            # Formateamos a string de manera segura
            try:
                # Si tiene tzinfo (zona horaria), lo removemos o formateamos directo
                if hasattr(fecha_dt, 'strftime'):
                    fecha_str = fecha_dt.strftime("%Y-%m-%d")
                else:
                    # Intento final con pandas
                    fecha_str = pd.to_datetime(fecha_dt).strftime("%Y-%m-%d")
            except:
                fecha_str = "Error Fecha"

            valor_str = f"{y[idx]:.2f}"
            text = f"Fecha: {fecha_str}\nValor: {valor_str}"
            annot.set_text(text)

        def hover(event):
            vis = annot.get_visible()
            if event.inaxes == ax:
                cont, ind = line.contains(event)
                if cont:
                    update_annot(ind)
                    annot.set_visible(True)
                    fig.canvas.draw_idle()
                else:
                    if vis:
                        annot.set_visible(False)
                        fig.canvas.draw_idle()

        fig.canvas.mpl_connect("motion_notify_event", hover)

        canvas = FigureCanvasTkAgg(fig, master=self.frame_plot)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        toolbar = NavigationToolbar2Tk(canvas, self.frame_plot)
        toolbar.update()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

if __name__ == "__main__":
    root = tk.Tk()
    app = ModuloVisualizador(root)
    root.mainloop()
