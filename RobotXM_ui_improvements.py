# Updated UI helpers: add robust Canvas-based RoundedCard and RoundedButton while keeping ttk Card as fallback.
# - Provides:
#    * RoundedCard: Canvas-backed card with true rounded corners that hosts arbitrary widgets reliably.
#    * RoundedButton: Canvas-backed clickable button with hover/press visual states and keyboard support.
#    * Retains Card (ttk-based) and RoundedButtonWrapper for backwards compatibility.
# - Usage:
#    from RobotXM_ui_improvements import RoundedCard, RoundedButton, Card, RoundedButtonWrapper, CustomDropdownWithTooltip
#    card = RoundedCard(parent, title="Mi tarjeta", icon="🚀"); card.pack(...)
#    body = card.get_body(); ttk.Label(body, text="Contenido").pack()
#    btn = RoundedButton(parent, text="Aceptar", command=on_ok); btn.pack()
#
# Notes:
# - This implementation aims to keep rounded visuals while avoiding fragile layout bugs:
#   * The Canvas draws the rounded rectangle and positions an inner Frame via create_window.
#   * Resize handling updates the drawn background and inner window size.
#   * The button is keyboard accessible (Tab focusable) and fires on <Return> or <space>.
# - Requires no external image assets. Pillow optional but not required.
#
import tkinter as tk
from tkinter import ttk

# Try to import Pillow for higher-quality antialias if available (optional)
try:
    from PIL import Image, ImageTk, ImageDraw
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

# ----------------------
# Helper: rounded rectangle drawing on Canvas
# ----------------------
def _draw_rounded_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    """
    Draw a rounded rectangle on canvas by composing arcs and rectangles.
    Returns the id of the created polygon/objects group (we return a list of ids).
    """
    ids = []
    # create rectangles and arcs for corners to approximate rounded rect
    # center rectangles
    ids.append(canvas.create_rectangle(x1 + r, y1, x2 - r, y2, **kwargs))
    ids.append(canvas.create_rectangle(x1, y1 + r, x2, y2 - r, **kwargs))
    # corners as arcs (use pieslice)
    ids.append(canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, style='pieslice', **kwargs))
    ids.append(canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, style='pieslice', **kwargs))
    ids.append(canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, style='pieslice', **kwargs))
    ids.append(canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, style='pieslice', **kwargs))
    return ids

