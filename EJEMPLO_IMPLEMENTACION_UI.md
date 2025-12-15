# 💻 Ejemplo de Implementación - Mejoras UI

Este documento contiene ejemplos de código para implementar las mejoras propuestas en el diseño UI.

---

## 🎨 1. Estilos Mejorados - Función `configurar_estilos_modernos()`

```python
def configurar_estilos_modernos(self):
    style = ttk.Style()
    style.theme_use('clam')
    
    # --- PALETA DE COLORES MEJORADA ---
    c_azul_primario = "#0093d0"
    c_azul_hover = "#007bb5"
    c_azul_claro = "#e0f2fe"
    c_verde_primario = "#8cc63f"
    c_verde_hover = "#7ab828"
    c_fondo_principal = "#f8fafc"  # Más claro que antes
    c_fondo_secundario = "#ffffff"
    c_borde_claro = "#e2e8f0"
    c_texto_primario = "#1e293b"  # Más oscuro para mejor contraste
    c_texto_secundario = "#64748b"
    c_texto_placeholder = "#94a3b8"
    c_exito = "#10b981"
    c_error = "#ef4444"
    
    self.root.configure(bg=c_fondo_principal)
    
    # --- FUENTES MEJORADAS ---
    f_h1 = ("Segoe UI", 24, "bold")
    f_h2 = ("Segoe UI", 18, "bold")
    f_h3 = ("Segoe UI", 14, "bold")
    f_body = ("Segoe UI", 11)
    f_small = ("Segoe UI", 9)
    f_mono = ("Consolas", 10)
    
    # --- CONFIGURACIÓN GENERAL ---
    style.configure(".", 
        background=c_fondo_principal, 
        foreground=c_texto_primario, 
        font=f_body
    )
    style.configure("TFrame", background=c_fondo_principal)
    style.configure("TLabelframe", 
        background=c_fondo_secundario, 
        borderwidth=1, 
        relief="solid",
        bordercolor=c_borde_claro
    )
    style.configure("TLabelframe.Label", 
        background=c_fondo_secundario, 
        foreground=c_azul_primario, 
        font=f_h3
    )
    
    # --- PESTAÑAS MEJORADAS ---
    style.configure("TNotebook", 
        background=c_fondo_principal, 
        borderwidth=0, 
        tabmargins=[0, 0, 0, 0], 
        relief="flat"
    )
    style.configure("TNotebook.Tab", 
        padding=[20, 12],  # Más espacioso
        font=("Segoe UI", 11, "bold"),
        background="#f1f5f9",  # Gris muy claro para hover
        foreground=c_texto_secundario,
        borderwidth=0,
        relief="flat"
    )
    style.map("TNotebook.Tab", 
        background=[
            ("selected", c_fondo_secundario),  # Blanco cuando está seleccionada
            ("active", "#f1f5f9")  # Gris claro al pasar mouse
        ],
        foreground=[
            ("selected", c_azul_primario),  # Azul cuando está seleccionada
            ("active", c_azul_primario)
        ],
        expand=[("selected", [0, 0, 0, 0])]
    )
    
    # --- BOTONES MEJORADOS ---
    # Botón Primario (Azul) - Más grande y con mejor padding
    style.configure("Primary.TButton", 
        font=("Segoe UI", 11, "bold"),
        background=c_azul_primario,
        foreground="white",
        borderwidth=0,
        focuscolor="none",
        padding=[16, 12]  # Más padding
    )
    style.map("Primary.TButton", 
        background=[
            ("active", c_azul_hover),
            ("disabled", "#cbd5e1")
        ]
    )
    
    # Botón Success (Verde)
    style.configure("Success.TButton", 
        font=("Segoe UI", 11, "bold"),
        background=c_verde_primario,
        foreground="white",
        borderwidth=0,
        focuscolor="none",
        padding=[16, 12]
    )
    style.map("Success.TButton", 
        background=[
            ("active", c_verde_hover),
            ("disabled", "#cbd5e1")
        ]
    )
    
    # Botón Danger (Rojo)
    style.configure("Danger.TButton", 
        font=("Segoe UI", 11, "bold"),
        background=c_error,
        foreground="white",
        borderwidth=0,
        focuscolor="none",
        padding=[16, 12]
    )
    style.map("Danger.TButton", 
        background=[
            ("active", "#dc2626"),
            ("disabled", "#cbd5e1")
        ]
    )
    
    # Botón Neutro (Default)
    style.configure("TButton", 
        font=f_body,
        padding=[12, 8]
    )
    
    # --- TREEVIEW (TABLAS) MEJORADAS ---
    style.configure("Treeview", 
        background=c_fondo_secundario,
        foreground=c_texto_primario,
        fieldbackground=c_fondo_secundario,
        rowheight=32,  # Más alto para mejor legibilidad
        font=f_body,
        borderwidth=1,
        relief="solid",
        bordercolor=c_borde_claro
    )
    style.configure("Treeview.Heading", 
        font=("Segoe UI", 11, "bold"),
        background="#f1f5f9",  # Header con fondo gris claro
        foreground=c_texto_primario,
        padding=[12, 8],
        relief="flat"
    )
    style.map("Treeview", 
        background=[
            ("selected", c_azul_primario),
            ("!selected", c_fondo_secundario)
        ],
        foreground=[
            ("selected", "white"),
            ("!selected", c_texto_primario)
        ]
    )
    
    # Filas alternadas (requiere lógica adicional en el código)
    # Se implementa en la función que crea las filas
    
    # --- ENTRADAS MEJORADAS ---
    style.configure("TEntry", 
        padding=[12, 10],  # Más padding interno
        relief="solid",
        borderwidth=1,
        bordercolor=c_borde_claro,
        fieldbackground=c_fondo_secundario
    )
    style.map("TEntry", 
        bordercolor=[
            ("focus", c_azul_primario),  # Borde azul al enfocar
            ("!focus", c_borde_claro)
        ],
        lightcolor=[
            ("focus", c_azul_claro)  # Resplandor suave al enfocar
        ]
    )
    
    # --- SCROLLBAR MEJORADA ---
    style.configure("Vertical.TScrollbar", 
        background="#cbd5e1",
        troughcolor=c_fondo_principal,
        borderwidth=0,
        arrowsize=14,
        width=14
    )
    style.map("Vertical.TScrollbar", 
        background=[
            ("active", "#94a3b8"),
            ("!active", "#cbd5e1")
        ]
    )
    
    # --- CARD STYLES MEJORADOS ---
    style.configure("Card.TFrame", 
        background=c_fondo_secundario,
        relief="flat",
        borderwidth=0
    )
    style.configure("CardHeader.TFrame", 
        background="#fafbfc"  # Fondo ligeramente diferente
    )
    style.configure("CardTitle.TLabel", 
        font=("Segoe UI", 14, "bold"),
        background="#fafbfc",
        foreground=c_azul_primario
    )
    style.configure("CardIcon.TLabel", 
        font=("Segoe UI", 16),
        foreground=c_azul_primario,
        background="#fafbfc"
    )
    style.configure("CardBody.TFrame", 
        background=c_fondo_secundario
    )
```

