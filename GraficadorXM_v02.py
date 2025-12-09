import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sqlite3
import pandas as pd
import os
import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.dates as mdates

matplotlib.use("TkAgg")

class ModuloVisualizador:
    def __init__(self, root):
        self.root = root
        self.root.title("Visualizador XM Master - Filtros Dinámicos + Fechas + Versiones")
        self.root.geometry("1200x950")
        
        self.ruta_db = "BaseDatosXM.db"
        self.diccionario_filtros = {} 
        
        # --- VARIABLES ---
        self.var_fecha_ini = tk.StringVar(value="2025-01-01")
        self.var_fecha_fin = tk.StringVar(value="2025-12-31")
        self.var_version = tk.StringVar()
        self.var_es_24h = tk.BooleanVar()

        # Configurar estilo para letra cursiva (CORREGIDO: Se define antes de usarse)
        style = ttk.Style()
        style.configure("Italic.TLabel", font=("Arial", 8, "italic"))

        # --- LAYOUT PRINCIPAL ---
        
        # 1. TOP: Selección de Archivo
        frame_top = ttk.Frame(root, padding=10)
        frame_top.pack(fill="x")
        ttk.Label(frame_top, text="BD:").pack(side="left")
        self.lbl_db = ttk.Entry(frame_top, width=50)
        self.lbl_db.pack(side="left", padx=5)
        self.lbl_db.insert(0, os.path.abspath(self.ruta_db))
        ttk.Button(frame_top, text="📂", command=self.seleccionar_db, width=3).pack(side="left")
        ttk.Button(frame_top, text="Conectar", command=self.cargar_tablas).pack(side="left", padx=5)

        # 2. PANEL GLOBAL (Tabla, Fechas, Versión)
        frame_global = ttk.LabelFrame(root, text="1. Configuración Global", padding=10)
        frame_global.pack(fill="x", padx=10, pady=5)

        # Fila 1: Tabla y Versión
        ttk.Label(frame_global, text="Tabla:").grid(row=0, column=0, sticky="w")
        self.cb_tabla = ttk.Combobox(frame_global, state="readonly", width=35)
        self.cb_tabla.grid(row=0, column=1, padx=5, sticky="w")
        self.cb_tabla.bind("<<ComboboxSelected>>", self.al_seleccionar_tabla)

        ttk.Label(frame_global, text="Versión:").grid(row=0, column=2, sticky="e", padx=10)
        self.cb_version = ttk.Combobox(frame_global, textvariable=self.var_version, state="readonly", width=20)
        self.cb_version.grid(row=0, column=3, sticky="w")

        # Fila 2: Rango de Fechas
        ttk.Label(frame_global, text="Rango Fechas:").grid(row=1, column=0, sticky="w", pady=10)
        frame_dates = ttk.Frame(frame_global)
        frame_dates.grid(row=1, column=1, columnspan=3, sticky="w")
        
        ttk.Entry(frame_dates, textvariable=self.var_fecha_ini, width=12).pack(side="left")
        ttk.Label(frame_dates, text="  hasta  ").pack(side="left")
        ttk.Entry(frame_dates, textvariable=self.var_fecha_fin, width=12).pack(side="left")
        
        # --- CORRECCIÓN AQUÍ ---
        # El estilo va dentro de Label(), no de pack()
        ttk.Label(frame_dates, text="(Formato: YYYY-MM-DD)", style="Italic.TLabel").pack(side="left", padx=10)

        # 3. PANEL FILTROS DINÁMICOS
        self.frame_filtros = ttk.LabelFrame(root, text="2. Filtros Específicos (Opcional)", padding=10)
        self.frame_filtros.pack(fill="x", padx=10, pady=5)
        
        # 4. PANEL OPERACIONES
        frame_ops = ttk.LabelFrame(root, text="3. Configuración de Gráfico", padding=10)
        frame_ops.pack(fill="x", padx=10)
        
        ttk.Label(frame_ops, text="Variable a Graficar:").pack(side="left")
        self.cb_valor = ttk.Combobox(frame_ops, state="readonly", width=20)
        self.cb_valor.pack(side="left", padx=5)
        
        ttk.Checkbutton(frame_ops, text="Es Variable Horaria (0-23)", variable=self.var_es_24h, command=self.toggle_24h).pack(side="left", padx=10)
        
        ttk.Label(frame_ops, text="Operación:").pack(side="left", padx=5)
        self.cb_operacion = ttk.Combobox(frame_ops, values=["Promedio", "Suma", "Máximo", "Mínimo"], state="readonly", width=10)
        self.cb_operacion.current(0)
        self.cb_operacion.pack(side="left")

        ttk.Button(frame_ops, text="📊 GENERAR GRÁFICO", command=self.generar_grafico).pack(side="right", padx=10)

        # 5. GRÁFICO
        self.frame_plot = ttk.Frame(root)
        self.frame_plot.pack(fill="both", expand=True, padx=10, pady=10)

        if os.path.exists(self.ruta_db): self.cargar_tablas()

    # --- LÓGICA BD ---
    def conectar(self): return sqlite3.connect(self.ruta_db)
    
    def seleccionar_db(self):
        f = filedialog.askopenfilename(filetypes=[("DB", "*.db")])
        if f: 
            self.ruta_db = f
            self.lbl_db.delete(0, tk.END); self.lbl_db.insert(0, f)
            self.cargar_tablas()

    def cargar_tablas(self):
        try:
            conn = self.conectar()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            self.cb_tabla['values'] = sorted([t[0] for t in cursor.fetchall()])
            conn.close()
        except: pass

    # --- LÓGICA DINÁMICA ---
    def al_seleccionar_tabla(self, event):
        tabla = self.cb_tabla.get()
        if not tabla: return
        
        conn = self.conectar()
        
        # 1. Cargar Versiones (Si existe)
        try:
            df_cols = pd.read_sql_query(f"SELECT * FROM {tabla} LIMIT 1", conn)
            cols = df_cols.columns.tolist()
            
            if 'version_dato' in cols:
                df_ver = pd.read_sql_query(f"SELECT DISTINCT version_dato FROM {tabla} ORDER BY version_dato DESC", conn)
                versiones = df_ver['version_dato'].astype(str).tolist()
                self.cb_version['values'] = versiones
                if versiones: self.cb_version.current(0)
                self.cb_version.configure(state="readonly")
            else:
                self.cb_version['values'] = ["N/A"]
                self.cb_version.set("N/A")
                self.cb_version.configure(state="disabled")
        except: pass

        # 2. Generar Filtros Dinámicos
        # Limpiar
        for widget in self.frame_filtros.winfo_children(): widget.destroy()
        self.diccionario_filtros = {}

        # Definir qué es columna técnica (NO FILTRO) y qué es horario
        cols_horarias = [c for c in cols if (c.isdigit() and int(c)<24) or 'hora_' in c.lower()]
        excluir = ['index', 'anio', 'mes_dia', 'fecha_carga', 'id', 'version_dato'] + cols_horarias
        
        candidatos_filtro = [c for c in cols if c not in excluir]
        
        # Crear widgets
        fila = 0; col = 0
        for campo in candidatos_filtro:
            ttk.Label(self.frame_filtros, text=f"{campo}:", font=("Arial", 8, "bold")).grid(row=fila, column=col*2, sticky="e", padx=5, pady=5)
            
            var_filtro = tk.StringVar()
            cb = ttk.Combobox(self.frame_filtros, textvariable=var_filtro, state="readonly", width=22)
            cb.grid(row=fila, column=col*2 + 1, sticky="w", padx=5, pady=5)
            
            self.diccionario_filtros[campo] = {'var': var_filtro, 'cb': cb}
            self.cargar_valores_filtro(tabla, campo, cb)
            
            col += 1
            if col > 2: # 3 columnas de filtros
                col = 0; fila += 1
        
        # Lógica 24h
        es_24h = len(cols_horarias) >= 24
        self.var_es_24h.set(es_24h)
        self.cb_valor['values'] = cols
        self.toggle_24h()
        
        conn.close()

    def cargar_valores_filtro(self, tabla, campo, combo):
        try:
            conn = self.conectar()
            valores = pd.read_sql_query(f"SELECT DISTINCT {campo} FROM {tabla} ORDER BY {campo}", conn)[campo].astype(str).tolist()
            conn.close()
            valores.insert(0, "TODOS")
            combo['values'] = valores
            combo.current(0)
        except: pass

    def toggle_24h(self):
        if self.var_es_24h.get(): self.cb_valor.configure(state="disabled")
        else: self.cb_valor.configure(state="readonly")

    # --- GENERACIÓN ---
    def generar_grafico(self):
        tabla = self.cb_tabla.get()
        if not tabla: return
        
        try:
            conn = self.conectar()
            
            # 1. Construir WHERE SQL (Filtros + Versión)
            clauses = []
            titulo_partes = []
            
            # A. Filtros Dinámicos
            for campo, widgets in self.diccionario_filtros.items():
                valor = widgets['var'].get()
                if valor and valor != "TODOS":
                    clauses.append(f"CAST({campo} AS TEXT) = '{valor}'")
                    titulo_partes.append(f"{valor}")
            
            # B. Filtro Versión
            ver = self.var_version.get()
            if ver and ver != "N/A":
                clauses.append(f"CAST(version_dato AS TEXT) = '{ver}'")
                titulo_partes.append(f"v: {ver}")

            query = f"SELECT * FROM {tabla}"
            if clauses: query += " WHERE " + " AND ".join(clauses)
            
            print(f"SQL: {query}")
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                messagebox.showwarning("Vacío", "No hay datos con esos filtros.")
                return

            # 2. Procesar FECHAS
            def armar_fecha(row):
                try:
                    a = str(row['anio']); md = str(row['mes_dia']).split('.')[0].zfill(4)
                    return pd.to_datetime(f"{a}-{md[:2]}-{md[2:]}")
                except: return pd.NaT
            
            df['Fecha'] = df.apply(armar_fecha, axis=1)
            df = df.dropna(subset=['Fecha'])
            
            # 3. FILTRO RANGO DE FECHAS (Pandas)
            try:
                f_ini = pd.to_datetime(self.var_fecha_ini.get())
                f_fin = pd.to_datetime(self.var_fecha_fin.get())
                df = df[(df['Fecha'] >= f_ini) & (df['Fecha'] <= f_fin)]
            except: 
                print("Error en rango de fechas, mostrando todo.")
            
            if df.empty:
                messagebox.showwarning("Vacío", "El rango de fechas dejó la tabla vacía.")
                return

            # 4. AGRUPACIÓN Y CÁLCULO
            operacion = self.cb_operacion.get()
            serie_final = None
            
            if self.var_es_24h.get():
                # Modo 24H (Inteligente)
                # Buscamos columnas hora_01 o 0, 1...
                cols_h = [c for c in df.columns if (c.isdigit() and int(c)<24) or 'hora_' in str(c).lower()]
                cols_h = sorted(list(set(cols_h))) # Limpieza
                
                # Convertir a numerico
                for c in cols_h: df[c] = pd.to_numeric(df[c], errors='coerce')
                
                # Reducción Horizontal
                if operacion == "Promedio": df['Val'] = df[cols_h].mean(axis=1)
                elif operacion == "Suma": df['Val'] = df[cols_h].sum(axis=1)
                elif operacion == "Máximo": df['Val'] = df[cols_h].max(axis=1)
                elif operacion == "Mínimo": df['Val'] = df[cols_h].min(axis=1)
                
                # Reducción Vertical (Agrupar por Fecha)
                serie_final = df.groupby('Fecha')['Val'].mean()
            else:
                # Modo Columna Simple
                col = self.cb_valor.get()
                if not col: return
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
                grupo = df.groupby('Fecha')[col]
                if operacion == "Promedio": serie_final = grupo.mean()
                elif operacion == "Suma": serie_final = grupo.sum()
                elif operacion == "Máximo": serie_final = grupo.max()
                elif operacion == "Mínimo": serie_final = grupo.min()

            # 5. DIBUJAR
            tit = f"{tabla.upper()} ({operacion})\n" + " | ".join(titulo_partes)
            self.dibujar(serie_final, tit)

        except Exception as e:
            messagebox.showerror("Error", str(e))
            print(e)

    def dibujar(self, serie, titulo):
        for w in self.frame_plot.winfo_children(): w.destroy()
        
        fig = Figure(figsize=(8,5), dpi=100)
        ax = fig.add_subplot(111)
        
        ax.plot(serie.index, serie.values, marker='o', markersize=3, color='#2980b9')
        ax.set_title(titulo, fontsize=10)
        ax.grid(True, linestyle=':', alpha=0.6)
        
        # Eje X Inteligente
        if len(serie) > 0:
            dias = (serie.index.max() - serie.index.min()).days
            if dias < 60:
                ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            else:
                ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            
        fig.autofmt_xdate()
        
        canvas = FigureCanvasTkAgg(fig, master=self.frame_plot)
        canvas.draw(); canvas.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(canvas, self.frame_plot)

if __name__ == "__main__":
    root = tk.Tk()
    app = ModuloVisualizador(root)
    root.mainloop()
