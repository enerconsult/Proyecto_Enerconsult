#!/usr/bin/env python3
"""
RobotXM_App_Copilot.py
Standalone demo of the improved UI (Rounded cards, Rounded buttons, searchable dropdown with tooltips).
Copy this file and run: python RobotXM_App_Copilot.py

This is a self-contained demo (no FTP / DB / Excel operations).
It shows the redesigned UI and components so you can see the visual result immediately.
"""
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import json
import os
import sys
import threading
import time
from datetime import datetime
import random

# Optional: matplotlib for a sample plot in the Visualizador tab
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    import matplotlib.dates as mdates
    HAS_MPL = True
except Exception:
    HAS_MPL = False

# ---------------------------
# UI Helpers: RoundedCard, RoundedButton, CustomDropdownWithTooltip
# ---------------------------

class RoundedCard(tk.Frame):
    """Canvas-backed rounded card that hosts a normal Frame (for content).
       Use get_body() to access the inner frame where you add widgets.
    """
    def __init__(self, parent, title=None, icon=None, radius=12, padding=(12, 10, 12, 10),
                 bg=None, fill="#ffffff", outline="#e5e7eb", outline_width=1, *args, **kwargs):
        super().__init__(parent, bg=bg or parent.cget("bg"), *args, **kwargs)
        self.radius = radius
        self.pad_left, self.pad_top, self.pad_right, self.pad_bottom = padding
        self.fill = fill
        self.outline = outline
        self.outline_width = outline_width

        self._canvas = tk.Canvas(self, highlightthickness=0, bg=self.cget("bg"))
        self._canvas.pack(fill="both", expand=True)
        self._inner = tk.Frame(self._canvas, bg=self.fill)
        self._win_id = self._canvas.create_window(self.pad_left, self.pad_top, window=self._inner, anchor="nw")

        if title or icon:
            header = tk.Frame(self._inner, bg=self.fill)
            header.pack(fill="x", pady=(0, 6))
            if icon:
                tk.Label(header, text=icon, bg=self.fill, font=("Segoe UI", 12)).pack(side="left", padx=(0,8))
            if title:
                tk.Label(header, text=title, bg=self.fill, font=("Segoe UI Semibold", 11), fg="#1f2937").pack(side="left")

        self._content = tk.Frame(self._inner, bg=self.fill)
        self._content.pack(fill="both", expand=True)

        self._canvas.bind("<Configure>", self._on_configure)
        self._inner.bind("<Configure>", self._on_inner_configure)

    def _on_configure(self, event):
        w = max(1, event.width)
        h = max(1, event.height)
        # delete previous bg
        self._canvas.delete("card_bg")
        r = self.radius
        x1, y1, x2, y2 = 1, 1, w-2, h-2
        # central rectangles
        self._canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=self.fill, outline="", tags=("card_bg",))
        self._canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=self.fill, outline="", tags=("card_bg",))
        # corners
        self._canvas.create_oval(x1, y1, x1 + 2*r, y1 + 2*r, fill=self.fill, outline="", tags=("card_bg",))
        self._canvas.create_oval(x2 - 2*r, y1, x2, y1 + 2*r, fill=self.fill, outline="", tags=("card_bg",))
        self._canvas.create_oval(x1, y2 - 2*r, x1 + 2*r, y2, fill=self.fill, outline="", tags=("card_bg",))
        self._canvas.create_oval(x2 - 2*r, y2 - 2*r, x2, y2, fill=self.fill, outline="", tags=("card_bg",))
        # border lines
        ow = self.outline_width
        if ow > 0:
            self._canvas.create_line(x1 + r, y1, x2 - r, y1, fill=self.outline, width=ow, tags=("card_bg",))
            self._canvas.create_line(x1 + r, y2, x2 - r, y2, fill=self.outline, width=ow, tags=("card_bg",))
            self._canvas.create_line(x1, y1 + r, x1, y2 - r, fill=self.outline, width=ow, tags=("card_bg",))
            self._canvas.create_line(x2, y1 + r, x2, y2 - r, fill=self.outline, width=ow, tags=("card_bg",))
            try:
                self._canvas.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, style='arc', outline=self.outline, width=ow, tags=("card_bg",))
                self._canvas.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, style='arc', outline=self.outline, width=ow, tags=("card_bg",))
                self._canvas.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, style='arc', outline=self.outline, width=ow, tags=("card_bg",))
                self._canvas.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, style='arc', outline=self.outline, width=ow, tags=("card_bg",))
            except Exception:
                pass

        inner_w = max(10, w - (self.pad_left + self.pad_right))
        inner_h = max(10, h - (self.pad_top + self.pad_bottom))
        self._canvas.coords(self._win_id, self.pad_left, self.pad_top)
        self._canvas.itemconfig(self._win_id, width=inner_w, height=inner_h)

    def _on_inner_configure(self, event):
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        req_w = event.width + (self.pad_left + self.pad_right)
        req_h = event.height + (self.pad_top + self.pad_bottom)
        if req_w > cw or req_h > ch:
            self._canvas.config(width=max(cw, req_w), height=max(ch, req_h))

    def get_body(self):
        return self._content


