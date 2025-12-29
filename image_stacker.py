import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageGrab
from io import BytesIO

import win32clipboard
import win32con

# =========================
# =========================
# 可调参数
# =========================
MAX_SIZE = 1500  # 截图后最长边
DEFAULT_SAVE_NAME = "tmp"

# =========================
# Windows 剪贴板工具
# =========================
def copy_image_to_clipboard(img: Image.Image):
    output = BytesIO()
    img.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]
    output.close()

    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32con.CF_DIB, data)
    win32clipboard.CloseClipboard()


def get_image_from_clipboard():
    img = ImageGrab.grabclipboard()
    if isinstance(img, Image.Image):
        return img
    if isinstance(img, list) and img:
        return Image.open(img[0])
    return None

# =========================
# 主程序
# =========================
class ImageStackerApp:
    def __init__(self, root):
        self.root = root
        root.title("Image Stacker (Windows)")

        self.base_img = None
        self.base_img_path = None
        self.crop_box = None
        self.tk_img = None

        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.drag_start = None
        self.space_pressed = False

        self.save_dir = None

        # UI
        container = tk.Frame(root)
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container, bg="#333")
        self.hbar = tk.Scrollbar(container, orient="horizontal", command=self.canvas.xview)
        self.vbar = tk.Scrollbar(container, orient="vertical", command=self.canvas.yview)

        self.canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")

        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        bar = tk.Frame(root)
        bar.pack(fill="x")

        tk.Button(bar, text="载入 PNG", command=self.load_base).pack(side="left")
        tk.Button(bar, text="重新加载 (F5)", command=self.reload_base).pack(side="left")
        tk.Button(bar, text="叠图", command=self.overlay).pack(side="left")

        self.use_clipboard = tk.BooleanVar(value=True)
        tk.Checkbutton(bar, text="从剪贴板读取", variable=self.use_clipboard).pack(side="left")

        self.copy_result = tk.BooleanVar(value=True)
        tk.Checkbutton(bar, text="复制结果到剪贴板", variable=self.copy_result).pack(side="left")

        self.save_crop = tk.BooleanVar(value=True)
        tk.Checkbutton(bar, text="保存截图结果", variable=self.save_crop).pack(side="left")

        self.use_timestamp = tk.BooleanVar(value=True)
        tk.Checkbutton(bar, text="时间戳命名", variable=self.use_timestamp).pack(side="left")

        tk.Button(bar, text="选择保存路径", command=self.choose_save_dir).pack(side="left")

        # 绑定事件
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        self.canvas.bind("<MouseWheel>", self.on_zoom)

        root.bind("<KeyPress-space>", self.on_space_down)
        root.bind("<KeyRelease-space>", self.on_space_up)
        root.bind("<F5>", self.on_reload_key)
        root.bind("<Control-v>", self.on_overlay_key)
        root.bind("<Control-V>", self.on_overlay_key)

        self.rect = None
        self.start_pos = None

    def choose_save_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.save_dir = path

    def load_base(self):
        path = filedialog.askopenfilename(filetypes=[("PNG", "*.png")])
        if not path:
            return
        self.base_img_path = path
        self.base_img = Image.open(path).convert("RGB")
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.show_image()

    def reload_base(self):
        if not self.base_img_path:
            messagebox.showerror("错误", "尚未加载图片")
            return
        self.base_img = Image.open(self.base_img_path).convert("RGB")
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.show_image()

    def on_reload_key(self, event=None):
        self.reload_base()

    def on_overlay_key(self, event=None):
        self.overlay()

    def show_image(self):
        if not self.base_img:
            return

        w, h = self.base_img.size
        zw, zh = int(w * self.zoom), int(h * self.zoom)
        disp = self.base_img.resize((zw, zh), Image.LANCZOS)

        self.tk_img = ImageTk.PhotoImage(disp)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        self.canvas.config(scrollregion=(0, 0, zw, zh))

    # ---------- 视图操作 ----------
    def on_zoom(self, e):
        if not self.base_img:
            return
        factor = 1.1 if e.delta > 0 else 0.9
        self.zoom *= factor
        self.zoom = max(0.1, min(self.zoom, 10))
        self.show_image()

    def on_space_down(self, e):
        self.space_pressed = True

    def on_space_up(self, e):
        self.space_pressed = False
        self.drag_start = None

    # ---------- 截取 ----------
    def on_press(self, e):
        if not self.base_img:
            return
        if self.space_pressed:
            self.drag_start = (e.x, e.y)
            return
        self.start_pos = (e.x, e.y)
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="red")

    def on_drag(self, e):
        if self.space_pressed and self.drag_start:
            dx = self.drag_start[0] - e.x
            dy = self.drag_start[1] - e.y
            self.canvas.xview_scroll(int(dx), "units")
            self.canvas.yview_scroll(int(dy), "units")
            self.drag_start = (e.x, e.y)
            return

        if not self.start_pos:
            return
        x0, y0 = self.start_pos
        self.canvas.coords(self.rect, x0, y0, e.x, e.y)

    def on_release(self, e):
        if self.space_pressed:
            return
        if not self.start_pos:
            return
        x0, y0 = self.start_pos
        x1, y1 = e.x, e.y
        self.start_pos = None

        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))

        # 反算到原图坐标
        inv = 1 / self.zoom
        self.crop_box = (
            int(x0 * inv),
            int(y0 * inv),
            int(x1 * inv),
            int(y1 * inv)
        )

        self.export_crop()

    def export_crop(self):
        x0, y0, x1, y1 = self.crop_box
        crop = self.base_img.crop((x0, y0, x1, y1))

        w, h = crop.size
        scale = MAX_SIZE / max(w, h)
        new_size = (int(w * scale), int(h * scale))
        crop_resized = crop.resize(new_size, Image.LANCZOS)

        copy_image_to_clipboard(crop_resized)

        if self.save_crop.get():
            import time, os
            if not self.save_dir:
                messagebox.showerror("错误", "请先选择保存路径")
                return
            if self.use_timestamp.get():
                name = str(int(time.time()))
            else:
                name = DEFAULT_SAVE_NAME
            path = os.path.join(self.save_dir, f"{name}.png")
            crop_resized.save(path)

        messagebox.showinfo("完成", "截图已复制到剪贴板")

    # ---------- 叠图 ----------
    def overlay(self):
        if not self.crop_box or not self.base_img:
            messagebox.showerror("错误", "尚未截取区域")
            return

        if self.use_clipboard.get():
            patch = get_image_from_clipboard()
            if patch is None:
                messagebox.showerror("错误", "剪贴板中没有图片")
                return
        else:
            path = filedialog.askopenfilename(filetypes=[("PNG", "*.png")])
            if not path:
                return
            patch = Image.open(path)

        patch = patch.convert("RGB")

        x0, y0, x1, y1 = self.crop_box
        ow, oh = x1 - x0, y1 - y0
        patch = patch.resize((ow, oh), Image.LANCZOS)

        out = Image.new("RGB", self.base_img.size, (255, 255, 255))
        out.paste(patch, (x0, y0))
        out.save("tmp.png")

        # 生成 mask：被叠区域黑，其余白
        mask = Image.new("L", self.base_img.size, 255)
        mask_draw = Image.new("L", (ow, oh), 0)
        mask.paste(mask_draw, (x0, y0))
        mask.save("mask.png")

        if self.copy_result.get():
            copy_image_to_clipboard(out)

        messagebox.showinfo("完成", "已生成 tmp.png")

# =========================
# 启动
# =========================
if __name__ == "__main__":
    root = tk.Tk()
    app = ImageStackerApp(root)
    root.mainloop()
