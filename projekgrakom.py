import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, simpledialog, messagebox
from PIL import Image, ImageDraw, ImageTk
import math
import time
import pickle
from collections import deque


class PaintApp:
    """
    Python Paint - Grafika Komputer

    Pengembangan tahap berikutnya:
    1. Mode algoritma grafika komputer:
       - Garis biasa
       - DDA Line
       - Bresenham Line
       - Midpoint Circle
       - Midpoint Ellipse
    2. Objek/primitif:
       - Brush, eraser, fill, picker, text
       - Line, rectangle, ellipse, triangle, star
       - Titik koordinat manual
    3. Transformasi 2D pada area seleksi:
       - Translasi / geser
       - Rotasi 90 derajat
       - Skala
       - Flip horizontal / vertikal
    4. Animasi sederhana:
       - Bouncing object
       - Rotation animation pada area seleksi
    5. Optimasi input-output:
       - Brush tidak melakukan render penuh setiap gerakan mouse
       - Render penuh hanya saat operasi besar selesai
    """

    def __init__(self, root):
        self.root = root
        self.root.title("Python Paint - Aplikasi Grafika Komputer")
        self.root.geometry("1500x880")
        self.root.minsize(1180, 740)
        self.root.configure(bg="#1f1f1f")

        self.canvas_width = 1100
        self.canvas_height = 650
        self.zoom = 1.0

        self.tool = "brush"
        self.shape = "rectangle"
        self.algorithm = "normal"
        self.primary_color = "#139de0"
        self.secondary_color = "#ffffff"
        self.brush_size = tk.IntVar(value=6)
        self.opacity = tk.IntVar(value=100)
        self.text_value = tk.StringVar(value="Teks")
        self.show_grid = tk.BooleanVar(value=False)
        self.animation_speed = tk.IntVar(value=30)  # FPS animasi, dapat diubah dari UI

        self.start_x = None
        self.start_y = None
        self.last_x = None
        self.last_y = None
        self.preview_item = None
        self.image_item = None
        self.canvas_offset_x = 40
        self.canvas_offset_y = 30

        self.history = []
        self.redo_stack = []
        self.layers = []
        self.active_layer_index = 0

        self.selection = None
        self.selection_item = None
        self.selected_object = None

        self.animation_running = False
        self.anim_obj = None
        self.anim_vx = 7
        self.anim_vy = 5
        self.anim_angle = 0
        self.anim_after_id = None
        self.animation_background_tk = None
        self.animation_base_image = None
        self.animation_selection_bounds = None

        self.drag_has_changed = False
        self.status_pending = False
        self.pending_status = "Ready"

        self.create_image_layer("Layer 1")
        self.build_ui()
        self.full_render()
        self.save_history(clear_redo=False)

    # =====================================================
    # DATA & LAYER
    # =====================================================
    def create_image_layer(self, name):
        image = Image.new("RGBA", (self.canvas_width, self.canvas_height), (255, 255, 255, 0))
        if not self.layers:
            draw = ImageDraw.Draw(image)
            draw.rectangle([0, 0, self.canvas_width, self.canvas_height], fill=(255, 255, 255, 255))
        self.layers.append({"name": name, "image": image, "visible": True})
        self.active_layer_index = len(self.layers) - 1

    def active_image(self):
        return self.layers[self.active_layer_index]["image"]

    def composite_image(self):
        result = Image.new("RGBA", (self.canvas_width, self.canvas_height), (255, 255, 255, 255))
        for layer in self.layers:
            if layer["visible"]:
                result.alpha_composite(layer["image"])
        return result

    def save_history(self, clear_redo=True):
        snapshot = {
            "layers": [layer["image"].copy() for layer in self.layers],
            "meta": [{"name": layer["name"], "visible": layer["visible"]} for layer in self.layers],
            "active": self.active_layer_index,
            "size": (self.canvas_width, self.canvas_height),
        }
        self.history.append(snapshot)
        self.history = self.history[-25:]
        if clear_redo:
            self.redo_stack.clear()

    def restore_snapshot(self, snapshot):
        self.canvas_width, self.canvas_height = snapshot["size"]
        self.layers = []
        for image, meta in zip(snapshot["layers"], snapshot["meta"]):
            self.layers.append({"name": meta["name"], "visible": meta["visible"], "image": image.copy()})
        self.active_layer_index = snapshot["active"]
        self.sync_size_entries()
        self.refresh_layer_list()
        self.full_render()

    # =====================================================
    # UI
    # =====================================================
    def build_ui(self):
        self.build_menu_bar()
        self.build_toolbar()
        self.build_workspace()
        self.build_statusbar()

    def build_menu_bar(self):
        top = tk.Frame(self.root, bg="#1f1f1f", height=42)
        top.pack(side=tk.TOP, fill=tk.X)

        menu_items = [
            ("File", self.show_file_menu),
            ("Edit", self.show_edit_menu),
            ("Draw", self.show_draw_menu),
            ("Transform", self.show_transform_menu),
            ("Animation", self.show_animation_menu),
            ("View", self.show_view_menu),
            ("Help", self.show_help),
        ]
        for text, command in menu_items:
            tk.Button(top, text=text, command=command, fg="white", bg="#1f1f1f", activebackground="#333333", activeforeground="white", relief=tk.FLAT, padx=10, pady=8, font=("Segoe UI", 10)).pack(side=tk.LEFT)

        quick_buttons = [
            ("💾", self.save_image, "Simpan PNG"),
            ("📁", self.save_project, "Simpan project .gkp"),
            ("📂", self.open_project, "Buka project .gkp"),
            ("🖼", self.open_image, "Buka Gambar"),
            ("↶", self.undo, "Undo"),
            ("↷", self.redo, "Redo"),
            ("🗑", self.clear_canvas, "Bersihkan"),
        ]
        for text, command, tip in quick_buttons:
            btn = tk.Button(top, text=text, command=command, bg="#2b2b2b", fg="white", relief=tk.FLAT, width=4)
            btn.pack(side=tk.LEFT, padx=2, pady=6)
            self.create_tooltip(btn, tip)

        tk.Label(top, text="Python Paint - Grafika Komputer", fg="#bdbdbd", bg="#1f1f1f", font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT, padx=16)


    def build_toolbar(self):
        """Toolbar dibuat lebih ringkas agar kanvas tidak terdorong terlalu jauh ke bawah.

        Panel Animation dan Layers dipindahkan ke panel kiri supaya tombol Transform tidak
        terpotong di layar 1366/1536 px. Indikator tool aktif dibuat kecil, bukan panel tinggi.
        """
        toolbar = tk.Frame(self.root, bg="#242424", height=104)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        toolbar.pack_propagate(False)

        self.active_tool_label = tk.Label(
            toolbar,
            text="Tool: brush",
            bg="#0d6efd",
            fg="white",
            padx=8,
            pady=3,
            font=("Segoe UI", 9, "bold"),
            anchor="center",
            width=18,
        )
        self.active_tool_label.pack(side=tk.LEFT, padx=(6, 6), pady=10)

        self.add_group(toolbar, "Selection", [
            ("▣", "Seleksi area", lambda: self.set_tool("select")),
            ("✂", "Crop", lambda: self.set_tool("crop")),
            ("⌖", "Titik manual", self.draw_manual_point),
        ])

        self.add_group(toolbar, "Image", [
            ("🖼", "Buka gambar", self.open_image),
            ("⟲", "Putar kanvas kiri", lambda: self.rotate_canvas("left")),
            ("⟳", "Putar kanvas kanan", lambda: self.rotate_canvas("right")),
        ])

        self.add_group(toolbar, "Tools", [
            ("✏", "Brush", lambda: self.set_tool("brush")),
            ("🧽", "Eraser", lambda: self.set_tool("eraser")),
            ("🪣", "Flood fill / bucket fill", lambda: self.set_tool("fill")),
            ("💧", "Pipet warna", lambda: self.set_tool("picker")),
            ("A", "Text", lambda: self.set_tool("text")),
        ])

        brush_group = tk.Frame(toolbar, bg="#242424", padx=8)
        brush_group.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(brush_group, text="Ukuran", bg="#242424", fg="white", font=("Segoe UI", 9)).pack(anchor="w")
        tk.Scale(
            brush_group,
            from_=1,
            to=60,
            orient=tk.HORIZONTAL,
            variable=self.brush_size,
            bg="#242424",
            fg="white",
            troughcolor="#3a3a3a",
            highlightthickness=0,
            length=118,
            showvalue=True,
            sliderlength=14,
        ).pack()
        tk.Label(brush_group, text="Brush", bg="#242424", fg="#cfcfcf", font=("Segoe UI", 8)).pack(side=tk.BOTTOM)

        shape_group = tk.Frame(toolbar, bg="#242424", padx=8)
        shape_group.pack(side=tk.LEFT, fill=tk.Y)
        grid = tk.Frame(shape_group, bg="#242424")
        grid.pack(pady=(5, 2))
        shape_buttons = [("╱", "line"), ("□", "rectangle"), ("○", "ellipse"), ("△", "triangle"), ("★", "star")]
        for i, (label, shape) in enumerate(shape_buttons):
            btn = tk.Button(grid, text=label, width=3, bg="#303030", fg="white", relief=tk.FLAT, command=lambda s=shape: self.set_shape(s))
            btn.grid(row=0, column=i, padx=1, pady=1)
            self.create_tooltip(btn, f"Shape: {shape}")
        tk.Label(shape_group, text="Algoritma", bg="#242424", fg="white", font=("Segoe UI", 9)).pack(anchor="w")
        self.algorithm_combo = ttk.Combobox(shape_group, state="readonly", width=15, values=["normal", "DDA Line", "Bresenham Line", "Midpoint Circle", "Midpoint Ellipse"])
        self.algorithm_combo.set("normal")
        self.algorithm_combo.pack()
        self.algorithm_combo.bind("<<ComboboxSelected>>", self.change_algorithm)
        tk.Label(shape_group, text="Shapes & Algorithm", bg="#242424", fg="#cfcfcf", font=("Segoe UI", 8)).pack(side=tk.BOTTOM)

        color_group = tk.Frame(toolbar, bg="#242424", padx=8)
        color_group.pack(side=tk.LEFT, fill=tk.Y)
        top = tk.Frame(color_group, bg="#242424")
        top.pack(pady=(3, 1))
        self.primary_btn = tk.Button(top, bg=self.primary_color, width=3, command=self.choose_primary_color)
        self.primary_btn.pack(side=tk.LEFT, padx=2)
        self.secondary_btn = tk.Button(top, bg=self.secondary_color, width=3, command=self.choose_secondary_color)
        self.secondary_btn.pack(side=tk.LEFT, padx=2)
        palette = tk.Frame(color_group, bg="#242424")
        palette.pack()
        colors = ["#000000", "#ffffff", "#808080", "#b00020", "#ff3030", "#ff8a35", "#ffe600", "#34b853", "#139de0", "#4b55d6", "#9b59b6", "#cfcfcf", "#c57b4b", "#ff9eb5", "#ffc928", "#fff0a8", "#b6e421", "#9bd5e5", "#7780c8", "#bbb6de"]
        for i, color in enumerate(colors):
            tk.Button(palette, bg=color, width=2, height=1, relief=tk.RIDGE, command=lambda c=color: self.set_primary_color(c)).grid(row=i // 10, column=i % 10, padx=1, pady=1)
        tk.Label(color_group, text="Colours", bg="#242424", fg="#cfcfcf", font=("Segoe UI", 8)).pack(side=tk.BOTTOM)

        transform_group = tk.Frame(toolbar, bg="#242424", padx=8)
        transform_group.pack(side=tk.LEFT, fill=tk.Y)
        tgrid = tk.Frame(transform_group, bg="#242424")
        tgrid.pack(pady=(7, 2))
        transform_buttons = [
            ("↔", lambda: self.flip_selection("h"), "Flip horizontal"),
            ("↕", lambda: self.flip_selection("v"), "Flip vertikal"),
            ("⟳", self.rotate_selection, "Rotasi area"),
            ("⤢", self.scale_selection, "Skala area"),
            ("➜", self.translate_selection, "Translasi area"),
            ("M", self.show_matrix_info, "Matriks transformasi"),
        ]
        for i, (label, command, tip) in enumerate(transform_buttons):
            btn = tk.Button(tgrid, text=label, width=3, bg="#303030", fg="white", relief=tk.FLAT, command=command)
            btn.grid(row=i // 3, column=i % 3, padx=2, pady=2)
            self.create_tooltip(btn, tip)
        tk.Label(transform_group, text="Transform", bg="#242424", fg="#cfcfcf", font=("Segoe UI", 8)).pack(side=tk.BOTTOM)


    def add_group(self, parent, title, items):
        group = tk.Frame(parent, bg="#242424", padx=6)
        group.pack(side=tk.LEFT, fill=tk.Y)
        box = tk.Frame(group, bg="#242424")
        box.pack(pady=(8, 2))
        for i, (symbol, tooltip, command) in enumerate(items):
            btn = tk.Button(box, text=symbol, command=command, width=3, height=1, bg="#303030", fg="white", relief=tk.FLAT, font=("Segoe UI", 11))
            btn.grid(row=i // 3, column=i % 3, padx=2, pady=2)
            self.create_tooltip(btn, tooltip)
        tk.Label(group, text=title, bg="#242424", fg="#cfcfcf", font=("Segoe UI", 8)).pack(side=tk.BOTTOM)


    def build_workspace(self):
        workspace = tk.Frame(self.root, bg="#181818")
        workspace.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        left_panel = tk.Frame(workspace, bg="#181818", width=245)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        left_panel.pack_propagate(False)

        panel = tk.LabelFrame(left_panel, text="Ukuran & Presisi", bg="#202020", fg="white", padx=10, pady=8)
        panel.pack(fill=tk.X)

        tk.Label(panel, text="Lebar px", bg="#202020", fg="white").pack(anchor="w")
        self.width_entry = tk.Entry(panel, bg="#303030", fg="white", insertbackground="white")
        self.width_entry.insert(0, str(self.canvas_width))
        self.width_entry.pack(fill=tk.X, pady=2)

        tk.Label(panel, text="Tinggi px", bg="#202020", fg="white").pack(anchor="w")
        self.height_entry = tk.Entry(panel, bg="#303030", fg="white", insertbackground="white")
        self.height_entry.insert(0, str(self.canvas_height))
        self.height_entry.pack(fill=tk.X, pady=2)

        tk.Button(panel, text="Terapkan Ukuran Kanvas", bg="#0d6efd", fg="white", relief=tk.FLAT, command=self.apply_canvas_size).pack(fill=tk.X, pady=6)

        tk.Label(panel, text="Teks", bg="#202020", fg="white").pack(anchor="w")
        tk.Entry(panel, textvariable=self.text_value, bg="#303030", fg="white", insertbackground="white").pack(fill=tk.X, pady=2)

        opacity_row = tk.Frame(panel, bg="#202020")
        opacity_row.pack(fill=tk.X, pady=(3, 0))
        tk.Label(opacity_row, text="Opasitas", bg="#202020", fg="white").pack(side=tk.LEFT)
        tk.Label(opacity_row, textvariable=self.opacity, bg="#202020", fg="#d0d0d0").pack(side=tk.RIGHT)
        tk.Scale(panel, from_=5, to=100, orient=tk.HORIZONTAL, variable=self.opacity, bg="#202020", fg="white", troughcolor="#3a3a3a", highlightthickness=0, showvalue=False, sliderlength=14).pack(fill=tk.X)

        tk.Checkbutton(panel, text="Tampilkan Grid", variable=self.show_grid, command=self.full_render, bg="#202020", fg="white", selectcolor="#303030", activebackground="#202020").pack(anchor="w", pady=3)
        tk.Button(panel, text="Simpan PNG", bg="#198754", fg="white", relief=tk.FLAT, command=self.save_image).pack(fill=tk.X, pady=3)
        tk.Button(panel, text="Bersihkan", bg="#dc3545", fg="white", relief=tk.FLAT, command=self.clear_canvas).pack(fill=tk.X, pady=3)

        object_panel = tk.LabelFrame(left_panel, text="Info Objek / Area", bg="#202020", fg="white", padx=10, pady=8)
        object_panel.pack(fill=tk.X, pady=8)
        self.object_info = tk.Label(object_panel, text="Belum ada seleksi", bg="#202020", fg="#d0d0d0", justify=tk.LEFT, anchor="w")
        self.object_info.pack(fill=tk.X)
        tk.Button(object_panel, text="Ambil Area Seleksi", bg="#303030", fg="white", relief=tk.FLAT, command=self.capture_selection).pack(fill=tk.X, pady=3)
        tk.Button(object_panel, text="Hapus Seleksi", bg="#303030", fg="white", relief=tk.FLAT, command=self.clear_selection).pack(fill=tk.X, pady=3)

        self.build_layer_animation_panels(left_panel)

        algo_panel = tk.LabelFrame(left_panel, text="Koordinat Manual", bg="#202020", fg="white", padx=10, pady=8)
        algo_panel.pack(fill=tk.X, pady=8)
        self.x1_entry = self.small_entry(algo_panel, "X1", "100")
        self.y1_entry = self.small_entry(algo_panel, "Y1", "100")
        self.x2_entry = self.small_entry(algo_panel, "X2", "300")
        self.y2_entry = self.small_entry(algo_panel, "Y2", "220")
        tk.Button(algo_panel, text="Gambar dari Angka", bg="#0d6efd", fg="white", relief=tk.FLAT, command=self.draw_from_numbers).pack(fill=tk.X, pady=5)

        canvas_frame = tk.Frame(workspace, bg="#181818")
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.canvas = tk.Canvas(canvas_frame, bg="#181818", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Motion>", self.on_mouse_motion_status)
        self.canvas.bind("<Escape>", lambda event: self.clear_selection())
        self.canvas.focus_set()


    def build_layer_animation_panels(self, parent):
        """Panel samping untuk fitur yang sebelumnya membuat toolbar terlalu lebar."""
        layer_panel = tk.LabelFrame(parent, text="Layers", bg="#202020", fg="white", padx=10, pady=8)
        layer_panel.pack(fill=tk.X, pady=8)
        layer_row = tk.Frame(layer_panel, bg="#202020")
        layer_row.pack(fill=tk.X)
        tk.Button(layer_row, text="+ Layer", bg="#303030", fg="white", relief=tk.FLAT, command=self.add_layer).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        tk.Button(layer_row, text="👁", bg="#303030", fg="white", relief=tk.FLAT, command=self.toggle_layer).pack(side=tk.LEFT, padx=(3, 0))
        self.layer_combo = ttk.Combobox(layer_panel, state="readonly", width=18)
        self.layer_combo.pack(fill=tk.X, pady=(5, 0))
        self.layer_combo.bind("<<ComboboxSelected>>", self.change_layer)
        self.refresh_layer_list()

        anim_panel = tk.LabelFrame(parent, text="Animation", bg="#202020", fg="white", padx=10, pady=8)
        anim_panel.pack(fill=tk.X, pady=8)
        row = tk.Frame(anim_panel, bg="#202020")
        row.pack(fill=tk.X)
        tk.Button(row, text="Bounce", bg="#303030", fg="white", relief=tk.FLAT, command=self.start_bounce_animation).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        tk.Button(row, text="Rotate", bg="#303030", fg="white", relief=tk.FLAT, command=self.start_rotate_animation).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        tk.Button(row, text="Stop", bg="#8b1e1e", fg="white", relief=tk.FLAT, command=self.stop_animation).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))
        tk.Button(anim_panel, text="Export GIF", bg="#303030", fg="white", relief=tk.FLAT, command=self.export_animation_gif).pack(fill=tk.X, pady=4)
        fps_row = tk.Frame(anim_panel, bg="#202020")
        fps_row.pack(fill=tk.X)
        tk.Label(fps_row, text="FPS", bg="#202020", fg="white").pack(side=tk.LEFT)
        tk.Label(fps_row, textvariable=self.animation_speed, bg="#202020", fg="#d0d0d0").pack(side=tk.RIGHT)
        tk.Scale(anim_panel, from_=5, to=60, orient=tk.HORIZONTAL, variable=self.animation_speed, bg="#202020", fg="white", troughcolor="#3a3a3a", highlightthickness=0, showvalue=False, sliderlength=14).pack(fill=tk.X)

    def small_entry(self, parent, label, default):
        row = tk.Frame(parent, bg="#202020")
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text=label, width=4, bg="#202020", fg="white").pack(side=tk.LEFT)
        entry = tk.Entry(row, bg="#303030", fg="white", insertbackground="white")
        entry.insert(0, default)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        return entry


    def build_statusbar(self):
        status = tk.Frame(self.root, bg="#222222", height=34)
        status.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_label = tk.Label(status, text="Ready", bg="#222222", fg="#d0d0d0", anchor="w")
        self.status_label.pack(side=tk.LEFT, padx=12)
        self.tool_status_label = tk.Label(status, text="Tool: brush", bg="#222222", fg="#9fd0ff", anchor="w", font=("Segoe UI", 9, "bold"))
        self.tool_status_label.pack(side=tk.LEFT, padx=10)
        tk.Button(status, text="-", bg="#303030", fg="white", relief=tk.FLAT, command=lambda: self.change_zoom(-0.1)).pack(side=tk.RIGHT, padx=3)
        tk.Button(status, text="+", bg="#303030", fg="white", relief=tk.FLAT, command=lambda: self.change_zoom(0.1)).pack(side=tk.RIGHT, padx=3)
        self.zoom_label = tk.Label(status, text="100%", bg="#222222", fg="#d0d0d0")
        self.zoom_label.pack(side=tk.RIGHT, padx=8)

    def full_render(self):
        self.canvas.delete("all")
        image = self.composite_image()
        display_size = (max(1, int(self.canvas_width * self.zoom)), max(1, int(self.canvas_height * self.zoom)))
        if self.zoom != 1.0:
            image = image.resize(display_size, Image.Resampling.BILINEAR)
        self.tk_image = ImageTk.PhotoImage(image)
        self.image_item = self.canvas.create_image(self.canvas_offset_x, self.canvas_offset_y, image=self.tk_image, anchor=tk.NW)
        self.canvas.create_rectangle(self.canvas_offset_x, self.canvas_offset_y, self.canvas_offset_x + display_size[0], self.canvas_offset_y + display_size[1], outline="#dddddd", tags="border")
        if self.show_grid.get():
            self.draw_grid_items()
        self.draw_selection_box()
        self.canvas.config(scrollregion=(0, 0, display_size[0] + 100, display_size[1] + 100))
        self.zoom_label.config(text=f"{int(self.zoom * 100)}%")
        self.update_object_info()


    def draw_grid_items(self):
        """Grid dibuat lebih halus agar tidak mengganggu gambar utama."""
        step = max(8, int(50 * self.zoom))
        w = int(self.canvas_width * self.zoom)
        h = int(self.canvas_height * self.zoom)
        ox, oy = self.canvas_offset_x, self.canvas_offset_y
        for x in range(0, w + 1, step):
            self.canvas.create_line(ox + x, oy, ox + x, oy + h, fill="#ededed", tags="grid")
        for y in range(0, h + 1, step):
            self.canvas.create_line(ox, oy + y, ox + w, oy + y, fill="#ededed", tags="grid")

    def canvas_to_image_coords(self, event):
        x = int((self.canvas.canvasx(event.x) - self.canvas_offset_x) / self.zoom)
        y = int((self.canvas.canvasy(event.y) - self.canvas_offset_y) / self.zoom)
        return max(0, min(x, self.canvas_width - 1)), max(0, min(y, self.canvas_height - 1))

    def image_to_canvas_coords(self, x, y):
        return self.canvas_offset_x + x * self.zoom, self.canvas_offset_y + y * self.zoom

    # =====================================================
    # EVENTS
    # =====================================================
    def on_mouse_down(self, event):
        self.canvas.focus_set()
        x, y = self.canvas_to_image_coords(event)
        self.start_x = self.last_x = x
        self.start_y = self.last_y = y
        self.drag_has_changed = False

        # Kalau user mulai menggambar, seleksi lama tidak ikut tampil.
        if self.tool in ["brush", "eraser", "fill", "picker", "text", "shape"] and self.selection:
            self.selection = None
            self.selected_object = None
            self.canvas.delete("selection")
            self.canvas.delete("preview")

        if self.tool == "fill":
            filled = self.flood_fill(x, y, self.primary_color)
            if filled:
                self.save_history()
                self.full_render()
                self.update_status(f"Flood fill selesai: {filled} pixel diubah.")
            return
        if self.tool == "picker":
            pixel = self.composite_image().getpixel((x, y))
            self.set_primary_color("#%02x%02x%02x" % pixel[:3])
            return
        if self.tool == "text":
            draw = ImageDraw.Draw(self.active_image())
            draw.text((x, y), self.text_value.get(), fill=self.hex_to_rgba(self.primary_color))
            self.save_history()
            self.full_render()
            return
        if self.tool in ["brush", "eraser"]:
            self.draw_point_to_image(x, y)
            cx, cy = self.image_to_canvas_coords(x, y)
            r = max(1, self.brush_size.get() * self.zoom / 2)
            color = "#ffffff" if self.tool == "eraser" else self.primary_color
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline=color, tags="live_stroke")
            self.drag_has_changed = True

    def on_mouse_move(self, event):
        x, y = self.canvas_to_image_coords(event)
        self.update_status_throttled(f"Tool: {self.tool} | Posisi: {x}, {y} | Kanvas: {self.canvas_width} × {self.canvas_height}px")
        if self.start_x is None or self.start_y is None:
            return
        if self.tool in ["brush", "eraser"]:
            if x == self.last_x and y == self.last_y:
                return
            self.draw_line_to_image(self.last_x, self.last_y, x, y)
            color = "#ffffff" if self.tool == "eraser" else self.primary_color
            c1 = self.image_to_canvas_coords(self.last_x, self.last_y)
            c2 = self.image_to_canvas_coords(x, y)
            self.canvas.create_line(c1[0], c1[1], c2[0], c2[1], fill=color, width=max(1, self.brush_size.get() * self.zoom), capstyle=tk.ROUND, joinstyle=tk.ROUND, tags="live_stroke")
            self.last_x, self.last_y = x, y
            self.drag_has_changed = True
            return
        if self.tool == "shape":
            self.update_shape_preview(self.start_x, self.start_y, x, y)
            return
        if self.tool in ["select", "crop"]:
            self.selection = (self.start_x, self.start_y, x, y)
            self.update_selection_preview(self.start_x, self.start_y, x, y)

    def on_mouse_up(self, event):
        if self.start_x is None or self.start_y is None:
            return
        x, y = self.canvas_to_image_coords(event)
        if self.tool == "shape":
            self.draw_shape_to_image(self.start_x, self.start_y, x, y)
            self.save_history()
            self.clear_preview()
            self.full_render()
        elif self.tool in ["brush", "eraser"]:
            if self.drag_has_changed:
                self.save_history()
            self.full_render()
        elif self.tool == "crop":
            self.crop_to_selection(self.start_x, self.start_y, x, y)
            self.save_history()
            self.clear_preview()
            self.selection = None
            self.full_render()
        elif self.tool == "select":
            self.selection = self.normalize_selection(self.start_x, self.start_y, x, y)
            self.clear_preview()
            self.full_render()
        self.start_x = self.start_y = self.last_x = self.last_y = None
        self.drag_has_changed = False

    def on_mouse_motion_status(self, event):
        x, y = self.canvas_to_image_coords(event)
        self.update_status_throttled(f"Tool: {self.tool} | Posisi: {x}, {y} | Kanvas: {self.canvas_width} × {self.canvas_height}px")

    def on_right_click(self, event):
        self.choose_secondary_color()

    # =====================================================
    # DRAWING HELPERS
    # =====================================================
    def erase_alpha_circle(self, x, y, radius):
        """Menghapus pixel pada layer aktif.

        Layer background tetap dihapus menjadi putih, sedangkan layer tambahan
        dihapus menjadi transparan agar tidak menutup layer di bawahnya.
        """
        img = self.active_image()
        draw = ImageDraw.Draw(img)
        fill = (255, 255, 255, 255) if self.active_layer_index == 0 else (0, 0, 0, 0)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)

    def draw_point_to_image(self, x, y):
        r = max(1, self.brush_size.get() // 2)
        if self.tool == "eraser":
            self.erase_alpha_circle(x, y, r)
            return
        draw = ImageDraw.Draw(self.active_image())
        draw.ellipse((x - r, y - r, x + r, y + r), fill=self.hex_to_rgba(self.primary_color))

    def draw_line_to_image(self, x1, y1, x2, y2):
        draw = ImageDraw.Draw(self.active_image())
        width = max(1, self.brush_size.get())
        if self.tool == "eraser":
            fill = (255, 255, 255, 255) if self.active_layer_index == 0 else (0, 0, 0, 0)
            draw.line((x1, y1, x2, y2), fill=fill, width=width, joint="curve")
            r = max(1, width // 2)
            draw.ellipse((x2 - r, y2 - r, x2 + r, y2 + r), fill=fill)
            return
        color = self.hex_to_rgba(self.primary_color)
        draw.line((x1, y1, x2, y2), fill=color, width=width, joint="curve")
        r = max(1, width // 2)
        draw.ellipse((x2 - r, y2 - r, x2 + r, y2 + r), fill=color)

    def draw_shape_to_image(self, x1, y1, x2, y2):
        if self.algorithm == "DDA Line":
            self.draw_pixels(self.dda_line(x1, y1, x2, y2))
            return
        if self.algorithm == "Bresenham Line":
            self.draw_pixels(self.bresenham_line(x1, y1, x2, y2))
            return
        if self.algorithm == "Midpoint Circle":
            r = int(math.hypot(x2 - x1, y2 - y1))
            self.draw_pixels(self.midpoint_circle(x1, y1, r))
            return
        if self.algorithm == "Midpoint Ellipse":
            rx = abs(x2 - x1)
            ry = abs(y2 - y1)
            self.draw_pixels(self.midpoint_ellipse(x1, y1, rx, ry))
            return

        draw = ImageDraw.Draw(self.active_image())
        outline = self.hex_to_rgba(self.primary_color)
        fill = self.hex_to_rgba(self.secondary_color)
        width = max(1, self.brush_size.get())
        box = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        if self.shape == "line":
            draw.line((x1, y1, x2, y2), fill=outline, width=width)
        elif self.shape == "rectangle":
            draw.rectangle(box, outline=outline, fill=fill, width=width)
        elif self.shape == "ellipse":
            draw.ellipse(box, outline=outline, fill=fill, width=width)
        elif self.shape == "triangle":
            points = [(x1 + (x2 - x1) / 2, y1), (x2, y2), (x1, y2)]
            draw.polygon(points, outline=outline, fill=fill)
            draw.line(points + [points[0]], fill=outline, width=width)
        elif self.shape == "star":
            points = self.star_points((x1 + x2) / 2, (y1 + y2) / 2, abs(x2 - x1) / 2, abs(y2 - y1) / 2)
            draw.polygon(points, outline=outline, fill=fill)
            draw.line(points + [points[0]], fill=outline, width=width)

    def draw_pixels(self, points):
        draw = ImageDraw.Draw(self.active_image())
        color = self.hex_to_rgba(self.primary_color)
        size = max(1, self.brush_size.get())
        r = max(0, size // 2)
        for x, y in points:
            if 0 <= x < self.canvas_width and 0 <= y < self.canvas_height:
                if r <= 1:
                    draw.point((x, y), fill=color)
                else:
                    draw.rectangle((x - r, y - r, x + r, y + r), fill=color)

    def update_shape_preview(self, x1, y1, x2, y2):
        self.clear_preview()
        cx1, cy1 = self.image_to_canvas_coords(x1, y1)
        cx2, cy2 = self.image_to_canvas_coords(x2, y2)
        width = max(1, self.brush_size.get() * self.zoom)
        if self.algorithm == "DDA Line" or self.algorithm == "Bresenham Line":
            self.preview_item = self.canvas.create_line(cx1, cy1, cx2, cy2, fill=self.primary_color, width=width, dash=(4, 3), tags="preview")
            return
        if self.algorithm == "Midpoint Circle":
            r = math.hypot(cx2 - cx1, cy2 - cy1)
            self.preview_item = self.canvas.create_oval(cx1 - r, cy1 - r, cx1 + r, cy1 + r, outline=self.primary_color, width=width, dash=(4, 3), tags="preview")
            return
        if self.algorithm == "Midpoint Ellipse":
            self.preview_item = self.canvas.create_oval(cx1, cy1, cx2, cy2, outline=self.primary_color, width=width, dash=(4, 3), tags="preview")
            return
        if self.shape == "line":
            self.preview_item = self.canvas.create_line(cx1, cy1, cx2, cy2, fill=self.primary_color, width=width, tags="preview")
        elif self.shape == "rectangle":
            self.preview_item = self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline=self.primary_color, width=width, tags="preview")
        elif self.shape == "ellipse":
            self.preview_item = self.canvas.create_oval(cx1, cy1, cx2, cy2, outline=self.primary_color, width=width, tags="preview")
        elif self.shape == "triangle":
            points = [cx1 + (cx2 - cx1) / 2, cy1, cx2, cy2, cx1, cy2]
            self.preview_item = self.canvas.create_polygon(points, outline=self.primary_color, fill="", width=width, tags="preview")
        elif self.shape == "star":
            pts = self.star_points((cx1 + cx2) / 2, (cy1 + cy2) / 2, abs(cx2 - cx1) / 2, abs(cy2 - cy1) / 2)
            flat = [coord for p in pts for coord in p]
            self.preview_item = self.canvas.create_polygon(flat, outline=self.primary_color, fill="", width=width, tags="preview")

    def update_selection_preview(self, x1, y1, x2, y2):
        self.clear_preview()
        normalized = self.normalize_selection(x1, y1, x2, y2)
        if normalized:
            x1, y1, x2, y2 = normalized
        cx1, cy1 = self.image_to_canvas_coords(x1, y1)
        cx2, cy2 = self.image_to_canvas_coords(x2, y2)
        self.preview_item = self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline="#008cff", dash=(6, 4), width=2, tags="preview")

    def clear_preview(self):
        self.canvas.delete("preview")
        self.preview_item = None

    # =====================================================
    # ALGORITHMS
    # =====================================================
    def dda_line(self, x1, y1, x2, y2):
        """Algoritma DDA: membentuk garis dengan incremental floating-point.

        Output berupa daftar titik pixel yang kemudian digambar satu per satu.
        """
        dx = x2 - x1
        dy = y2 - y1
        steps = int(max(abs(dx), abs(dy)))
        if steps == 0:
            return [(x1, y1)]
        x_inc = dx / steps
        y_inc = dy / steps
        x, y = x1, y1
        points = []
        for _ in range(steps + 1):
            points.append((round(x), round(y)))
            x += x_inc
            y += y_inc
        return points

    def bresenham_line(self, x1, y1, x2, y2):
        """Algoritma Bresenham: garis berbasis keputusan integer.

        Lebih efisien dibanding DDA karena menghindari operasi pecahan saat
        menentukan pixel berikutnya.
        """
        points = []
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        while True:
            points.append((x1, y1))
            if x1 == x2 and y1 == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy
        return points

    def midpoint_circle(self, cx, cy, r):
        """Algoritma Midpoint Circle dengan simetri 8 arah."""
        points = []
        x = 0
        y = r
        p = 1 - r
        while x <= y:
            points.extend([
                (cx + x, cy + y), (cx - x, cy + y), (cx + x, cy - y), (cx - x, cy - y),
                (cx + y, cy + x), (cx - y, cy + x), (cx + y, cy - x), (cx - y, cy - x),
            ])
            x += 1
            if p < 0:
                p += 2 * x + 1
            else:
                y -= 1
                p += 2 * (x - y) + 1
        return points

    def midpoint_ellipse(self, cx, cy, rx, ry):
        """Algoritma Midpoint Ellipse dengan dua region keputusan."""
        points = []
        if rx == 0 or ry == 0:
            return points
        x = 0
        y = ry
        rx2 = rx * rx
        ry2 = ry * ry
        px = 0
        py = 2 * rx2 * y
        p = ry2 - (rx2 * ry) + (0.25 * rx2)
        while px < py:
            points.extend([(cx + x, cy + y), (cx - x, cy + y), (cx + x, cy - y), (cx - x, cy - y)])
            x += 1
            px += 2 * ry2
            if p < 0:
                p += ry2 + px
            else:
                y -= 1
                py -= 2 * rx2
                p += ry2 + px - py
        p = ry2 * ((x + 0.5) ** 2) + rx2 * ((y - 1) ** 2) - rx2 * ry2
        while y >= 0:
            points.extend([(cx + x, cy + y), (cx - x, cy + y), (cx + x, cy - y), (cx - x, cy - y)])
            y -= 1
            py -= 2 * rx2
            if p > 0:
                p += rx2 - py
            else:
                x += 1
                px += 2 * ry2
                p += rx2 - py + px
        return points

    # =====================================================
    # SELECTION & TRANSFORM
    # =====================================================
    def normalize_selection(self, x1, y1, x2, y2):
        left, top, right, bottom = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        if right - left < 2 or bottom - top < 2:
            return None
        return (left, top, right, bottom)

    def draw_selection_box(self):
        if not self.selection:
            return
        x1, y1, x2, y2 = self.selection
        cx1, cy1 = self.image_to_canvas_coords(x1, y1)
        cx2, cy2 = self.image_to_canvas_coords(x2, y2)
        self.selection_item = self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline="#00aaff", dash=(6, 4), width=2, tags="selection")

    def capture_selection(self):
        if not self.selection:
            messagebox.showinfo("Info", "Pilih area terlebih dahulu memakai tool Seleksi.")
            return
        x1, y1, x2, y2 = self.selection
        self.selected_object = self.active_image().crop((x1, y1, x2, y2))
        ImageDraw.Draw(self.active_image()).rectangle((x1, y1, x2, y2), fill=(255, 255, 255, 0))
        self.save_history()
        self.full_render()
        self.update_status("Area seleksi sudah diambil sebagai objek transformasi.")

    def paste_selected_object(self, x, y, obj=None):
        if obj is None:
            obj = self.selected_object
        if obj is None:
            return
        self.active_image().alpha_composite(obj, (x, y))
        self.selection = (x, y, x + obj.width, y + obj.height)

    def translate_selection(self):
        if not self.selection:
            messagebox.showinfo("Info", "Buat area seleksi terlebih dahulu.")
            return
        dx = simpledialog.askinteger("Translasi", "Geser X:", initialvalue=50)
        if dx is None:
            return
        dy = simpledialog.askinteger("Translasi", "Geser Y:", initialvalue=30)
        if dy is None:
            return
        x1, y1, x2, y2 = self.selection
        obj = self.active_image().crop((x1, y1, x2, y2))
        ImageDraw.Draw(self.active_image()).rectangle((x1, y1, x2, y2), fill=(255, 255, 255, 0))
        nx = max(0, min(self.canvas_width - obj.width, x1 + dx))
        ny = max(0, min(self.canvas_height - obj.height, y1 + dy))
        self.paste_selected_object(nx, ny, obj)
        self.save_history()
        self.full_render()

    def rotate_selection(self):
        if not self.selection:
            messagebox.showinfo("Info", "Buat area seleksi terlebih dahulu.")
            return
        angle = simpledialog.askinteger("Rotasi", "Sudut rotasi derajat:", initialvalue=90)
        if angle is None:
            return
        x1, y1, x2, y2 = self.selection
        obj = self.active_image().crop((x1, y1, x2, y2))
        ImageDraw.Draw(self.active_image()).rectangle((x1, y1, x2, y2), fill=(255, 255, 255, 0))
        obj = obj.rotate(angle, expand=True)
        self.paste_selected_object(x1, y1, obj)
        self.save_history()
        self.full_render()

    def scale_selection(self):
        if not self.selection:
            messagebox.showinfo("Info", "Buat area seleksi terlebih dahulu.")
            return
        factor = simpledialog.askfloat("Skala", "Faktor skala, contoh 1.5 atau 0.5:", initialvalue=1.5)
        if factor is None or factor <= 0:
            return
        x1, y1, x2, y2 = self.selection
        obj = self.active_image().crop((x1, y1, x2, y2))
        ImageDraw.Draw(self.active_image()).rectangle((x1, y1, x2, y2), fill=(255, 255, 255, 0))
        new_size = (max(1, int(obj.width * factor)), max(1, int(obj.height * factor)))
        obj = obj.resize(new_size, Image.Resampling.LANCZOS)
        self.paste_selected_object(x1, y1, obj)
        self.save_history()
        self.full_render()

    def flip_selection(self, mode):
        if not self.selection:
            messagebox.showinfo("Info", "Buat area seleksi terlebih dahulu.")
            return
        x1, y1, x2, y2 = self.selection
        obj = self.active_image().crop((x1, y1, x2, y2))
        ImageDraw.Draw(self.active_image()).rectangle((x1, y1, x2, y2), fill=(255, 255, 255, 0))
        obj = obj.transpose(Image.Transpose.FLIP_LEFT_RIGHT if mode == "h" else Image.Transpose.FLIP_TOP_BOTTOM)
        self.paste_selected_object(x1, y1, obj)
        self.save_history()
        self.full_render()

    def clear_selection(self):
        self.selection = None
        self.selected_object = None
        self.clear_preview()
        self.canvas.delete("selection")
        self.full_render()
        self.update_status("Seleksi dibersihkan.")

    # =====================================================
    # ANIMATION
    # =====================================================
    def start_bounce_animation(self):
        self.stop_animation()
        if self.selection:
            x1, y1, x2, y2 = self.selection
            obj = self.composite_image().crop((x1, y1, x2, y2))
            self.prepare_animation_background((x1, y1, x2, y2))
        else:
            obj = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
            draw = ImageDraw.Draw(obj)
            draw.ellipse((4, 4, 76, 76), fill=self.hex_to_rgba(self.primary_color), outline=(0, 0, 0, 255), width=3)
            x1, y1 = 80, 80
            self.prepare_animation_background(None)
        self.selection = None
        self.canvas.delete("selection")
        self.anim_obj = {"image": obj, "x": x1, "y": y1, "mode": "bounce"}
        self.animation_running = True
        self.render_animation_background()
        self.animate()

    def start_rotate_animation(self):
        self.stop_animation()
        if self.selection:
            x1, y1, x2, y2 = self.selection
            obj = self.composite_image().crop((x1, y1, x2, y2))
            self.prepare_animation_background((x1, y1, x2, y2))
        else:
            obj = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
            draw = ImageDraw.Draw(obj)
            draw.rectangle((18, 18, 82, 82), fill=self.hex_to_rgba(self.primary_color), outline=(0, 0, 0, 255), width=3)
            x1, y1 = 120, 120
            self.prepare_animation_background(None)
        self.selection = None
        self.canvas.delete("selection")
        self.anim_obj = {"image": obj, "x": x1, "y": y1, "mode": "rotate", "base_x": x1, "base_y": y1}
        self.anim_angle = 0
        self.anim_after_id = None
        self.animation_running = True
        self.render_animation_background()
        self.animate()

    def prepare_animation_background(self, source_bounds=None):
        """Siapkan background animasi tanpa menggandakan objek sumber.

        Jika animasi memakai area seleksi, area asli pada tampilan background ditutup
        warna putih terlebih dahulu. Data layer asli tidak diubah, sehingga ketika
        animasi dihentikan gambar asli tetap kembali seperti semula.
        """
        base = self.composite_image().convert("RGBA")
        self.animation_selection_bounds = source_bounds
        if source_bounds:
            x1, y1, x2, y2 = source_bounds
            ImageDraw.Draw(base).rectangle((x1, y1, x2, y2), fill=(255, 255, 255, 255))
        self.animation_base_image = base

    def render_animation_background(self):
        """Render satu kali background animasi; frame berikutnya hanya menggerakkan objek."""
        self.canvas.delete("all")
        image = self.animation_base_image if self.animation_base_image is not None else self.composite_image()
        display_size = (max(1, int(self.canvas_width * self.zoom)), max(1, int(self.canvas_height * self.zoom)))
        display_image = image
        if self.zoom != 1.0:
            display_image = image.resize(display_size, Image.Resampling.BILINEAR)
        self.tk_image = ImageTk.PhotoImage(display_image)
        self.image_item = self.canvas.create_image(self.canvas_offset_x, self.canvas_offset_y, image=self.tk_image, anchor=tk.NW, tags="base")
        self.canvas.create_rectangle(self.canvas_offset_x, self.canvas_offset_y, self.canvas_offset_x + display_size[0], self.canvas_offset_y + display_size[1], outline="#dddddd", tags="border")
        if self.show_grid.get():
            self.draw_grid_items()
        self.canvas.config(scrollregion=(0, 0, display_size[0] + 100, display_size[1] + 100))
        self.zoom_label.config(text=f"{int(self.zoom * 100)}%")
        self.update_object_info()

    def animate(self):
        if not self.animation_running or self.anim_obj is None:
            return

        # Penting: jangan render ulang gambar asli setiap frame, dan jangan biarkan
        # objek sumber tetap tampil di background. Background sudah disiapkan tanpa
        # area seleksi, sehingga yang terlihat hanya satu objek yang bergerak.
        self.canvas.delete("animation")
        obj = self.anim_obj["image"]
        x = self.anim_obj["x"]
        y = self.anim_obj["y"]
        if self.anim_obj["mode"] == "bounce":
            x += self.anim_vx
            y += self.anim_vy
            if x <= 0 or x + obj.width >= self.canvas_width:
                self.anim_vx *= -1
            if y <= 0 or y + obj.height >= self.canvas_height:
                self.anim_vy *= -1
            self.anim_obj["x"] = max(0, min(self.canvas_width - obj.width, x))
            self.anim_obj["y"] = max(0, min(self.canvas_height - obj.height, y))
            render_obj = obj
            draw_x = int(self.anim_obj["x"])
            draw_y = int(self.anim_obj["y"])
        else:
            self.anim_angle = (self.anim_angle + 8) % 360
            render_obj = obj.rotate(self.anim_angle, expand=True)
            # Rotasi dijaga di sekitar pusat objek asli agar tidak terlihat meloncat.
            cx = self.anim_obj.get("base_x", x) + obj.width / 2
            cy = self.anim_obj.get("base_y", y) + obj.height / 2
            draw_x = int(cx - render_obj.width / 2)
            draw_y = int(cy - render_obj.height / 2)

        clipped, clipped_x, clipped_y = self.clip_image_to_canvas(render_obj, draw_x, draw_y)
        if clipped is not None:
            display = clipped.resize((max(1, int(clipped.width * self.zoom)), max(1, int(clipped.height * self.zoom))), Image.Resampling.BILINEAR)
            self.anim_tk = ImageTk.PhotoImage(display)
            cx, cy = self.image_to_canvas_coords(clipped_x, clipped_y)
            self.canvas.create_image(cx, cy, image=self.anim_tk, anchor=tk.NW, tags="animation")

        delay = max(16, int(1000 / max(1, self.animation_speed.get())))
        self.anim_after_id = self.root.after(delay, self.animate)

    def clip_image_to_canvas(self, image, x, y):
        """Potong gambar agar item animasi/preview tidak bocor ke luar kanvas."""
        left = max(0, x)
        top = max(0, y)
        right = min(self.canvas_width, x + image.width)
        bottom = min(self.canvas_height, y + image.height)
        if right <= left or bottom <= top:
            return None, x, y
        crop_box = (left - x, top - y, right - x, bottom - y)
        return image.crop(crop_box), left, top

    def stop_animation(self):
        self.animation_running = False
        self.anim_obj = None
        self.animation_base_image = None
        self.animation_selection_bounds = None
        if self.anim_after_id is not None:
            try:
                self.root.after_cancel(self.anim_after_id)
            except Exception:
                pass
            self.anim_after_id = None
        if hasattr(self, "canvas"):
            self.canvas.delete("animation")
            # Tampilkan lagi layer asli setelah animasi berhenti.
            self.full_render()

    # =====================================================
    # ACTIONS
    # =====================================================
    def set_tool(self, tool):
        self.stop_animation()
        self.tool = tool

        # Saat kembali ke tool menggambar, kotak seleksi lama otomatis dihapus.
        # Ini mencegah tampilan seperti garis biru/kotak seleksi besar menutupi gambar.
        if tool not in ["select", "crop"]:
            self.selection = None
            self.selected_object = None
            if hasattr(self, "canvas"):
                self.canvas.delete("selection")
                self.canvas.delete("preview")
                self.full_render()

        self.update_status(f"Tool aktif: {tool}")
        self.update_active_tool_label()
        self.update_object_info()

    def set_shape(self, shape):
        self.stop_animation()
        self.shape = shape
        self.tool = "shape"
        self.selection = None
        self.selected_object = None
        if hasattr(self, "canvas"):
            self.canvas.delete("selection")
            self.canvas.delete("preview")
            self.full_render()
        self.update_status(f"Shape aktif: {shape}")
        self.update_active_tool_label()
        self.update_object_info()

    def change_algorithm(self, event=None):
        self.algorithm = self.algorithm_combo.get()
        self.tool = "shape"
        self.update_active_tool_label()
        self.update_status(f"Algoritma aktif: {self.algorithm}")

    def choose_primary_color(self):
        color = colorchooser.askcolor(color=self.primary_color)[1]
        if color:
            self.set_primary_color(color)

    def choose_secondary_color(self):
        color = colorchooser.askcolor(color=self.secondary_color)[1]
        if color:
            self.secondary_color = color
            self.secondary_btn.config(bg=color)

    def set_primary_color(self, color):
        self.primary_color = color
        self.primary_btn.config(bg=color)

    def hex_to_rgba(self, color, alpha=None):
        color = color.lstrip("#")
        r, g, b = tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
        a = int(255 * (self.opacity.get() / 100)) if alpha is None else alpha
        return r, g, b, a

    def color_distance(self, a, b):
        return sum(abs(int(a[i]) - int(b[i])) for i in range(4))

    def flood_fill(self, x, y, color, tolerance=8):
        """Bucket fill berbasis flood fill 4-arah.

        Algoritma mengambil warna target pada titik klik, lalu menyebar ke
        piksel tetangga yang warnanya masih mirip. Ini lebih sesuai dengan
        materi Fill Area Primitif dibanding mengisi seluruh layer.
        """
        img = self.active_image()
        if not (0 <= x < self.canvas_width and 0 <= y < self.canvas_height):
            return 0
        target = img.getpixel((x, y))
        replacement = self.hex_to_rgba(color)
        if self.color_distance(target, replacement) <= tolerance:
            return 0

        pixels = img.load()
        q = deque([(x, y)])
        visited = set()
        filled = 0
        while q:
            px, py = q.popleft()
            if (px, py) in visited:
                continue
            visited.add((px, py))
            if not (0 <= px < self.canvas_width and 0 <= py < self.canvas_height):
                continue
            if self.color_distance(pixels[px, py], target) > tolerance:
                continue
            pixels[px, py] = replacement
            filled += 1
            q.extend(((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)))
        return filled

    def fill_layer(self, color):
        draw = ImageDraw.Draw(self.active_image())
        draw.rectangle([0, 0, self.canvas_width, self.canvas_height], fill=self.hex_to_rgba(color))

    def clear_canvas(self):
        if not messagebox.askyesno("Konfirmasi", "Bersihkan seluruh kanvas?"):
            return
        self.stop_animation()
        self.layers = []
        self.selection = None
        self.selected_object = None
        self.create_image_layer("Layer 1")
        self.refresh_layer_list()
        self.save_history()
        self.full_render()

    def apply_canvas_size(self):
        try:
            new_w = max(1, int(self.width_entry.get()))
            new_h = max(1, int(self.height_entry.get()))
        except ValueError:
            messagebox.showerror("Error", "Lebar dan tinggi harus berupa angka.")
            return
        for i, layer in enumerate(self.layers):
            old = layer["image"]
            new_image = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 0))
            if i == 0:
                ImageDraw.Draw(new_image).rectangle([0, 0, new_w, new_h], fill=(255, 255, 255, 255))
            new_image.alpha_composite(old.crop((0, 0, min(old.width, new_w), min(old.height, new_h))))
            layer["image"] = new_image
        self.canvas_width = new_w
        self.canvas_height = new_h
        self.selection = None
        self.save_history()
        self.full_render()

    def crop_to_selection(self, x1, y1, x2, y2):
        left, top, right, bottom = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        if right - left < 2 or bottom - top < 2:
            return
        self.canvas_width = right - left
        self.canvas_height = bottom - top
        for layer in self.layers:
            layer["image"] = layer["image"].crop((left, top, right, bottom))
        self.sync_size_entries()

    def rotate_canvas(self, direction):
        angle = 90 if direction == "left" else -90
        for layer in self.layers:
            layer["image"] = layer["image"].rotate(angle, expand=True)
        self.canvas_width, self.canvas_height = self.canvas_height, self.canvas_width
        self.selection = None
        self.sync_size_entries()
        self.save_history()
        self.full_render()

    def open_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.webp")])
        if not path:
            return
        img = Image.open(path).convert("RGBA")
        img.thumbnail((self.canvas_width, self.canvas_height), Image.Resampling.LANCZOS)
        x = (self.canvas_width - img.width) // 2
        y = (self.canvas_height - img.height) // 2
        self.active_image().alpha_composite(img, (x, y))
        self.save_history()
        self.full_render()

    def save_image(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg"), ("BMP Image", "*.bmp")])
        if not path:
            return
        self.composite_image().convert("RGB").save(path)
        messagebox.showinfo("Berhasil", f"Gambar disimpan:\n{path}")

    def export_animation_gif(self):
        path = filedialog.asksaveasfilename(defaultextension=".gif", filetypes=[("GIF Animation", "*.gif")])
        if not path:
            return

        mode = simpledialog.askstring("Export GIF", "Mode animasi: bounce atau rotate", initialvalue="bounce")
        if not mode:
            return
        mode = mode.strip().lower()
        if mode not in {"bounce", "rotate"}:
            messagebox.showerror("Error", "Mode harus 'bounce' atau 'rotate'.")
            return

        if self.selection:
            x1, y1, x2, y2 = self.selection
            obj = self.composite_image().crop((x1, y1, x2, y2))
            start_x, start_y = x1, y1
        else:
            obj = Image.new("RGBA", (90, 90), (0, 0, 0, 0))
            draw = ImageDraw.Draw(obj)
            if mode == "bounce":
                draw.ellipse((5, 5, 85, 85), fill=self.hex_to_rgba(self.primary_color), outline=(0, 0, 0, 255), width=3)
            else:
                draw.rectangle((15, 15, 75, 75), fill=self.hex_to_rgba(self.primary_color), outline=(0, 0, 0, 255), width=3)
            start_x, start_y = 70, 70

        background = self.composite_image().convert("RGBA")
        # Jika memakai seleksi, hapus area sumber dari background GIF agar tidak ada dua gambar.
        if self.selection:
            x1, y1, x2, y2 = self.selection
            ImageDraw.Draw(background).rectangle((x1, y1, x2, y2), fill=(255, 255, 255, 255))
        frames = []
        x, y = start_x, start_y
        vx, vy = self.anim_vx, self.anim_vy
        frame_count = 90
        for i in range(frame_count):
            frame = background.copy()
            render_obj = obj
            px, py = x, y
            if mode == "bounce":
                x += vx
                y += vy
                if x <= 0 or x + obj.width >= self.canvas_width:
                    vx *= -1
                if y <= 0 or y + obj.height >= self.canvas_height:
                    vy *= -1
                x = max(0, min(self.canvas_width - obj.width, x))
                y = max(0, min(self.canvas_height - obj.height, y))
                px, py = x, y
            else:
                render_obj = obj.rotate((i * 8) % 360, expand=True)
                px = max(0, min(self.canvas_width - render_obj.width, start_x))
                py = max(0, min(self.canvas_height - render_obj.height, start_y))
            frame.alpha_composite(render_obj, (int(px), int(py)))
            frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE))

        duration = max(16, int(1000 / max(1, self.animation_speed.get())))
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=duration, loop=0)
        messagebox.showinfo("Berhasil", f"Animasi GIF disimpan:\n{path}")

    def save_project(self):
        path = filedialog.asksaveasfilename(defaultextension=".gkp", filetypes=[("Grafkom Paint Project", "*.gkp")])
        if not path:
            return
        data = {
            "version": 1,
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "zoom": self.zoom,
            "layers": self.layers,
            "active_layer_index": self.active_layer_index,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)
        messagebox.showinfo("Berhasil", f"Project disimpan:\n{path}")

    def open_project(self):
        path = filedialog.askopenfilename(filetypes=[("Grafkom Paint Project", "*.gkp")])
        if not path:
            return
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self.stop_animation()
            self.canvas_width = int(data["canvas_width"])
            self.canvas_height = int(data["canvas_height"])
            self.zoom = float(data.get("zoom", 1.0))
            self.layers = data["layers"]
            self.active_layer_index = int(data.get("active_layer_index", 0))
            self.primary_color = data.get("primary_color", self.primary_color)
            self.secondary_color = data.get("secondary_color", self.secondary_color)
            self.primary_btn.config(bg=self.primary_color)
            self.secondary_btn.config(bg=self.secondary_color)
            self.selection = None
            self.selected_object = None
            self.sync_size_entries()
            self.refresh_layer_list()
            self.history.clear()
            self.redo_stack.clear()
            self.save_history(clear_redo=False)
            self.full_render()
            self.update_status("Project berhasil dibuka.")
        except Exception as exc:
            messagebox.showerror("Error", f"Gagal membuka project:\n{exc}")

    def undo(self):
        if len(self.history) <= 1:
            return
        current = self.history.pop()
        self.redo_stack.append(current)
        self.selection = None
        self.restore_snapshot(self.history[-1])

    def redo(self):
        if not self.redo_stack:
            return
        snapshot = self.redo_stack.pop()
        self.history.append(snapshot)
        self.selection = None
        self.restore_snapshot(snapshot)

    def add_layer(self):
        name = simpledialog.askstring("Layer Baru", "Nama layer:", initialvalue=f"Layer {len(self.layers) + 1}")
        if not name:
            return
        self.create_image_layer(name)
        self.refresh_layer_list()
        self.save_history()
        self.full_render()

    def refresh_layer_list(self):
        if hasattr(self, "layer_combo"):
            self.layer_combo["values"] = [layer["name"] for layer in self.layers]
            self.layer_combo.current(self.active_layer_index)

    def change_layer(self, event=None):
        self.active_layer_index = self.layer_combo.current()
        self.update_status(f"Layer aktif: {self.layers[self.active_layer_index]['name']}")

    def toggle_layer(self):
        layer = self.layers[self.active_layer_index]
        layer["visible"] = not layer["visible"]
        self.save_history()
        self.full_render()

    def change_zoom(self, delta):
        self.zoom = min(3.0, max(0.25, self.zoom + delta))
        self.full_render()

    def draw_manual_point(self):
        x = simpledialog.askinteger("Titik", "Koordinat X:", initialvalue=100)
        if x is None:
            return
        y = simpledialog.askinteger("Titik", "Koordinat Y:", initialvalue=100)
        if y is None:
            return
        self.draw_pixels([(x, y)])
        self.save_history()
        self.full_render()

    def draw_from_numbers(self):
        try:
            x1 = int(self.x1_entry.get())
            y1 = int(self.y1_entry.get())
            x2 = int(self.x2_entry.get())
            y2 = int(self.y2_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Koordinat harus angka.")
            return
        self.draw_shape_to_image(x1, y1, x2, y2)
        self.save_history()
        self.full_render()

    # =====================================================
    # MENU POPUPS
    # =====================================================
    def popup_menu(self, items):
        menu = tk.Menu(self.root, tearoff=0, bg="#2b2b2b", fg="white")
        for label, command in items:
            if label == "-":
                menu.add_separator()
            else:
                menu.add_command(label=label, command=command)
        try:
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()

    def show_file_menu(self):
        self.popup_menu([
            ("Open Image", self.open_image),
            ("Save Image", self.save_image),
            ("Save Project", self.save_project),
            ("Open Project", self.open_project),
            ("-", None),
            ("Clear Canvas", self.clear_canvas),
        ])

    def show_edit_menu(self):
        self.popup_menu([("Undo", self.undo), ("Redo", self.redo), ("Clear Selection", self.clear_selection)])

    def show_draw_menu(self):
        self.popup_menu([("Brush", lambda: self.set_tool("brush")), ("Text", lambda: self.set_tool("text")), ("Shape", lambda: self.set_tool("shape")), ("Draw From Numbers", self.draw_from_numbers)])

    def show_transform_menu(self):
        self.popup_menu([("Translate", self.translate_selection), ("Rotate", self.rotate_selection), ("Scale", self.scale_selection), ("Flip Horizontal", lambda: self.flip_selection("h")), ("Flip Vertical", lambda: self.flip_selection("v")), ("Matrix Info", self.show_matrix_info)])

    def show_animation_menu(self):
        self.popup_menu([
            ("Bounce Animation", self.start_bounce_animation),
            ("Rotate Animation", self.start_rotate_animation),
            ("Export GIF", self.export_animation_gif),
            ("Stop Animation", self.stop_animation),
        ])

    def show_view_menu(self):
        self.popup_menu([("Zoom In", lambda: self.change_zoom(0.1)), ("Zoom Out", lambda: self.change_zoom(-0.1)), ("Toggle Grid", self.toggle_grid)])

    def show_help(self):
        messagebox.showinfo(
            "Help",
            "Python Paint - Grafika Komputer\n\n"
            "1. Pilih tool Brush untuk menggambar manual.\n"
            "2. Pilih Shapes lalu drag pada kanvas.\n"
            "3. Pilih algoritma DDA, Bresenham, Midpoint Circle, atau Midpoint Ellipse.\n"
            "4. Untuk transformasi, pilih area memakai Selection, lalu gunakan Transform.\n"
            "5. Animation dapat menjalankan objek bouncing atau rotasi."
        )

    def toggle_grid(self):
        self.show_grid.set(not self.show_grid.get())
        self.full_render()

    def show_matrix_info(self):
        messagebox.showinfo(
            "Matriks Transformasi 2D",
            "Translasi:\n[1 0 Tx]\n[0 1 Ty]\n[0 0 1]\n\n"
            "Skala:\n[Sx 0 0]\n[0 Sy 0]\n[0 0 1]\n\n"
            "Rotasi:\n[cosθ -sinθ 0]\n[sinθ  cosθ 0]\n[0     0    1]\n\n"
            "Flip Horizontal:\n[-1 0 0]\n[ 0 1 0]\n[ 0 0 1]\n\n"
            "Koordinat homogen: P' = M × P"
        )

    # =====================================================
    # UTILS
    # =====================================================

    def update_active_tool_label(self):
        text = f"Tool: {self.tool}"
        if self.tool == "shape":
            text += f" | {self.shape}"
        if self.algorithm != "normal":
            text += f" | {self.algorithm}"
        if hasattr(self, "active_tool_label"):
            self.active_tool_label.config(text=text)
        if hasattr(self, "tool_status_label"):
            self.tool_status_label.config(text=text)

    def sync_size_entries(self):
        self.width_entry.delete(0, tk.END)
        self.width_entry.insert(0, str(self.canvas_width))
        self.height_entry.delete(0, tk.END)
        self.height_entry.insert(0, str(self.canvas_height))

    def star_points(self, cx, cy, rx, ry):
        points = []
        for i in range(10):
            angle = -math.pi / 2 + i * math.pi / 5
            radius_x = rx if i % 2 == 0 else rx * 0.45
            radius_y = ry if i % 2 == 0 else ry * 0.45
            points.append((cx + math.cos(angle) * radius_x, cy + math.sin(angle) * radius_y))
        return points

    def update_object_info(self):
        if not hasattr(self, "object_info"):
            return
        if self.selection:
            x1, y1, x2, y2 = self.selection
            text = f"Seleksi:\nX: {x1}\nY: {y1}\nW: {x2 - x1}\nH: {y2 - y1}\nTool: {self.tool}\nAlgoritma: {self.algorithm}"
        else:
            text = f"Tool: {self.tool}\nShape: {self.shape}\nAlgoritma: {self.algorithm}\nLayer: {self.layers[self.active_layer_index]['name']}"
        self.object_info.config(text=text)

    def update_status(self, text):
        if hasattr(self, "status_label"):
            self.status_label.config(text=text)

    def update_status_throttled(self, text):
        self.pending_status = text
        if self.status_pending:
            return
        self.status_pending = True
        self.root.after(80, self._flush_status)

    def _flush_status(self):
        self.status_pending = False
        self.update_status(self.pending_status)

    def create_tooltip(self, widget, text):
        def enter(_):
            self.update_status(text)
        def leave(_):
            self.update_status("Ready")
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)


if __name__ == "__main__":
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("Pillow belum terpasang. Jalankan: pip install pillow")
        raise

    root = tk.Tk()
    app = PaintApp(root)
    root.mainloop()