class RoundedButton(tk.Canvas):
    """Canvas-backed rounded button with hover/press and keyboard activation support."""
    def __init__(self, parent, text="", icon=None, command=None, radius=10,
                 padding=(12,6), bg=None, fill="#0093d0", fill_hover="#007bb5", fill_pressed="#0070a0",
                 fg="white", outline=None, outline_width=0, *args, **kwargs):
        super().__init__(parent, height=32, highlightthickness=0, bg=bg or parent.cget("bg"), *args, **kwargs)
        self.command = command
        self.text = text
        self.icon = icon
        self.radius = radius
        self.pad_x, self.pad_y = padding
        self.fill = fill
        self.fill_hover = fill_hover
        self.fill_pressed = fill_pressed
        self.fg = fg
        self.outline = outline
        self.outline_width = outline_width

        self._state = "normal"  # normal, hover, pressed

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Key>", self._on_key)
        self.bind("<FocusIn>", lambda e: self._draw())
        self.bind("<FocusOut>", lambda e: self._draw())

        self.configure(takefocus=1)
        self._draw()
        self.update_idletasks()
        self.bind("<Configure>", lambda e: self._draw())

    def _current_fill(self):
        if self._state == "pressed":
            return self.fill_pressed
        if self._state == "hover":
            return self.fill_hover
        return self.fill

    def _draw(self):
        self.delete("all")
        w = max(60, self.winfo_width() or 80)
        h = max(24, self.winfo_height() or 32)
        r = self.radius
        fill_color = self._current_fill()
        x1, y1, x2, y2 = 1, 1, w-2, h-2
        self.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill_color, width=0, tags=("bg",))
        self.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill_color, width=0, tags=("bg",))
        self.create_oval(x1, y1, x1 + 2*r, y1 + 2*r, fill=fill_color, width=0, tags=("bg",))
        self.create_oval(x2 - 2*r, y1, x2, y1 + 2*r, fill=fill_color, width=0, tags=("bg",))
        self.create_oval(x1, y2 - 2*r, x1 + 2*r, y2, fill=fill_color, width=0, tags=("bg",))
        self.create_oval(x2 - 2*r, y2 - 2*r, x2, y2, fill=fill_color, width=0, tags=("bg",))
        label = f"{self.icon + '  ' if self.icon else ''}{self.text}"
        self.create_text(w/2, h/2, text=label, fill=self.fg, font=("Segoe UI Semibold", 10))

    def _on_enter(self, event=None):
        if self._state != "pressed":
            self._state = "hover"
            self._draw()

    def _on_leave(self, event=None):
        if self._state != "pressed":
            self._state = "normal"
            self._draw()

    def _on_press(self, event=None):
        self._state = "pressed"
        self._draw()

    def _on_release(self, event=None):
        # Robust: if event is None (keyboard activation), assume trigger.
        triggered = False
        if event is None:
            triggered = True
        else:
            try:
                x, y = event.x, event.y
                triggered = (0 <= x <= self.winfo_width() and 0 <= y <= self.winfo_height())
            except Exception:
                triggered = True

        if triggered and callable(self.command):
            try:
                self.command()
            except Exception:
                pass

        self._state = "hover"
        self._draw()

    def _on_key(self, event):
        if event.keysym in ("Return", "space"):
            self._on_press()
            self.after(80, lambda: self._on_release(None))


