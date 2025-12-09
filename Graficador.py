import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sqlite3
import pandas as pd
import numpy as np
import os
import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.dates as mdates

matplotlib.use("TkAgg")

# --- CLASE 1: TOOLTIP ---
class ToolTip(object):
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0

    def showtip(self, text):
        self.text = text
        if self.tipwindow or not self.text: return
        try:
            x, y, cx, cy = self.widget.bbox("insert")
            x = x + self.widget.winfo_rootx() + 25
            y = y + cy + self.widget.winfo_rooty() + 25
            self.tipwindow = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(1)
            tw.wm_geometry("+%d+%d" % (x, y))
            label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                        background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                        font=("tahoma", "8", "normal"))
            label.pack(ipadx=1)
        except: pass

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw: tw.destroy()

def CreateToolTip(widget, text):
    toolTip = ToolTip(widget)
    def enter(event):
        if isinstance(widget, ttk.Combobox):
            val = widget.get()
            if val: toolTip.showtip(val)
        else:
            toolTip.showtip(text)
    def leave(event): toolTip.hidetip()
    widget.bind('<Enter>', enter)
    widget.bind('<Leave>', leave)

# --- CLASE 2: AUTOCOMPLETE COMBOBOX (ROBUSTA) ---
class AutocompleteCombobox(ttk.Combobox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind('<KeyRelease>', self.handle_keyrelease)
        self._completion_list = []
        self.bind('<Button-1>', self.autosize_popdown)

    def set_completion_list(self, completion_list):
        self._completion_list = sorted(completion_list, key=str.lower)
        self['values'] = self._completion_list

    def handle_keyrelease(self, event):
        if event.keysym in ('BackSpace', 'Left', 'Right', 'Up', 'Down', 'Return', 'Tab', 'Shift_L', 'Shift_R', 'Control_L', 'Alt_L'):
            return
        
        try: cursor_pos = self.index(tk.INSERT)
        except: cursor_pos = tk.END

        value = self.get()
        if value == '':
            self['values'] = self._completion_list
        else:
            data = [item for item in self._completion_list if value.lower() in item.lower()]
            self['values'] = data
        
        try: self.icursor(cursor_pos)
        except: pass

        if len(self['values']) > 0 and value != '':
             try: self.tk.call('ttk::combobox::Post', self._w)
             except: pass
             self.autosize_popdown(None)

    def autosize_popdown(self, event):
        try:
            values = self['values']
            if not values: return
            max_len = max(len(str(v)) for v in values)
            font_width = 7 
            req_width = max_len * font_width + 20
            if req_width < self.winfo_width(): req_width = self.winfo_width()
            popdown = self.tk.eval('ttk::combobox::PopdownWindow %s' % self._w)
            self.tk.call('%s.f.l' % popdown, 'configure', '-width', int(req_width // font_width) + 2)
        except: pass

# --- CLASE PRINCIPAL ---
class ModuloVisualizador:
    def __init__(self, root):
        self.root = root
        self.root.title("Visualizador XM Expert - V10 (Cascada Automática)")
        self.root.geometry("1300x950")
        
        self.ruta_db = "BaseDatosXM.db"
        self.diccionario_filtros = {} 
        
        self.var_fecha_ini = tk.StringVar(value="2020-01-01")
        self.var_fecha_fin = tk.StringVar(value="2030-12-31")
        self.var_version = tk.StringVar()
        self.var_es_24h = tk.BooleanVar()

        style = ttk.Style()
        style.configure("Italic.TLabel", font=("Arial", 8, "italic"))

        # --- LAYOUT ---
        frame_top = ttk.Frame(root, padding=10)
        frame_top.pack(fill="x")
        ttk.Label(frame_top, text="BD:").pack(side="left")
        self.lbl_db = ttk.Entry(frame_top, width=60)
        self.lbl_db.pack(side="left", padx=5)
        self.lbl_db.insert(0, os.path.abspath(self.ruta_db))
        ttk.Button(frame_top, text="📂", command=self.seleccionar_db, width=3).pack(side="left")
        ttk.Button(frame_top, text="Conectar", command=self.cargar_tablas).pack(side="left", padx=5)

        # Panel Global
        frame_global = ttk.LabelFrame(root, text="1. Configuración Global", padding=10)
        frame_global.pack(fill="x", padx=10, pady=5)

        ttk.Label(frame_global, text="Tabla:").grid(row=0, column=0, sticky="w")
        self.cb_tabla = AutocompleteCombobox(frame_global, state="normal", width=40)
        self.cb_tabla.grid(row=0, column=1, padx=5, sticky="w")
        self.cb_tabla.bind("<<ComboboxSelected>>", self.al_seleccionar_tabla)
        
        ttk.Label(frame_global, text="Versión:").grid(row=0, column=2, sticky="e", padx=10)
        self.cb_version = ttk.Combobox(frame_global, textvariable=self.var_version, state="readonly", width=20)
        self.cb_version.grid(row=0, column=3, sticky="w")

        # Fechas
        ttk.Label(frame_global, text="Rango Fechas:").grid(row=1, column=0, sticky="w", pady=10)
        frame_dates = ttk.Frame(frame_global)
        frame_dates.grid(row=1, column=1, columnspan=3, sticky="w")
        ttk.Entry(frame_dates, textvariable=self.var_fecha_ini, width=12).pack(side="left")
        ttk.Label(frame_dates, text=" a ").pack(side="left")
        ttk.Entry(frame_dates, textvariable=self.var_fecha_fin, width=12).pack(side="left")
        ttk.Label(frame_dates, text="(YYYY-MM-DD)", style="Italic.TLabel").pack(side="left", padx=10)

        # Panel Filtros
        self.frame_filtros = ttk.LabelFrame(root, text="2. Filtros Dinámicos (Cascada Inteligente)", padding=10)
        self.frame_filtros.pack(fill="x", padx=10, pady=5)
        
        # Panel Operaciones
        frame_ops = ttk.LabelFrame(root, text="3. Gráfico", padding=10)
        frame_ops.pack(fill="x", padx=10)
        
        ttk.Label(frame_ops, text="Var. Vertical:").pack(side="left")
        self.cb_valor = AutocompleteCombobox(frame_ops, state="normal", width=30)
        self.cb_valor.pack(side="left", padx=5)
        
        ttk.Checkbutton(frame_ops, text="Es Horaria (0-23)", variable=self.var_es_24h, command=self.toggle_24h).pack(side="left", padx=10)
        
        ttk.Label(frame_ops, text="Op:").pack(side="left", padx=5)
        self.cb_operacion = ttk.Combobox(frame_ops, values=["Promedio", "Suma", "Máximo", "Mínimo"], state="readonly", width=10)
        self.cb_operacion.current(0)
        self.cb_operacion.pack(side="left")

        ttk.Button(frame_ops, text="📊 GRAFICAR", command=self.generar_grafico).pack(side="right", padx=10)

        # Area Grafico
        self.frame_plot = ttk.Frame(root)
        self.frame_plot.pack(fill="both", expand=True, padx=10, pady=10)

        if os.path.exists(self.ruta_db): self.cargar_tablas()

    # --- BD ---
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
            tablas = [t[0] for t in cursor.fetchall()]
            self.cb_tabla.set_completion_list(sorted(tablas)) 
            conn.close()
        except: pass

    # --- LOGICA CASCADA (MEJORADA) ---
    def trigger_cascada(self, event=None):
        # Usamos 'after' para dar tiempo a que la variable se actualice si fue por teclado
        self.root.after(100, self.actualizar_filtros_cascada)

    def actualizar_filtros_cascada(self):
        tabla = self.cb_tabla.get()
        if not tabla: return

        # 1. Obtener seleccion actual
        seleccion_actual = {}
        for campo, widgets in self.diccionario_filtros.items():
            val = widgets['var'].get()
            if val and val != "TODOS" and val != "":
                seleccion_actual[campo] = val

        print(f"DEBUG: Actualizando cascada. Selección: {seleccion_actual}")

        # 2. Actualizar CADA filtro
        for campo_objetivo, widgets_obj in self.diccionario_filtros.items():
            clauses = []
            for col_sel, val_sel in seleccion_actual.items():
                # Filtrar basado en los OTROS campos
                if col_sel != campo_objetivo:
                    clauses.append(f"CAST({col_sel} AS TEXT) = '{val_sel}'")
            
            query = f"SELECT DISTINCT {campo_objetivo} FROM {tabla}"
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            query += f" ORDER BY {campo_objetivo}"

            try:
                conn = self.conectar()
                vals = pd.read_sql_query(query, conn)[campo_objetivo].astype(str).tolist()
                conn.close()
                vals.insert(0, "TODOS")
                
                # Actualizar lista
                widgets_obj['cb'].set_completion_list(vals)
                
                # AUTO-SELECCIÓN: Si solo hay 1 opción real (len=2 con TODOS), seleccionarla
                # Solo si el usuario no ha seleccionado nada aún o tiene algo invalido
                curr_val = widgets_obj['var'].get()
                
                if len(vals) == 2:
                    val_unico = vals[1]
                    if curr_val != val_unico:
                        print(f"--> Auto-seleccionando {val_unico} en {campo_objetivo}")
                        widgets_obj['cb'].set(val_unico)
                elif curr_val not in vals and curr_val != "" and curr_val != "TODOS":
                    # Si lo que tengo seleccionado ya no es válido, resetear
                    widgets_obj['cb'].set("TODOS")

            except Exception as e:
                print(f"Error cascada en {campo_objetivo}: {e}")

    # --- TABLA Y FILTROS UI ---
    def al_seleccionar_tabla(self, event):
        tabla = self.cb_tabla.get()
        if not tabla: return
        
        conn = self.conectar()
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
                self.cb_version['values'] = ["N/A"]; self.cb_version.set("N/A"); self.cb_version.configure(state="disabled")
        except: pass

        for widget in self.frame_filtros.winfo_children(): widget.destroy()
        self.diccionario_filtros = {}

        cols_horarias = [c for c in cols if (c.isdigit() and int(c)<24) or 'hora_' in c.lower()]
        excluir = ['index', 'anio', 'mes_dia', 'fecha_carga', 'id', 'version_dato'] + cols_horarias
        candidatos = [c for c in cols if c not in excluir]
        
        fila = 0; col = 0
        for campo in candidatos:
            ttk.Label(self.frame_filtros, text=f"{campo}:", font=("Arial", 8, "bold")).grid(row=fila, column=col*2, sticky="e", padx=5, pady=5)
            
            var_filtro = tk.StringVar()
            cb = AutocompleteCombobox(self.frame_filtros, textvariable=var_filtro, state="normal", width=35)
            cb.grid(row=fila, column=col*2 + 1, sticky="w", padx=5, pady=5)
            CreateToolTip(cb, f"Filtro: {campo}")
            
            # BINDINGS PARA CASCADA (Múltiples para asegurar)
            cb.bind("<<ComboboxSelected>>", self.trigger_cascada)
            cb.bind("<Return>", self.trigger_cascada)
            cb.bind("<FocusOut>", self.trigger_cascada)
            
            self.diccionario_filtros[campo] = {'var': var_filtro, 'cb': cb}
            self.cargar_valores_filtro(tabla, campo, cb)
            
            col += 1
            if col > 1:
                col = 0; fila += 1
        
        es_24h = len(cols_horarias) >= 24
        self.var_es_24h.set(es_24h)
        self.cb_valor.set_completion_list(cols)
        self.toggle_24h()
        conn.close()

    def cargar_valores_filtro(self, tabla, campo, combo):
        try:
            conn = self.conectar()
            valores = pd.read_sql_query(f"SELECT DISTINCT {campo} FROM {tabla} ORDER BY {campo}", conn)[campo].astype(str).tolist()
            conn.close()
            valores.insert(0, "TODOS")
            combo.set_completion_list(valores) 
            combo.current(0)
        except: pass

    def toggle_24h(self):
        if self.var_es_24h.get(): self.cb_valor.configure(state="disabled")
        else: self.cb_valor.configure(state="normal")

    # --- GENERACION ---
    def generar_grafico(self):
        tabla = self.cb_tabla.get()
        if not tabla: return
        
        try:
            conn = self.conectar()
            clauses = []
            titulo_partes = []
            
            for campo, widgets in self.diccionario_filtros.items():
                valor = widgets['var'].get()
                if valor and valor != "TODOS":
                    clauses.append(f"CAST({campo} AS TEXT) = '{valor}'")
                    val_corto = (valor[:25] + '..') if len(valor) > 25 else valor
                    titulo_partes.append(val_corto)
            
            ver = self.var_version.get()
            if ver and ver != "N/A":
                clauses.append(f"CAST(version_dato AS TEXT) = '{ver}'")
                titulo_partes.append(f"v:{ver}")

            query = f"SELECT * FROM {tabla}"
            if clauses: query += " WHERE " + " AND ".join(clauses)
            
            print(f"SQL: {query}")
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty: messagebox.showwarning("Vacío", "No hay datos."); return

            def armar_fecha(row):
                try:
                    a = str(row['anio']); md = str(row['mes_dia']).split('.')[0].zfill(4)
                    return pd.to_datetime(f"{a}-{md[:2]}-{md[2:]}")
                except: return pd.NaT
            
            df['Fecha'] = df.apply(armar_fecha, axis=1)
            df = df.dropna(subset=['Fecha'])
            
            try:
                f_ini = pd.to_datetime(self.var_fecha_ini.get())
                f_fin = pd.to_datetime(self.var_fecha_fin.get())
                df = df[(df['Fecha'] >= f_ini) & (df['Fecha'] <= f_fin)]
            except: pass
            
            if df.empty: messagebox.showwarning("Vacío", "Rango de fechas vacío."); return

            operacion = self.cb_operacion.get()
            serie_final = None
            
            if self.var_es_24h.get():
                cols_h = [c for c in df.columns if (c.isdigit() and int(c)<24) or 'hora_' in str(c).lower()]
                cols_h = sorted(list(set(cols_h)))
                if not cols_h: messagebox.showerror("Error", "No se detectaron columnas horarias"); return
                
                for c in cols_h: df[c] = pd.to_numeric(df[c], errors='coerce')
                
                if operacion == "Promedio": df['Val'] = df[cols_h].mean(axis=1)
                elif operacion == "Suma": df['Val'] = df[cols_h].sum(axis=1)
                elif operacion == "Máximo": df['Val'] = df[cols_h].max(axis=1)
                elif operacion == "Mínimo": df['Val'] = df[cols_h].min(axis=1)
                serie_final = df.groupby('Fecha')['Val'].mean()
            else:
                col = self.cb_valor.get()
                if not col: messagebox.showwarning("Falta dato", "Seleccione Variable Vertical"); return
                df[col] = pd.to_numeric(df[col], errors='coerce')
                grupo = df.groupby('Fecha')[col]
                if operacion == "Promedio": serie_final = grupo.mean()
                elif operacion == "Suma": serie_final = grupo.sum()
                elif operacion == "Máximo": serie_final = grupo.max()
                elif operacion == "Mínimo": serie_final = grupo.min()

            tit = f"{tabla.upper()} ({operacion})\n" + " | ".join(titulo_partes)
            self.dibujar(serie_final.sort_index(), tit)

        except Exception as e:
            messagebox.showerror("Error", str(e))
            print(e)

    def dibujar(self, serie, titulo):
        for w in self.frame_plot.winfo_children(): w.destroy()
        
        fig = Figure(figsize=(8,5), dpi=100)
        ax = fig.add_subplot(111)
        
        line, = ax.plot(serie.index, serie.values, marker='o', markersize=3, color='#2980b9')
        ax.set_title(titulo, fontsize=10)
        ax.grid(True, linestyle=':', alpha=0.6)
        
        dias = (serie.index.max() - serie.index.min()).days
        if dias < 60:
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        else:
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        fig.autofmt_xdate()

        # CURSOR MAGNÉTICO
        vline = ax.axvline(x=serie.index[0], color='k', linestyle='--', alpha=0.5)
        vline.set_visible(False)
        
        annot = ax.annotate("", xy=(0,0), xytext=(10,10), textcoords="offset points",
                            bbox=dict(boxstyle="round", fc="w", alpha=0.9),
                            arrowprops=dict(arrowstyle="->"))
        annot.set_visible(False)

        x_data_num = mdates.date2num(serie.index.to_pydatetime())
        y_data = serie.values

        def hover(event):
            if event.inaxes == ax:
                try:
                    idx = (np.abs(x_data_num - event.xdata)).argmin()
                    x_val = x_data_num[idx]
                    y_val = y_data[idx]
                    
                    vline.set_xdata([x_val, x_val])
                    vline.set_visible(True)
                    
                    annot.xy = (x_val, y_val)
                    fecha_str = mdates.num2date(x_val).strftime("%Y-%m-%d")
                    annot.set_text(f"Fecha: {fecha_str}\nValor: {y_val:,.2f}")
                    annot.set_visible(True)
                    canvas.draw_idle()
                except: pass
            else:
                if annot.get_visible():
                    annot.set_visible(False)
                    vline.set_visible(False)
                    canvas.draw_idle()

        canvas = FigureCanvasTkAgg(fig, master=self.frame_plot)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
        fig.canvas.mpl_connect("motion_notify_event", hover)
        NavigationToolbar2Tk(canvas, self.frame_plot)

if __name__ == "__main__":
    root = tk.Tk()
    app = ModuloVisualizador(root)
    root.mainloop()
