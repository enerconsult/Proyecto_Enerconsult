# Recomendaciones y componentes alternativos para RobotXM_App_mejoras_v02.py
# - Contiene:
#   * CustomDropdownWithTooltip (correcciones: width var, init listbox, Escape/focus handling)
#   * Card (simple, usa ttk.Frame en vez de Canvas para evitar problemas)
#   * RoundedButtonWrapper (usa ttk.Button con estilos en lugar de Canvas)
# Cómo usar:
#   from RobotXM_ui_improvements import CustomDropdownWithTooltip, Card, RoundedButtonWrapper
#   Reemplazar llamadas actuales a create_card / create_rounded_button por estos componentes.
#
# Nota: no intento reimplementar todas las funciones UI del archivo grande:
# copia gradualmente estas clases y adapta llamadas (p. ej. create_card -> Card(parent, title=...))
#
#
import tkinter as tk
from tkinter import ttk

# ----------------------
#  UTIL: fallback PIL resampling
# ----------------------
try:
    from PIL import Image
    # compatibilidad: Image.Resampling existe en Pillow >= 9.1.0
    RESAMPLE_LANCZOS = getattr(Image, "Resampling", Image).LANCZOS
except Exception:
    RESAMPLE_LANCZOS = None

# ======================
# CustomDropdownWithTooltip (mejorada)
# ======================
class CustomDropdownWithTooltip:
    """Dropdown searchable con tooltip para items largos.
    Mejoras:
      - Corrige errores de width/variables no definidas.
      - Inicializa atributos (listbox).
      - Maneja Escape y FocusOut para cerrar dropdown.
      - No depender de overrideredirect exclusivamente (pero permite usarlo).
    Uso:
      cb = CustomDropdownWithTooltip(parent, textvariable=var, width=25, command=callback)
      cb.entry.grid(...)  # el Entry es el widget visible
      cb.update_items(['A','B', ...])
    """
    def __init__(self, master, textvariable=None, width=18, command=None, tooltip_threshold=15, dropdown_height=160):
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

        # initialize attributes
        self.dropdown = None
        self.tooltip = None
        self.listbox = None
        self.current_index = None

    def focus_listbox(self, event=None):
        if not self.dropdown:
            self.show_dropdown()
        if self.listbox:
            self.listbox.focus_set()
            # ensure selection visible
            if self.listbox.size() > 0:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(0)
                self.listbox.activate(0)

    def update_items(self, new_items):
        self.items = [str(x) for x in new_items]
        self.filtered_items = self.items[:]

    def show_dropdown(self, event=None):
        # toggle
        if self.dropdown:
            self.close_dropdown()
            return

        # create dropdown Toplevel
        self.dropdown = tk.Toplevel(self.master)
        # Use transient and topmost to avoid some overrideredirect issues
        try:
            self.dropdown.wm_overrideredirect(True)
            self.dropdown.attributes("-topmost", True)
        except Exception:
            # fallback for platforms that don't support attributes
            pass

        # compute position relative to entry
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        w_pixels = max(self.entry.winfo_width(), 150)

        # geometry: width x height + x + y
        height = self.dropdown_height
        self.dropdown.geometry(f"{w_pixels}x{height}+{x}+{y}")

        # frame + scrollbar + listbox
        frame_list = tk.Frame(self.dropdown, bd=0)
        frame_list.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(frame_list, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        chars_w = width_chars(w_pixels)
        self.listbox = tk.Listbox(frame_list, width=chars_w, height=8, yscrollcommand=scrollbar.set,
                                  exportselection=False, bg="#ffffff", fg="#2c3e50",
                                  selectbackground="#0093d0", selectforeground="#ffffff",
                                  font=("Segoe UI", 10), borderwidth=0)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)

        # populate
        self.listbox.delete(0, tk.END)
        for item in self.filtered_items:
            self.listbox.insert(tk.END, item)

        # bindings
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
        # position
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
            # update listbox
            self.listbox.delete(0, tk.END)
            for item in self.filtered_items:
                self.listbox.insert(tk.END, item)
        else:
            if query:
                # show only if there's a query (prevents immediate dropdown on focus)
                self.show_dropdown()

# ======================
# Card (simple, ttk-based)
# ======================
class Card(ttk.Frame):
    """Card visual simple usando ttk.Frame y padding.
    No pretende dibujar esquinas redondeadas, pero brinda un contenedor consistente,
    con header opcional.
    Reemplaza create_card con algo mucho más robusto.
    """
    def __init__(self, parent, title=None, icon=None, *args, **kwargs):
        super().__init__(parent, style="Card.TFrame", padding=(10, 8))
        # crear header si corresponde
        if title or icon:
            header = ttk.Frame(self, style="CardHeader.TFrame")
            header.pack(fill="x", pady=(0, 6))
            if icon:
                lbl_icon = ttk.Label(header, text=icon, style="CardIcon.TLabel")
                lbl_icon.pack(side="left", padx=(0, 8))
            if title:
                lbl_title = ttk.Label(header, text=title, style="CardTitle.TLabel")
                lbl_title.pack(side="left")

        # body: donde el usuario pone widgets
        self.body = ttk.Frame(self, style="CardBody.TFrame")
        self.body.pack(fill="both", expand=True)

    def get_body(self):
        return self.body

# ======================
# RoundedButtonWrapper (usa ttk.Button + estilo)
# ======================
class RoundedButtonWrapper(ttk.Button):
    """Pequeña envoltura para crear un botón con estilo ya definido en tu 'configurar_estilos_modernos'.
    Llamar con style='Primary.TButton' o 'Success.TButton' etc.
    """
    def __init__(self, parent, text, command=None, style="Primary.TButton", width=None, *args, **kwargs):
        super().__init__(parent, text=text, command=command, style=style, *args, **kwargs)
        if width:
            try:
                self.configure(width=width)
            except Exception:
                pass

# ======================
# Helper: width_chars
# ======================
def width_chars(pixels):
    # Estimación conservadora
    return max(10, int(pixels / 7))

# ======================
# Recomendaciones de estilos (añadir a configurar_estilos_modernos)
# ======================
# En tu función configurar_estilos_modernos(), añade algo así:
#
# style.configure("Card.TFrame", background=c_blanco, relief="flat")
# style.configure("CardHeader.TFrame", background=c_blanco)
# style.configure("CardTitle.TLabel", font=("Segoe UI Semibold", 11), background=c_blanco, foreground=c_azul_corp)
# style.configure("CardIcon.TLabel", background=c_blanco)
# style.configure("CardBody.TFrame", background=c_blanco)
#
# Para botones: ya tienes "Primary.TButton" y "Success.TButton": úsalos directamente en lugar de canvas custom.