class CustomDropdownWithTooltip:
    """Searchable dropdown with tooltip for long items (simple demo)."""
    def __init__(self, master, textvariable=None, width=18, command=None, tooltip_threshold=18, dropdown_height=160):
        self.master = master
        self.items = []
        self.filtered_items = []
        self.textvariable = textvariable
        self.command = command
        self.tooltip_threshold = tooltip_threshold
        self.dropdown_height = dropdown_height

        self.entry = ttk.Entry(master, width=width, textvariable=self.textvariable)
        self.entry.bind("<Button-1>", self.show_dropdown)
        self.entry.bind("<KeyRelease>", self.filter_items)
        self.entry.bind("<Down>", self.focus_listbox)
        self.entry.bind("<Escape>", lambda e: self.close_dropdown())

        self.dropdown = None
        self.tooltip = None
        self.listbox = None
        self.current_index = None

    def focus_listbox(self, event=None):
        if not self.dropdown:
            self.show_dropdown()
        if self.listbox:
            self.listbox.focus_set()
            if self.listbox.size() > 0:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(0)
                self.listbox.activate(0)

    def update_items(self, new_items):
        self.items = [str(x) for x in new_items]
        self.filtered_items = self.items[:]

    def show_dropdown(self, event=None):
        if self.dropdown:
            self.close_dropdown()
            return
        self.dropdown = tk.Toplevel(self.master)
        try:
            self.dropdown.wm_overrideredirect(True)
            self.dropdown.attributes("-topmost", True)
        except Exception:
            pass
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        w_pixels = max(self.entry.winfo_width(), 150)
        height = self.dropdown_height
        self.dropdown.geometry(f"{w_pixels}x{height}+{x}+{y}")
        frame_list = tk.Frame(self.dropdown, bd=0)
        frame_list.pack(fill="both", expand=True)
        scrollbar = tk.Scrollbar(frame_list, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        chars_w = max(10, int(w_pixels/7))
        self.listbox = tk.Listbox(frame_list, width=chars_w, height=8, yscrollcommand=scrollbar.set, exportselection=False,
                                  bg="#ffffff", fg="#2c3e50", selectbackground="#0093d0", selectforeground="#ffffff",
                                  font=("Segoe UI", 10), borderwidth=0)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)
        self.listbox.delete(0, tk.END)
        for item in self.filtered_items:
            self.listbox.insert(tk.END, item)
        self.listbox.bind("<Motion>", self.on_motion)
        self.listbox.bind("<Leave>", self.hide_tooltip)
        self.listbox.bind("<ButtonRelease-1>", self.select_item)
        self.listbox.bind("<Escape>", lambda e: self.close_dropdown())
        self.dropdown.bind("<FocusOut>", lambda e: self.close_dropdown())

    def on_motion(self, event):
        if not self.listbox:
            return
        index = self.listbox.nearest(event.y)
        if index >= 0 and index < self.listbox.size():
            if index != self.current_index:
                self.current_index = index
                self.show_tooltip(index, event)

    def show_tooltip(self, index, event):
        self.hide_tooltip()
        try:
            text = self.listbox.get(index)
        except Exception:
            return
        if len(text) < self.tooltip_threshold:
            return
        x = event.x_root + 20
        y = event.y_root + 10
        self.tooltip = tk.Toplevel(self.master)
        try:
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.attributes("-topmost", True)
        except:
            pass
        self.tooltip.geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip, text=text, background="#ffffe0",
                         relief="solid", borderwidth=1,
                         font=("Arial", "9", "normal"), padx=5, pady=2)
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip:
            try:
                self.tooltip.destroy()
            except Exception:
                pass
            self.tooltip = None

    def select_item(self, event=None):
        if not self.listbox:
            return
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
        if self.command:
            try:
                self.command(None)
            except Exception:
                pass

    def close_dropdown(self):
        self.hide_tooltip()
        if self.dropdown:
            try:
                self.dropdown.destroy()
            except Exception:
                pass
            self.dropdown = None
            self.listbox = None
            self.current_index = None

    def filter_items(self, event):
        if event.keysym in ['Down', 'Up', 'Return', 'Escape']:
            return
        query = self.entry.get().lower()
        self.filtered_items = [item for item in self.items if query in item.lower()]
        if self.dropdown and self.listbox:
            self.listbox.delete(0, tk.END)
            for item in self.filtered_items:
                self.listbox.insert(tk.END, item)
        else:
            if query:
                self.show_dropdown()