---

## 🎴 2. Encabezado Mejorado

```python
def construir_encabezado_logo(self):
    # Frame principal con altura aumentada y gradiente simulado
    frame_header = tk.Frame(self.root, bg="#f0f9ff", height=120)  # Azul muy claro
    frame_header.pack(fill="x", side="top")
    
    # Frame interno para centrar contenido
    frame_content = tk.Frame(frame_header, bg="#f0f9ff")
    frame_content.pack(expand=True, fill="both", pady=15)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ruta_logo = os.path.join(script_dir, LOGO_FILENAME)
    
    if TIENE_PILLOW and os.path.exists(ruta_logo):
        try:
            pil_img = Image.open(ruta_logo)
            base_height = 80  # Más grande que antes (60px)
            w_percent = (base_height / float(pil_img.size[1]))
            w_size = int((float(pil_img.size[0]) * float(w_percent)))
            pil_img = pil_img.resize((w_size, base_height), RESAMPLE_LANCZOS)
            self.logo_img = ImageTk.PhotoImage(pil_img)
            lbl_logo = tk.Label(frame_content, image=self.logo_img, bg="#f0f9ff")
            lbl_logo.pack()
            
            # Título debajo del logo (opcional)
            lbl_title = tk.Label(
                frame_content, 
                text="Suite XM Inteligente", 
                bg="#f0f9ff",
                fg="#0093d0",
                font=("Segoe UI", 16, "bold")
            )
            lbl_title.pack(pady=(5, 0))
        except Exception as e:
            print(f"⚠️ Error logo: {e}")
    
    # Línea separadora sutil
    separator = tk.Frame(self.root, bg="#e2e8f0", height=1)
    separator.pack(fill="x", side="top")
```

---

## 📊 3. Tabla con Filas Alternadas