# ----------------------
# RoundedCard: Canvas wrapper that hosts a Frame inside a rounded background
# ----------------------
class RoundedCard(tk.Frame):
    """
    Canvas-backed rounded card that hosts a normal Frame (accessible for layout).
    Parameters:
      - parent: Tk container
      - radius: corner radius in px
      - padding: internal padding (left/right/top/bottom)
      - bg: parent background color (outside card)
      - fill: card fill color
      - outline: card border color
      - outline_width: border thickness
      - title/icon: optional header (drawn inside the inner body as a small header frame)
    """
    def __init__(self, parent, title=None, icon=None, radius=12, padding=(12, 10, 12, 10),
                 bg=None, fill="#ffffff", outline="#e5e7eb", outline_width=1, *args, **kwargs):
        super().__init__(parent, bg=bg or parent.cget("bg"), *args, **kwargs)
        self.radius = radius
        self.pad_left, self.pad_top, self.pad_right, self.pad_bottom = padding
        self.fill = fill
        self.outline = outline
        self.outline_width = outline_width

        # Canvas that draws background
        self._canvas = tk.Canvas(self, highlightthickness=0, bg=self.cget("bg"))
        self._canvas.pack(fill="both", expand=True)
        # Inner frame where user places widgets
        self._inner = tk.Frame(self._canvas, bg=self.fill)
        # Create window; we will manage its size in _on_configure
        self._win_id = self._canvas.create_window(self.pad_left, self.pad_top, window=self._inner, anchor="nw")

        # Optional header inside inner
        if title or icon:
            header = tk.Frame(self._inner, bg=self.fill)
            header.pack(fill="x", pady=(0, 6))
            if icon:
                tk.Label(header, text=icon, bg=self.fill, font=("Segoe UI", 12)).pack(side="left", padx=(0,8))
            if title:
                tk.Label(header, text=title, bg=self.fill, font=("Segoe UI Semibold", 11), fg="#1f2937").pack(side="left")

        # Bindings
        self._canvas.bind("<Configure>", self._on_configure)
        # To support expand/shrink when inner content changes
        self._inner.bind("<Configure>", self._on_inner_configure)

    def _on_configure(self, event):
        # Redraw rounded background and resize inner window
        w = max(1, event.width)
        h = max(1, event.height)
        self._canvas.delete("card_bg")
        r = self.radius
        ow = self.outline_width
        # Draw using canvas shapes with 'card_bg' tag to later delete
        # We'll draw a single rounded rectangle approximated by polygons/arcs
        # Simpler approach: draw a rectangle with corner ovals to emulate rounding
        x1, y1, x2, y2 = 1, 1, w-2, h-2
        # center rectangle
        self._canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=self.fill, outline="", tags=("card_bg",))
        self._canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=self.fill, outline="", tags=("card_bg",))
        # corners as ovals
        self._canvas.create_oval(x1, y1, x1 + 2*r, y1 + 2*r, fill=self.fill, outline="", tags=("card_bg",))
        self._canvas.create_oval(x2 - 2*r, y1, x2, y1 + 2*r, fill=self.fill, outline="", tags=("card_bg",))
        self._canvas.create_oval(x1, y2 - 2*r, x1 + 2*r, y2, fill=self.fill, outline="", tags=("card_bg",))
        self._canvas.create_oval(x2 - 2*r, y2 - 2*r, x2, y2, fill=self.fill, outline="", tags=("card_bg",))
        # border - draw same shapes but with no fill and outline color
        if ow > 0:
            # center rect border
            self._canvas.create_line(x1 + r, y1, x2 - r, y1, fill=self.outline, width=ow, tags=("card_bg",))
            self._canvas.create_line(x1 + r, y2, x2 - r, y2, fill=self.outline, width=ow, tags=("card_bg",))
            self._canvas.create_line(x1, y1 + r, x1, y2 - r, fill=self.outline, width=ow, tags=("card_bg",))
            self._canvas.create_line(x2, y1 + r, x2, y2 - r, fill=self.outline, width=ow, tags=("card_bg",))
            # corners border as arcs (approx with create_arc)
            try:
                self._canvas.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, style='arc', outline=self.outline, width=ow, tags=("card_bg",))
                self._canvas.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, style='arc', outline=self.outline, width=ow, tags=("card_bg",))
                self._canvas.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, style='arc', outline=self.outline, width=ow, tags=("card_bg",))
                self._canvas.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, style='arc', outline=self.outline, width=ow, tags=("card_bg",))
            except Exception:
                pass

        # Update inner window size to respect padding
        inner_w = max(10, w - (self.pad_left + self.pad_right))
        inner_h = max(10, h - (self.pad_top + self.pad_bottom))
        self._canvas.coords(self._win_id, self.pad_left, self.pad_top)
        self._canvas.itemconfig(self._win_id, width=inner_w, height=inner_h)

    def _on_inner_configure(self, event):
        # If inner requests a larger size than canvas, expand canvas (helpful when pack_propagate interferes)
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        req_w = event.width + (self.pad_left + self.pad_right)
        req_h = event.height + (self.pad_top + self.pad_bottom)
        if req_w > cw or req_h > ch:
            # Grow the canvas size
            self._canvas.config(width=max(cw, req_w), height=max(ch, req_h))

    def get_body(self):
        return self._inner