# ---------------------------
# Main Application
# ---------------------------

APP_CONFIG_FILE = "demo_config_ui.json"

class AplicacionXM:
    def __init__(self, root):
        self.root = root
        self.root.title("RobotXM_App_Copilot")
        self.root.geometry("1100x820")
        self.root.minsize(900, 700)

        self.setup_styles()

        # Top header with logo/title
        header = tk.Frame(root, bg="#ffffff")
        header.pack(fill="x", pady=(6,6))
        lbl_title = tk.Label(header, text="RobotXM - Demo UI (Copilot)", bg="#ffffff", fg="#0b69a6",
                             font=("Segoe UI Semibold", 16))
        lbl_title.pack(padx=20, pady=10, anchor="w")

        # Tabs
        tab_control = ttk.Notebook(root)
        tab_control.pack(expand=1, fill="both", padx=12, pady=(0,8))

        self.tab_general = tk.Frame(tab_control, bg="#f4f6f7")
        self.tab_archivos = tk.Frame(tab_control, bg="#f4f6f7")
        self.tab_filtros = tk.Frame(tab_control, bg="#f4f6f7")
        self.tab_visualizador = tk.Frame(tab_control, bg="#f4f6f7")

        tab_control.add(self.tab_general, text='🔧 Configuración')
        tab_control.add(self.tab_archivos, text='📥 Descargas')
        tab_control.add(self.tab_filtros, text='📋 Filtros')
        tab_control.add(self.tab_visualizador, text='📈 Visualizador')

        self.build_tab_general()
        self.build_tab_archivos()
        self.build_tab_filtros()
        self.build_tab_visualizador()

        # Console / monitor
        tk.Label(root, text=">_ Monitor de Ejecución", font=("Segoe UI", 9, "bold"), fg="#374151").pack(anchor="w", padx=15)
        self.txt_console = scrolledtext.ScrolledText(root, height=8, state='disabled', bg='black', fg='#00FF00', font=('Consolas', 9))
        self.txt_console.pack(fill="both", expand=False, padx=10, pady=(3,10))
        sys.stdout = PrintRedirector(self.txt_console)

        # Load demo config if exists
        self.config = self.load_config()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        c_azul_corp = "#0093d0"
        c_verde_corp = "#8cc63f"
        c_fondo = "#f4f6f7"
        c_blanco = "#ffffff"
        c_texto = "#2c3e50"
        self.root.configure(bg=c_fondo)

        f_main = ("Segoe UI", 10)
        f_head = ("Segoe UI Semibold", 11)
        f_title = ("Segoe UI", 12, "bold")

        style.configure(".", background=c_fondo, foreground=c_texto, font=f_main)
        style.configure("TFrame", background=c_fondo)
        style.configure("TLabelframe", background=c_fondo, borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background=c_fondo, foreground=c_azul_corp, font=f_title)

        style.configure("TNotebook", background=c_fondo, borderwidth=0, tabmargins=[0, 0, 0, 0])
        style.configure("TNotebook.Tab", padding=[12, 8], font=f_head, background="#ecf2f6", foreground="#7f8c8d")
        style.map("TNotebook.Tab", background=[("selected", c_blanco)], foreground=[("selected", c_azul_corp)])

        style.configure("Primary.TButton", font=f_head, background=c_azul_corp, foreground="white")
        style.map("Primary.TButton", background=[("active", "#007bb5")])
        style.configure("Success.TButton", font=f_head, background=c_verde_corp, foreground="white")

        style.configure("Treeview", background=c_blanco, foreground=c_texto, fieldbackground=c_blanco, rowheight=24, font=f_main)
        style.configure("Treeview.Heading", font=f_head, background="#dfe6e9", foreground=c_texto, padding=5)

        # Card styles
        style.configure("Card.TFrame", background=c_blanco, relief="flat")
        style.configure("CardHeader.TFrame", background=c_blanco)
        style.configure("CardTitle.TLabel", font=("Segoe UI Semibold", 11), background=c_blanco, foreground=c_azul_corp)
        style.configure("CardIcon.TLabel", background=c_blanco)
        style.configure("CardBody.TFrame", background=c_blanco)

    def build_tab_general(self):
        container = tk.Frame(self.tab_general, bg="#f4f6f7")
        container.pack(fill="both", expand=True, padx=20, pady=10)

        card = RoundedCard(container, title="Credenciales FTP y Rutas", icon="🔐", fill="#ffffff")
        card.pack(fill="x", pady=(0, 8))
        body = card.get_body()
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        tk.Label(body, text="Usuario FTP", bg="#ffffff", anchor="w", font=("Segoe UI Semibold", 9)).grid(row=0, column=0, sticky="w", padx=10, pady=(6,2))
        self.ent_user = ttk.Entry(body)
        self.ent_user.grid(row=1, column=0, sticky="ew", padx=10)

        tk.Label(body, text="Password FTP", bg="#ffffff", anchor="w", font=("Segoe UI Semibold", 9)).grid(row=0, column=1, sticky="w", padx=10, pady=(6,2))
        self.ent_pass = ttk.Entry(body, show="*")
        self.ent_pass.grid(row=1, column=1, sticky="ew", padx=10)

        tk.Label(body, text="Ruta Local", bg="#ffffff", anchor="w", font=("Segoe UI Semibold", 9)).grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(8,2))
        fr_ruta = tk.Frame(body, bg="#ffffff")
        fr_ruta.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(0,8))
        fr_ruta.columnconfigure(0, weight=1)
        self.ent_ruta = ttk.Entry(fr_ruta)
        self.ent_ruta.insert(0, os.path.abspath("."))
        self.ent_ruta.grid(row=0, column=0, sticky="ew")
        btn_folder = RoundedButton(fr_ruta, icon="📂", command=self.select_folder, fill="#0093d0", radius=8)
        btn_folder.grid(row=0, column=1, padx=(8,0))

        # Action row
        row_actions = tk.Frame(container, bg="#f4f6f7")
        row_actions.pack(pady=(4, 12))

        self.btn_guardar = RoundedButton(row_actions, text="GUARDAR CONFIG", icon="💾", command=self.save_config, fill="#8cc63f")
        self.btn_guardar.grid(row=0, column=0, padx=8)
        self.btn_descargar = RoundedButton(row_actions, text="EJECUTAR DESCARGA", icon="▶️", command=self.simulate_workflow, fill="#0093d0")
        self.btn_descargar.grid(row=0, column=1, padx=8)
        self.btn_reporte = RoundedButton(row_actions, text="GENERAR REPORTE", icon="📊", command=self.simulate_report, fill="#0093d0")
        self.btn_reporte.grid(row=0, column=2, padx=8)

        # Dashboard (2 columns)
        dash_frame = tk.Frame(container, bg="#f4f6f7")
        dash_frame.pack(fill="both", expand=True)
        dash_left = RoundedCard(dash_frame, title="Estado del Sistema", icon="📊", fill="#ffffff")
        dash_left.pack(side="left", fill="both", expand=True, padx=(0,10), pady=6)
        dl = dash_left.get_body()
        tk.Label(dl, text="Base de Datos", bg="#ffffff", font=("Segoe UI Semibold", 10)).pack(anchor="w", padx=10, pady=(6,2))
        tk.Label(dl, text="156.4 MB (demo)", bg="#ffffff", fg="#16a34a").pack(anchor="w", padx=10)

        dash_right = RoundedCard(dash_frame, title="Flujo de Trabajo", icon="🚀", fill="#ffffff")
        dash_right.pack(side="left", fill="both", expand=True, padx=(10,0), pady=6)
        dr = dash_right.get_body()
        tk.Label(dr, text="1) Configurar credenciales\n2) Ejecutar Descarga + BD\n3) Visualizar/Generar Reporte", bg="#ffffff", justify="left").pack(anchor="w", padx=10, pady=6)

    def build_tab_archivos(self):
        container = tk.Frame(self.tab_archivos, bg="#f4f6f7")
        container.pack(fill="both", expand=True, padx=20, pady=10)

        card = RoundedCard(container, title="Archivos a descargar", icon="📥", fill="#ffffff")
        card.pack(fill="both", expand=True)
        body = card.get_body()
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=0)

        self.ent_file_name = ttk.Entry(body)
        self.ent_file_name.grid(row=0, column=0, sticky="ew", padx=10, pady=6)
        btn_add = RoundedButton(body, text="Agregar", command=self.add_file_demo, fill="#8cc63f")
        btn_add.grid(row=0, column=1, padx=8, pady=6)

        cols = ("nombre", "ruta")
        self.tree_files = ttk.Treeview(body, columns=cols, show="headings", height=8)
        self.tree_files.heading("nombre", text="Nombre Archivo")
        self.tree_files.heading("ruta", text="Ruta FTP")
        self.tree_files.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=(0,10))
        body.rowconfigure(1, weight=1)

        # seed demo items
        for i in range(4):
            self.tree_files.insert("", "end", values=(f"trsd_{i+1}", f"/Reportes/Predespacho/{i+1}"))

    def build_tab_filtros(self):
        container = tk.Frame(self.tab_filtros, bg="#f4f6f7")
        container.pack(fill="both", expand=True, padx=20, pady=10)

        card = RoundedCard(container, title="Filtros reporte", icon="🔎", fill="#ffffff")
        card.pack(fill="both", expand=True)
        body = card.get_body()

        tk.Label(body, text="Tabla", bg="#ffffff").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        tk.Label(body, text="Campo", bg="#ffffff").grid(row=0, column=1, padx=8, pady=6, sticky="w")
        tk.Label(body, text="Valor", bg="#ffffff").grid(row=0, column=2, padx=8, pady=6, sticky="w")

        self.ent_r_tab = ttk.Entry(body); self.ent_r_tab.grid(row=1, column=0, padx=8, pady=6)
        self.ent_r_cam = ttk.Entry(body); self.ent_r_cam.grid(row=1, column=1, padx=8, pady=6)
        self.ent_r_val = ttk.Entry(body); self.ent_r_val.grid(row=1, column=2, padx=8, pady=6)
        btn_add = RoundedButton(body, text="Agregar filtro", command=self.add_filter_demo, fill="#8cc63f")
        btn_add.grid(row=1, column=3, padx=10, pady=6)

        self.tree_filtros = ttk.Treeview(body, columns=("tabla","campo","valor"), show="headings", height=8)
        self.tree_filtros.heading("tabla", text="Tabla"); self.tree_filtros.heading("campo", text="Campo"); self.tree_filtros.heading("valor", text="Valor")
        self.tree_filtros.grid(row=2, column=0, columnspan=4, sticky="nsew", padx=8, pady=(0,8))
        body.rowconfigure(2, weight=1)

    def build_tab_visualizador(self):
        container = tk.Frame(self.tab_visualizador, bg="#f4f6f7")
        container.pack(fill="both", expand=True, padx=12, pady=12)
        controls = tk.Frame(container, bg="#f4f6f7")
        controls.pack(fill="x")

        tk.Label(controls, text="Archivo:", bg="#f4f6f7").pack(side="left", padx=(6,4))
        self.var_tabla = tk.StringVar()
        self.cb_tabla = ttk.Combobox(controls, textvariable=self.var_tabla, values=["trsd_1","trsd_2","PEI"])
        self.cb_tabla.pack(side="left", padx=4)
        tk.Label(controls, text="Variable:", bg="#f4f6f7").pack(side="left", padx=(12,4))
        self.var_val = tk.StringVar()
        self.cb_val = ttk.Combobox(controls, textvariable=self.var_val, values=["Valor","Promedio","Suma"])
        self.cb_val.pack(side="left", padx=4)

        btn_graf = RoundedButton(controls, text="GRAFICAR", command=self.plot_demo, fill="#0093d0")
        btn_graf.pack(side="left", padx=10)

        self.frame_plot = tk.Frame(container, bg="#ffffff")
        self.frame_plot.pack(fill="both", expand=True, pady=(12,0))

        # initial placeholder
        lbl = tk.Label(self.frame_plot, text="Aquí se mostrará el gráfico", bg="#ffffff")
        lbl.pack(expand=True)

    # -------------------------
    # Demo / helpers
    # -------------------------
    def select_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.ent_ruta.delete(0, tk.END)
            self.ent_ruta.insert(0, d)
            print(f"Ruta seleccionada: {d}")

    def add_file_demo(self):
        n = self.ent_file_name.get().strip()
        if not n:
            messagebox.showwarning("Nombre vacío", "Ingrese nombre de archivo.")
            return
        self.tree_files.insert("", "end", values=(n, "/Reportes/Predespacho"))
        self.ent_file_name.delete(0, tk.END)
        print(f"Archivo agregado: {n}")

    def add_filter_demo(self):
        t = self.ent_r_tab.get().strip() or "trsd"
        c = self.ent_r_cam.get().strip() or "Recurso"
        v = self.ent_r_val.get().strip() or "IXEG"
        self.tree_filtros.insert("", "end", values=(t,c,v))
        self.ent_r_tab.delete(0, tk.END); self.ent_r_cam.delete(0, tk.END); self.ent_r_val.delete(0, tk.END)
        print(f"Filtro agregado: {t} - {c} = {v}")

    def save_config(self):
        data = {
            "usuario": self.ent_user.get(),
            "password": self.ent_pass.get(),
            "ruta_local": self.ent_ruta.get(),
            "fecha_guardado": str(datetime.now())
        }
        try:
            with open(APP_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("✅ Configuración guardada.")
            messagebox.showinfo("Guardado", "Configuración demo guardada.")
        except Exception as e:
            print("❌ Error guardando:", e)
            messagebox.showerror("Error", str(e))

    def load_config(self):
        if os.path.exists(APP_CONFIG_FILE):
            try:
                with open(APP_CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                print("⚙️ Config demo cargada.")
                return cfg
            except:
                return {}
        return {}

    def simulate_workflow(self):
        def job():
            print("🚀 INICIANDO DESCARGA DE ARCHIVOS (demo)...")
            time.sleep(0.8)
            print("⬇️ Descargando archivos desde XM FTP... (simulado)")
            time.sleep(1.2)
            print("💾 Procesando base de datos... (simulado)")
            time.sleep(1.3)
            print("✅ PROCESO DEMO FINALIZADO.")
        threading.Thread(target=job).start()

    def simulate_report(self):
        print("📈 Generando reporte (demo)...")
        self.after(1200, lambda: print("✅ Reporte Excel generado: Reporte_Horizontal_XM_demo.xlsx"))

    def plot_demo(self):
        # simple random timeseries demo using matplotlib if available
        for w in self.frame_plot.winfo_children():
            w.destroy()
        if not HAS_MPL:
            tk.Label(self.frame_plot, text="matplotlib no disponible en este entorno.", bg="#ffffff").pack()
            return
        fig = Figure(figsize=(8,4), dpi=100, facecolor="#ffffff")
        ax = fig.add_subplot(111)
        days = [datetime(2025,1, i+1) for i in range(15)]
        values = [random.uniform(50, 200) for _ in days]
        ax.plot(days, values, marker='o', color="#0093d0")
        ax.set_title("Demo Serie Temporal")
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate(rotation=45)
        canvas = FigureCanvasTkAgg(fig, master=self.frame_plot)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        toolbar = NavigationToolbar2Tk(canvas, self.frame_plot)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")

# Simple print redirector to show logs in the GUI text widget
class PrintRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget
    def write(self, s):
        try:
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, str(s))
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
        except tk.TclError:
            pass
    def flush(self):
        pass

# ---------------------------
# Run the app
# ---------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = AplicacionXM(root)
    root.mainloop()