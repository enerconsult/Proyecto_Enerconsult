import tkinter as tk

class CustomDropdownWithTooltip:
    def __init__(self, master, items):
        self.master = master
        self.items = items
        self.entry = tk.Entry(master, width=15)
        self.entry.pack(pady=10)
        self.entry.bind("<Button-1>", self.show_dropdown)

        self.dropdown = None
        self.tooltip = None
        self.current_index = None

    def show_dropdown(self, event=None):
        if self.dropdown:
            self.dropdown.destroy()
        self.dropdown = tk.Toplevel(self.master)
        self.dropdown.wm_overrideredirect(True)
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        self.dropdown.geometry(f"+{x}+{y}")

        self.listbox = tk.Listbox(self.dropdown, width=15, height=min(6, len(self.items)))
        self.listbox.pack()
        for item in self.items:
            self.listbox.insert(tk.END, item)

        self.listbox.bind("<Motion>", self.on_motion)
        self.listbox.bind("<Leave>", self.hide_tooltip)
        self.listbox.bind("<ButtonRelease-1>", self.select_item)

    def on_motion(self, event):
        index = self.listbox.nearest(event.y)
        if index != self.current_index:
            self.current_index = index
            self.show_tooltip(index, event)

    def show_tooltip(self, index, event):
        self.hide_tooltip()
        text = self.listbox.get(index)
        x = event.x_root + 20
        y = event.y_root + 10
        self.tooltip = tw = tk.Toplevel(self.master)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=text, background="lightyellow",
                         relief="solid", borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

    def select_item(self, event):
        index = self.listbox.curselection()
        if index:
            self.entry.delete(0, tk.END)
            self.entry.insert(0, self.listbox.get(index))
        self.dropdown.destroy()
        self.hide_tooltip()

# Ejemplo de uso
root = tk.Tk()
root.geometry("400x200")

items = [
    "variable_con_nombre_muy_largo_001",
    "variable_con_n",
    "otra",
    "corta/variable_extensa_002",
    "variable_con_nombre_muy_largo_002"
]

CustomDropdownWithTooltip(root, items)

root.mainloop()