```python
def crear_tabla_con_filas_alternadas(self, parent, columns, data):
    """Crea una tabla Treeview con filas alternadas"""
    tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
    
    # Configurar columnas
    for col in columns:
        tree.heading(col, text=col.title(), anchor="w")
        tree.column(col, width=150, anchor="w")
    
    # Insertar datos con colores alternados
    for i, row_data in enumerate(data):
        tags = ("even",) if i % 2 == 0 else ("odd",)
        tree.insert("", "end", values=row_data, tags=tags)
    
    # Configurar colores de filas alternadas
    tree.tag_configure("even", background="#ffffff")
    tree.tag_configure("odd", background="#f8fafc")
    
    # Hover effect (requiere evento bind)
    def on_hover(event):
        item = tree.identify_row(event.y)
        if item:
            tree.set(item)
            # Cambiar temporalmente el fondo
            current_tags = tree.item(item, "tags")
            if "hover" not in current_tags:
                tree.item(item, tags=current_tags + ("hover",))
                tree.tag_configure("hover", background="#e0f2fe")
    
    def on_leave(event):
        for item in tree.get_children():
            tags = list(tree.item(item, "tags"))
            if "hover" in tags:
                tags.remove("hover")
                # Restaurar color original basado en índice
                index = tree.index(item)
                tags.append("even" if index % 2 == 0 else "odd")
                tree.item(item, tags=tags)
    
    tree.bind("<Motion>", on_hover)
    tree.bind("<Leave>", on_leave)
    
    return tree
```

---

## 🎯 4. Input con Placeholder Mejorado

```python
class ModernEntry(ttk.Entry):
    """Entry con placeholder mejorado y focus visual"""
    def __init__(self, parent, placeholder="", *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.placeholder = placeholder
        self.placeholder_color = "#94a3b8"
        self.normal_color = "#1e293b"
        
        # Insertar placeholder inicial
        if placeholder:
            self.insert(0, placeholder)
            self.configure(foreground=self.placeholder_color, font=("Segoe UI", 11, "italic"))
        
        # Bind eventos
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
    
    def _on_focus_in(self, event):
        if self.get() == self.placeholder:
            self.delete(0, tk.END)
            self.configure(foreground=self.normal_color, font=("Segoe UI", 11))
    
    def _on_focus_out(self, event):
        if not self.get():
            self.insert(0, self.placeholder)
            self.configure(foreground=self.placeholder_color, font=("Segoe UI", 11, "italic"))
    
    def get_value(self):
        """Retorna el valor real (sin placeholder)"""
        value = self.get()
        return "" if value == self.placeholder else value
```

---

## 📈 5. Dashboard Mejorado con Métricas Destacadas

```python
def crear_metric_card(self, parent, icon, value, label, color="#0093d0"):
    """Crea una tarjeta de métrica destacada"""
    card = tk.Frame(parent, bg="#ffffff", relief="flat", bd=0)
    
    # Frame interno con padding
    inner = tk.Frame(card, bg="#ffffff")
    inner.pack(fill="both", expand=True, padx=20, pady=20)
    
    # Icono grande
    icon_label = tk.Label(
        inner, 
        text=icon, 
        font=("Segoe UI", 32),
        bg="#ffffff",
        fg=color
    )
    icon_label.pack(side="left", padx=(0, 15))
    
    # Frame para texto
    text_frame = tk.Frame(inner, bg="#ffffff")
    text_frame.pack(side="left", fill="both", expand=True)
    
    # Valor destacado
    value_label = tk.Label(
        text_frame,
        text=str(value),
        font=("Segoe UI", 24, "bold"),
        bg="#ffffff",
        fg="#1e293b"
    )
    value_label.pack(anchor="w")
    
    # Etiqueta
    label_label = tk.Label(
        text_frame,
        text=label,
        font=("Segoe UI", 10),
        bg="#ffffff",
        fg="#64748b"
    )
    label_label.pack(anchor="w")
    
    return card

# Uso en actualizar_dashboard():
def actualizar_dashboard(self):
    # Limpiar dashboard previo
    for w in self.frame_dashboard.winfo_children():
        w.destroy()
    
    # Crear contenedor con grid
    grid_container = tk.Frame(self.frame_dashboard, bg="#f8fafc")
    grid_container.pack(fill="both", expand=True, padx=20, pady=20)
    
    # Configurar grid de 3 columnas
    for i in range(3):
        grid_container.columnconfigure(i, weight=1, uniform="metric")
    
    # Obtener métricas
    db_size = "125.5 MB"  # Ejemplo
    n_files = len(self.tree_files.get_children())
    n_filters = len(self.tree_filtros.get_children())
    
    # Crear tarjetas de métricas
    card1 = self.crear_metric_card(grid_container, "💾", db_size, "Base de Datos", "#0093d0")
    card1.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
    
    card2 = self.crear_metric_card(grid_container, "📥", n_files, "Archivos Configurados", "#8cc63f")
    card2.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
    
    card3 = self.crear_metric_card(grid_container, "📋", n_filters, "Filtros Reporte", "#f59e0b")
    card3.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")
```