# ----------------------
# RoundedButton: Canvas-based clickable control with rounded background
# ----------------------
class RoundedButton(tk.Canvas):
    """
    Small rounded button implemented on a Canvas for consistent rounded corners.
    Supports:
      - text label, optional icon (emoji/text)
      - hover and pressed states
      - keyboard activation (Tab focusable, <Return> and <space>)
      - command callback
    """
    def __init__(self, parent, text="", icon=None, command=None, radius=10,
                 padding=(12,6), bg=None, fill="#0093d0", fill_hover="#007bb5", fill_pressed="#0070a0",
                 fg="white", outline=None, outline_width=0, *args, **kwargs):
        super().__init__(parent, height=32, highlightthickness=0, bg=bg or parent.cget("bg"))
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
        self._bg_id = None
        self._text_id = None

        # focusable: use tk built-in focus engine by binding focus events
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Key>", self._on_key)
        self.bind("<FocusIn>", lambda e: self._draw())
        self.bind("<FocusOut>", lambda e: self._draw())

        # Make widget focusable
        self.configure(takefocus=1)
        # initial draw
        self._draw()

        # ensure the canvas resizes to fit text
        self.update_idletasks()
        self.bind("<Configure>", lambda e: self._draw())

    def _current_fill(self):
        if self._state == "pressed":
            return self.fill_pressed
        if self._state == "hover":
            return self.fill_hover
        return self.fill

    def _draw(self):
        # clear
        self.delete("all")
        w = max(60, self.winfo_width() or 80)
        h = max(24, self.winfo_height() or 32)
        r = self.radius
        fill_color = self._current_fill()
        # draw rounded background (approx with ovals + rect)
        x1, y1, x2, y2 = 1, 1, w-2, h-2
        # center rectangles
        self.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill_color, width=0, tags=("bg",))
        self.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill_color, width=0, tags=("bg",))
        # corners
        self.create_oval(x1, y1, x1 + 2*r, y1 + 2*r, fill=fill_color, width=0, tags=("bg",))
        self.create_oval(x2 - 2*r, y1, x2, y1 + 2*r, fill=fill_color, width=0, tags=("bg",))
        self.create_oval(x1, y2 - 2*r, x1 + 2*r, y2, fill=fill_color, width=0, tags=("bg",))
        self.create_oval(x2 - 2*r, y2 - 2*r, x2, y2, fill=fill_color, width=0, tags=("bg",))
        # outline if requested
        if self.outline and self.outline_width:
            try:
                self.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, style='arc', outline=self.outline, width=self.outline_width)
                self.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, style='arc', outline=self.outline, width=self.outline_width)
                self.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, style='arc', outline=self.outline, width=self.outline_width)
                self.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, style='arc', outline=self.outline, width=self.outline_width)
            except Exception:
                pass

        # draw text + optional icon
        label = f"{self.icon + '  ' if self.icon else ''}{self.text}"
        self._text_id = self.create_text(w/2, h/2, text=label, fill=self.fg, font=("Segoe UI Semibold", 10))
        # update requested size to fit label
        bbox = self.bbox(self._text_id)
        if bbox:
            text_width = bbox[2] - bbox[0]
            desired_w = text_width + self.pad_x * 2
            if desired_w > w:
                # expand widget
                self.config(width=desired_w)
                # redraw to fit new width
                # avoid recursion: schedule redraw after configure if needed
                self.after_idle(self._draw)

    # Event handlers
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
        # only trigger if pointer is still over widget
        x, y = event.x, event.y
        if 0 <= x <= self.winfo_width() and 0 <= y <= self.winfo_height():
            # call command
            if callable(self.command):
                try:
                    self.command()
                except Exception:
                    pass
        self._state = "hover"
        self._draw()

    def _on_key(self, event):
        if event.keysym in ("Return", "space"):
            # simulate press/release
            self._on_press()
            self.after(80, lambda: (self._on_release(tk.Event())))
            # attempt to call command
            if callable(self.command):
                try:
                    self.command()
                except Exception:
                    pass

# ----------------------
# Backwards-compatible simple ttk-based Card and Button wrapper
# ----------------------
class Card(ttk.Frame):
    """Fallback ttk-based Card (keeps behavior for non-rounded usage)."""
    def __init__(self, parent, title=None, icon=None, *args, **kwargs):
        super().__init__(parent, style="Card.TFrame", padding=(10,8), *args, **kwargs)
        if title or icon:
            header = ttk.Frame(self, style="CardHeader.TFrame")
            header.pack(fill="x", pady=(0,6))
            if icon:
                lbl_icon = ttk.Label(header, text=icon, style="CardIcon.TLabel")
                lbl_icon.pack(side="left", padx=(0,8))
            if title:
                lbl_title = ttk.Label(header, text=title, style="CardTitle.TLabel")
                lbl_title.pack(side="left")
        self.body = ttk.Frame(self, style="CardBody.TFrame")
        self.body.pack(fill="both", expand=True)
    def get_body(self):
        return self.body

class RoundedButtonWrapper(ttk.Button):
    """Compatibility wrapper: use style-based button (no true rounded corners)."""
    def __init__(self, parent, text, command=None, style="Primary.TButton", width=None, *args, **kwargs):
        super().__init__(parent, text=text, command=command, style=style, *args, **kwargs)
        if width:
            try:
                self.configure(width=width)
            except Exception:
                pass

# ----------------------
# CustomDropdownWithTooltip (exported here)
# ----------------------
class CustomDropdownWithTooltip:
    """Searchable dropdown with tooltip for long items.
    Kept minimal; prefer the version already reviewed that handles Escape/FocusOut.
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
