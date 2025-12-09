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
import matplotlib.ticker as ticker # Importamos ticker para formatear ejes

class ModuloVisualizador:
    def __init__(self, root):
        self.root = root
        self.root.title("Módulo de Inteligencia Visual XM - Soporte 24 Horas")
        self.root.geometry("1150x950") 
        
        # Ruta de la BD
        self.ruta_db = "BaseDatosXM.db"
        
        # --- VARIABLES DE CONTROL ---
        self.var_tabla = tk.StringVar()
        self.var_version = tk.StringVar()
        
        # Filtro 1
        self.var_campo_filtro1 = tk.StringVar()
        self.var_valor_filtro1 = tk.StringVar()
        
        # Filtro 2
        self.var_campo_filtro2 = tk.StringVar()
        self.var_valor_filtro2 = tk.StringVar()
        
        self.var_campo_valor = tk.StringVar()
        self.var_agregacion = tk.StringVar(value="Promedio")
        
        self.var_fecha_ini = tk.StringVar()
        self.var_fecha_fin = tk.StringVar()
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

        # FILA 0: Archivo y Versión
        ttk.Label(frame_cfg, text="1. Archivo (Tabla):").grid(row=0, column=0, sticky="w", pady=5)
        self.cb_tabla = ttk.Combobox(frame_cfg, textvariable=self.var_tabla, state="readonly", width=25)
        self.cb_tabla.grid(row=0, column=1, padx=5, pady=5)
        self.cb_tabla.bind("<<ComboboxSelected>>", self.al_seleccionar_tabla)

        ttk.Label(frame_cfg, text="2. Versión Dato:").grid(row=0, column=2, sticky="w", padx=10)
        self.cb_version = ttk.Combobox(frame_cfg, textvariable=self.var_version, state="readonly", width=25)
        self.cb_version.grid(row=0, column=3, padx=5)

        # FILA 1: Filtro Primario
        ttk.Label(frame_cfg, text="3. Filtro Principal (Campo):").grid(row=1, column=0, sticky="w", pady=5)
        self.cb_campo_filtro1 = ttk.Combobox(frame_cfg, textvariable=self.var_campo_filtro1, state="readonly", width=25)
        self.cb_campo_filtro1.grid(row=1, column=1, padx=5)
        self.cb_campo_filtro1.bind("<<ComboboxSelected>>", self.al_seleccionar_campo_filtro1)

        ttk.Label(frame_cfg, text="Valor Principal:").grid(row=1, column=2, sticky="w", padx=10)
        self.cb_valor_filtro1 = ttk.Combobox(frame_cfg, textvariable=self.var_valor_filtro1, width=25) 
        self.cb_valor_filtro1.grid(row=1, column=3, padx=5)

        # FILA 2: Filtro Secundario (OPCIONAL)
        ttk.Label(frame_cfg, text="4. Filtro Secundario (Opcional):").grid(row=2, column=0, sticky="w", pady=5)
        self.cb_campo_filtro2 = ttk.Combobox(frame_cfg, textvariable=self.var_campo_filtro2, state="readonly", width=25)
        self.cb_campo_filtro2.grid(row=2, column=1, padx=5)
        self.cb_campo_filtro2.bind("<<ComboboxSelected>>", self.al_seleccionar_campo_filtro2)

        ttk.Label(frame_cfg, text="Valor Secundario (Dejar vacío para ignorar):").grid(row=2, column=2, sticky="w", padx=10)
        self.cb_valor_filtro2 = ttk.Combobox(frame_cfg, textvariable=self.var_valor_filtro2, width=25) 
        self.cb_valor_filtro2.grid(row=2, column=3, padx=5)

        # FILA 3: Checkbox 24h y Columna Valor
        self.chk_horario = ttk.Checkbutton(frame_cfg, text="5. Es Variable Horaria (24 cols)", variable=self.var_es_horario, command=self.toggle_campo_valor)
        self.chk_horario.grid(row=3, column=0, columnspan=2, sticky="w", pady=10)

        self.lbl_valor = ttk.Label(frame_cfg, text="6. Columna Valor Único:")
        self.lbl_valor.grid(row=3, column=2, sticky="w", padx=10)
        self.cb_campo_valor = ttk.Combobox(frame_cfg, textvariable=self.var_campo_valor, state="readonly", width=25)
        self.cb_campo_valor.grid(row=3, column=3, padx=5)

        # FILA 4: Operación
        ttk.Label(frame_cfg, text="7. Operación Matemática:").grid(row=4, column=0, sticky="w", pady=5)
        self.cb_agregacion = ttk.Combobox(frame_cfg, textvariable=self.var_agregacion, state="readonly", width=25)
        self.cb_agregacion['values'] = ["Promedio", "Suma", "Máximo", "Mínimo"]
        self.cb_agregacion.current(0)
        self.cb_agregacion.grid(row=4, column=1, padx=5)

        # FILA 5: Fechas
        ttk.Label(frame_cfg, text="Fecha Inicio (YYYY-MM-DD):").grid(row=5, column=0, sticky="w", pady=5)
        self.ent_fecha_ini = ttk.Entry(frame_cfg, textvariable=self.var_fecha_ini, width=25)
        self.ent_fecha_ini.grid(row=5, column=1, padx=5)
        self.ent_fecha_ini.insert(0, "2020-01-01") 

        ttk.Label(frame_cfg, text="Fecha Fin (YYYY-MM-DD):").grid(row=5, column=2, sticky="w", padx=10)
        self.ent_fecha_fin = ttk.Entry(frame_cfg, textvariable=self.var_fecha_fin, width=25)
        self.ent_fecha_fin.grid(row=5, column=3, padx=5)
        self.ent_fecha_fin.insert(0, datetime.today().strftime('%Y-%m-%d')) 

        # Botón Graficar
        ttk.Button(frame_cfg, text="📊 GENERAR VISUALIZACIÓN MULTI-FILTRO", command=self.generar_grafico).grid(row=6, column=0, columnspan=4, pady=15, sticky="ew")

        # 3. Área de Gráfico
        self.frame_plot = ttk.Frame(root)
        self.frame_plot.pack(fill="both", expand=True, padx=10, pady=10)
        
        if os.path.exists(self.ruta_db):
            self.cargar_tablas()

    # --- LÓGICA DE INTERFAZ ---
    def toggle_campo_valor(self):
        if self.var_es_horario.get():
            self.cb_campo_valor.configure(state="disabled")
            self.lbl_valor.configure(text="6. (Modo 24 Horas Activo)")
        else:
            self.cb_campo_valor.configure(state="readonly")
            self.lbl_valor.configure(text="6. Columna Valor Único:")

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
        
        # Versiones
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
        
        # Limpiar selecciones previas
        self.cb_campo_filtro1.set('')
        self.cb_valor_filtro1.set('')
        self.cb_campo_filtro2.set('')
        self.cb_valor_filtro2.set('')

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

    # --- LÓGICA CORE DE GRAFICACIÓN ---
    def generar_grafico(self):
        tabla = self.var_tabla.get()
        version = self.var_version.get()
        
        campo1 = self.var_campo_filtro1.get()
        valor1 = self.var_valor_filtro1.get()
        
        campo2 = self.var_campo_filtro2.get()
        valor2 = self.var_valor_filtro2.get()
        
        operacion = self.var_agregacion.get()
        es_24h = self.var_es_horario.get()
        
        f_ini_str = self.var_fecha_ini.get()
        f_fin_str = self.var_fecha_fin.get()
        
        if not tabla: return

        try:
            conn = self.conectar()
            
            # --- QUERY MULTI-FILTRO ---
            query = f"SELECT * FROM {tabla} WHERE 1=1"
            
            if campo1 and valor1:
                query += f" AND CAST({campo1} AS TEXT) = '{valor1}'"
            
            if campo2 and valor2:
                query += f" AND CAST({campo2} AS TEXT) = '{valor2}'"
            
            if version and version != "N/A":
                query += f" AND version_dato = '{version}'"
            
            print(f"Ejecutando SQL: {query}")
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                messagebox.showinfo("Vacío", f"No hay datos con esos filtros combinados.")
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
                    messagebox.showwarning("Falta dato", "Selecciona la Columna de Valor (Campo 6).")
                    return
                
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
            messagebox.showerror("Error Crítico", f"Detalle: {e}")
            print(e)

    def dibujar_plot(self, serie, titulo):
        for widget in self.frame_plot.winfo_children(): widget.destroy()

        fig = Figure(figsize=(8, 5), dpi=100)
        ax = fig.add_subplot(111)
        
        line, = ax.plot(serie.index, serie.values, marker='o', linestyle='-', markersize=4, color='#27ae60') 
        
        ax.set_title(titulo, fontsize=10, fontweight='bold')
        ax.grid(True, linestyle=':', alpha=0.6)
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        
        # --- NUEVO: FORMATEAR EJE Y CON COMAS ---
        ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}')) 
        
        fig.autofmt_xdate()

        annot = ax.annotate("", xy=(0,0), xytext=(10,10),textcoords="offset points",
                            bbox=dict(boxstyle="round", fc="w", ec="gray", alpha=0.9),
                            arrowprops=dict(arrowstyle="->"))
        annot.set_visible(False)

        def update_annot(ind):
            x, y = line.get_data()
            idx = ind["ind"][0]
            val_x = x[idx]
            annot.xy = (val_x, y[idx])
            
            try:
                fecha_dt = mdates.num2date(val_x)
            except:
                fecha_dt = val_x

            try:
                if hasattr(fecha_dt, 'strftime'):
                    fecha_str = fecha_dt.strftime("%Y-%m-%d")
                else:
                    fecha_str = pd.to_datetime(fecha_dt).strftime("%Y-%m-%d")
            except:
                fecha_str = "Fecha?"

            # --- CAMBIO APLICADO AQUÍ: {:,.2f} ---
            valor_str = f"{y[idx]:,.2f}"
            
            text = f"{fecha_str}\n{valor_str}"
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