---

## 🖥️ 6. Consola de Monitoreo Mejorada

```python
def crear_consola_mejorada(self, parent):
    """Crea una consola de monitoreo con estilo mejorado"""
    # Frame contenedor
    console_container = tk.Frame(parent, bg="#1e293b")
    console_container.pack(fill="both", expand=False, padx=10, pady=5)
    
    # Header de la consola
    header_frame = tk.Frame(console_container, bg="#1e293b", height=35)
    header_frame.pack(fill="x", side="top")
    
    # Título
    title_label = tk.Label(
        header_frame,
        text=">_ Monitor de Ejecución",
        font=("Segoe UI", 10, "bold"),
        bg="#1e293b",
        fg="white",
        anchor="w"
    )
    title_label.pack(side="left", padx=15, pady=8)
    
    # Botón limpiar (opcional)
    def limpiar_consola():
        self.txt_console.config(state="normal")
        self.txt_console.delete(1.0, tk.END)
        self.txt_console.config(state="disabled")
    
    btn_clear = tk.Button(
        header_frame,
        text="🗑️ Limpiar",
        command=limpiar_consola,
        bg="#374151",
        fg="white",
        font=("Segoe UI", 9),
        relief="flat",
        padx=10,
        pady=5,
        cursor="hand2"
    )
    btn_clear.pack(side="right", padx=10, pady=5)
    
    # Área de texto con fondo más oscuro
    self.txt_console = scrolledtext.ScrolledText(
        console_container,
        height=8,
        state='disabled',
        bg='#0f172a',  # Más oscuro
        fg='#22c55e',  # Verde más suave
        font=('Consolas', 10),
        insertbackground='#22c55e',
        selectbackground='#374151',
        selectforeground='white',
        wrap='word',
        relief='flat',
        borderwidth=0
    )
    self.txt_console.pack(fill="both", expand=True, padx=0, pady=0)
    
    # Configurar scrollbar personalizada
    scrollbar = self.txt_console.vbar
    scrollbar.configure(
        bg="#374151",
        troughcolor="#0f172a",
        activebackground="#4b5563",
        borderwidth=0
    )
    
    return self.txt_console
```

---

## 🎨 7. Clase Card Mejorada con Sombra Simulada

```python
class ModernCard(ttk.Frame):
    """Card mejorada con sombra simulada y mejor espaciado"""
    def __init__(self, parent, title=None, icon=None, *args, **kwargs):
        # Frame externo para sombra (simulada con múltiples frames)
        self.shadow_frame = tk.Frame(parent, bg="#e2e8f0")
        self.shadow_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Frame principal (card)
        super().__init__(self.shadow_frame, style="Card.TFrame", padding=(20, 16))
        
        # Header si corresponde
        if title or icon:
            header = ttk.Frame(self, style="CardHeader.TFrame")
            header.pack(fill="x", pady=(0, 12))
            
            if icon:
                lbl_icon = ttk.Label(
                    header, 
                    text=icon, 
                    style="CardIcon.TLabel"
                )
                lbl_icon.pack(side="left", padx=(0, 8))
            
            if title:
                lbl_title = ttk.Label(
                    header, 
                    text=title, 
                    style="CardTitle.TLabel"
                )
                lbl_title.pack(side="left")
        
        # Body
        self.body = ttk.Frame(self, style="CardBody.TFrame")
        self.body.pack(fill="both", expand=True)
    
    def get_body(self):
        return self.body
    
    def pack(self, **kwargs):
        """Override pack para empaquetar el shadow_frame"""
        self.shadow_frame.pack(**kwargs)
        super().pack(fill="both", expand=True)
```

---

## 📝 Notas de Implementación

1. **Compatibilidad**: Estos ejemplos son compatibles con tkinter estándar y no requieren librerías adicionales.

2. **Limitaciones**: 
   - Las sombras reales no son posibles en tkinter, se simulan con frames
   - Los bordes redondeados requieren imágenes o Canvas
   - Las animaciones son básicas usando `after()`

3. **Orden de Implementación**:
   - Primero actualizar `configurar_estilos_modernos()`
   - Luego mejorar componentes individuales
   - Finalmente agregar efectos y animaciones

4. **Pruebas**: Probar cada componente individualmente antes de integrar todo.

---

**Versión**: 1.0  
**Fecha**: Enero 2025

