import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageDraw, ImageTk, ImageSequence
import threading
import os
import time

import config

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# Генерація спінера якщо файл відсутній
def _ensure_spinner_gif():
    if os.path.exists(config.SPINNER_GIF):
        return
    os.makedirs(config.ASSETS_DIR, exist_ok=True)
    SIZE, FRAMES    = 24, 12
    ARC_COLOR       = (114, 137, 218)
    TRAIL_COLOR     = (60, 60, 90)
    frames = []
    for i in range(FRAMES):
        img  = Image.new("RGBA", (SIZE, SIZE), (20, 20, 35, 0))
        draw = ImageDraw.Draw(img)
        angle = (i / FRAMES) * 360
        draw.arc([2, 2, SIZE - 3, SIZE - 3], 0, 360,            fill=TRAIL_COLOR, width=3)
        draw.arc([2, 2, SIZE - 3, SIZE - 3], angle, angle + 90, fill=ARC_COLOR,   width=3)
        frames.append(img.convert("RGBA"))
    frames[0].save(
        config.SPINNER_GIF, save_all=True, append_images=frames[1:],
        loop=0, duration=60, disposal=2,
    )


# Клас стану зображення
class ImageState:
    def __init__(self):
        self.original: Image.Image | None = None
        self.overlay:  Image.Image | None = None
        self.path:         str | None = None
        self.zoom:         float = 1.0
        self.show_overlay: bool  = False

    def reset(self):
        self.__init__()

    @property
    def loaded(self) -> bool:
        return self.original is not None


# Клас стану завдання
class TaskState:
    def __init__(self):
        self.running:    bool  = False
        self.start_time: float = 0.0
        self.spinner_idx: int  = 0
        self.tick_id           = None

    def start(self):
        self.running     = True
        self.start_time  = time.time()
        self.spinner_idx = 0

    def stop(self):
        self.running = False

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time if self.start_time else 0.0

    @property
    def elapsed_formatted(self) -> str:
        total = int(self.elapsed)
        if total < 60:
            return f"{total}s"
        h, rem = divmod(total, 3600)
        m, s   = divmod(rem, 60)
        return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

    def next_frame_idx(self, total: int) -> int:
        idx = self.spinner_idx
        self.spinner_idx = (self.spinner_idx + 1) % max(1, total)
        return idx


# Клас пайплайну
class PipelineState:
    def __init__(self):
        self.ready:      bool = False
        self.ocr              = None
        self.translator       = None

    def reset(self):
        self.__init__()

    def initialize(self, url: str):
        from pipeline.ocr        import ComicOCR
        from pipeline.translator import ComicTranslator
        self.ocr        = ComicOCR(colab_url=url)
        self.translator = ComicTranslator(colab_url=url)
        self.ready      = True


class ComicsTranslatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(config.WINDOW_TITLE)
        self.geometry(config.WINDOW_GEOMETRY)
        self.minsize(*config.WINDOW_MINSIZE)

        # Стан програми
        self.image_state    = ImageState()
        self.task_state     = TaskState()
        self.pipeline_state = PipelineState()
        self.bubbles: list[dict] = []
        self._current_tab: str   = "main"

        self._load_icons()
        self._load_spinner_frames()
        self._build_ui()

    # Завантаження ресурсів

    def _load_icons(self):
        if os.path.exists(config.APP_ICON):
            try:
                self.iconbitmap(config.APP_ICON)
            except Exception:
                pass

        def _ctk_icon(path: str, size=(20, 20)) -> ctk.CTkImage | None:
            if os.path.exists(path):
                try:
                    img = Image.open(path)
                    return ctk.CTkImage(light_image=img, dark_image=img, size=size)
                except Exception:
                    pass
            return None

        self.icon_settings = _ctk_icon(config.ICON_SETTINGS, (18, 18))
        self.icon_back     = _ctk_icon(config.ICON_BACK,     (18, 18))
        self.icon_success  = _ctk_icon(config.ICON_SUCCESS,  (12, 12))
        self.icon_error    = _ctk_icon(config.ICON_ERROR,    (16, 16))

    def _load_spinner_frames(self):
        _ensure_spinner_gif()
        self.spinner_frames: list[ctk.CTkImage] = []
        try:
            gif = Image.open(config.SPINNER_GIF)
            for frame in ImageSequence.Iterator(gif):
                img = frame.copy().convert("RGBA").resize((20, 20), Image.Resampling.LANCZOS)
                self.spinner_frames.append(ctk.CTkImage(light_image=img, dark_image=img, size=(20, 20)))
        except Exception:
            pass

    # Побудова інтерфейсу

    def _build_ui(self):
        self._build_taskbar()
        self._build_left_panel()
        self._build_canvas_panel()

    def _build_taskbar(self):
        self.taskbar = ctk.CTkFrame(self, height=35, corner_radius=0, fg_color=("#e9ecef", "#141423"))
        self.taskbar.pack(side="bottom", fill="x")
        self.taskbar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.taskbar, text="Ready",
            font=("Segoe UI", 12), text_color="#a2a2d0"
        )
        self.status_label.pack(side="left", padx=15)

        self.spinner_label = ctk.CTkLabel(self.taskbar, text="", font=("Segoe UI", 13), width=24)
        self.spinner_label.pack(side="right", padx=(5, 15))

        self.timer_label = ctk.CTkLabel(
            self.taskbar, text="",
            font=("Consolas", 12, "bold"), text_color="#a2a2d0"
        )
        self.timer_label.pack(side="right")

    def _build_left_panel(self):
        self.left_panel = ctk.CTkFrame(self, width=240, corner_radius=10)
        self.left_panel.pack(side="left", fill="y", padx=10, pady=10)
        self.left_panel.pack_propagate(False)

        self._build_panel_header()
        self._build_main_tab()
        self._build_settings_tab()

    def _build_panel_header(self):
        header = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 0))

        ctk.CTkLabel(header, text="Control Center", font=("Segoe UI", 16, "bold")).pack(side="left")

        self.settings_btn = ctk.CTkButton(
            header,
            text="" if self.icon_settings else "Settings",
            image=self.icon_settings,
            width=32 if self.icon_settings else 60,
            height=32,
            font=("Segoe UI", 11),
            fg_color="transparent",
            hover_color=("#d0d0d0", "#2a2a3a"),
            text_color=("gray40", "gray70"),
            command=self._toggle_tab,
        )
        self.settings_btn.pack(side="right")

    def _build_main_tab(self):
        self.main_tab = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.main_tab.pack(fill="both", expand=True)

        self.btn_open  = self._make_button(self.main_tab, "Відкрити сторінку",  self.load_image)
        self.btn_ocr   = self._make_button(self.main_tab, "Запустити OCR",       self.run_ocr,
                                            color=("#1d3557", "#132237"), state="disabled")
        self.btn_trans = self._make_button(self.main_tab, "Перекласти репліки",  self.run_translate,
                                            color=("#1d3557", "#132237"), state="disabled")
        self.btn_save  = self._make_button(self.main_tab, "Зберегти результат",  self.save_result,
                                            color=("#6b4226", "#4a2c17"), state="disabled")
        self.btn_reset = self._make_button(self.main_tab, "Скинути все",          self.reset_all,
                                            color="transparent", state="disabled")
        self.btn_reset.configure(border_width=1)

        self.toggle_var = ctk.BooleanVar(value=False)
        self.toggle = ctk.CTkSwitch(
            self.main_tab, text="Показати переклад",
            variable=self.toggle_var,
            command=self.toggle_overlay,
            state="disabled",
            button_color=("#a0a0a0", "#555555"),
        )
        self.toggle.pack(padx=15, pady=15, fill="x")

        ctk.CTkLabel(
            self.main_tab, text="Текстовий лог:",
            font=("Segoe UI", 11, "bold"), text_color="gray"
        ).pack(padx=15, anchor="w")

        self.report_box = ctk.CTkTextbox(
            self.main_tab, font=("Consolas", 11),
            state="disabled", wrap="word"
        )
        self.report_box.pack(padx=15, pady=(2, 15), fill="both", expand=True)

    def _build_settings_tab(self):
        self.settings_tab = ctk.CTkFrame(self.left_panel, fg_color="transparent")

        ctk.CTkLabel(
            self.settings_tab, text="Налаштування",
            font=("Segoe UI", 14, "bold")
        ).pack(padx=15, pady=(20, 4), anchor="w")

        ctk.CTkFrame(self.settings_tab, height=1, fg_color="#333").pack(fill="x", padx=15, pady=(0, 16))

        ctk.CTkLabel(
            self.settings_tab, text="Remote Server URL:",
            font=("Segoe UI", 11), text_color="gray"
        ).pack(padx=15, anchor="w")

        self.url_entry = ctk.CTkEntry(
            self.settings_tab,
            placeholder_text="https://xxxx.ngrok-free.app",
            font=("Segoe UI", 11), height=34
        )
        self.url_entry.pack(padx=15, pady=(4, 6), fill="x")
        self._load_config_url()

        ctk.CTkLabel(
            self.settings_tab,
            text="Вставте посилання на запущений\nColab-сервер з моделлю Dragoman.",
            font=("Segoe UI", 10), text_color="gray", justify="left"
        ).pack(padx=15, anchor="w")

        ctk.CTkFrame(self.settings_tab, height=1, fg_color="#333").pack(fill="x", padx=15, pady=16)

        self.save_url_btn = ctk.CTkButton(
            self.settings_tab, text="Зберегти URL",
            height=36, font=("Segoe UI", 12, "bold"),
            command=self._save_url,
        )
        self.save_url_btn.pack(padx=15, fill="x")

        self.url_status = ctk.CTkLabel(
            self.settings_tab, text="",
            font=("Segoe UI", 10), text_color="#4cc9f0"
        )
        self.url_status.pack(padx=15, pady=(6, 0), anchor="w")

    def _build_canvas_panel(self):
        right_panel = ctk.CTkFrame(self, corner_radius=10)
        right_panel.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)
        right_panel.grid_rowconfigure(0, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(right_panel, bg=config.CANVAS_BG, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        v_scroll = ctk.CTkScrollbar(right_panel, orientation="vertical",   command=self.canvas.yview)
        h_scroll = ctk.CTkScrollbar(right_panel, orientation="horizontal",  command=self.canvas.xview)
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.placeholder = self.canvas.create_text(
            400, 300, fill="gray", justify="center", font=("Segoe UI", 13),
            text="Завантажте графічний файл для початку роботи\n\n"
                 "Ctrl + Колесо миші — Масштабування\n"
                 "ЛКМ (затиснути) — Переміщення картинки"
        )

        self.canvas.bind("<Configure>",    self._on_canvas_resize)
        self.bind("<MouseWheel>",          self._on_mouse_wheel)
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>",    self._on_drag_motion)

        self._build_overlay_panel()

    def _build_overlay_panel(self):
        self._info_expanded = False

        self.overlay_border = tk.Frame(self.canvas, bg="#444455")
        self.overlay_frame  = ctk.CTkFrame(
            self.overlay_border, corner_radius=0,
            fg_color=("#e9ecef", "#1e1e2d")
        )
        self.overlay_frame.pack(fill="both", expand=True, padx=1, pady=1)

        self.overlay_header = ctk.CTkFrame(self.overlay_frame, fg_color="transparent")
        self.overlay_header.pack(fill="x", padx=8, pady=5)

        self.zoom_label = ctk.CTkLabel(
            self.overlay_header, text="100%",
            font=("Consolas", 13, "bold"), text_color=("#333", "#ccc")
        )
        self.zoom_label.pack(side="left", padx=(5, 10))

        self.toggle_info_btn = ctk.CTkButton(
            self.overlay_header, text="▾", width=24, height=24,
            fg_color="transparent", hover_color=("#d0d0d0", "#2a2a3a"),
            text_color=("black", "white"), font=("Segoe UI", 10),
            command=self._toggle_info_panel
        )
        self.toggle_info_btn.pack(side="right")

        self.overlay_content = ctk.CTkFrame(self.overlay_frame, fg_color="transparent")

        ctk.CTkLabel(
            self.overlay_content,
            text="Ctrl + Коліщатко :   Масштаб\nЛКМ (затиснути) :    Переміщення\nКоліщатко :              Прокрутка",
            justify="left", font=("Segoe UI", 11), text_color="gray"
        ).pack(padx=12, pady=(0, 10), anchor="w")

        self.reset_zoom_btn = ctk.CTkButton(
            self.overlay_content, text="Скинути",
            height=26, font=("Segoe UI", 11),
            fg_color=("#3a0ca3", "#3f37c9"),
            hover_color=("#d0d0d0", "#333344"),
            command=self._reset_zoom
        )
        self.reset_zoom_btn.pack(padx=12, pady=(0, 10), fill="x")

    # Допоміжні методи UI

    def _make_button(self, master, text: str, command, color=None, state: str = "normal") -> ctk.CTkButton:
        btn = ctk.CTkButton(
            master, text=text, command=command,
            state=state, height=38, font=("Segoe UI", 12, "bold")
        )
        if color is not None:
            btn.configure(fg_color=color)
        btn.pack(padx=15, pady=5, fill="x")
        return btn

    def _set_report(self, text: str):
        self.report_box.configure(state="normal")
        self.report_box.delete("1.0", "end")
        self.report_box.insert("end", text)
        self.report_box.configure(state="disabled")

    def _toggle_info_panel(self):
        self._info_expanded = not self._info_expanded
        if self._info_expanded:
            self.toggle_info_btn.configure(text="▲")
            self.overlay_content.pack(fill="x")
        else:
            self.toggle_info_btn.configure(text="▼")
            self.overlay_content.pack_forget()

    def _update_zoom_label(self):
        self.zoom_label.configure(text=f"{int(self.image_state.zoom * 100)}%")

    def _reset_zoom(self):
        if not self.image_state.loaded:
            return
        self.image_state.zoom = 1.0
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self._redraw()

    # Перемикання вкладок

    def _toggle_tab(self):
        if self._current_tab == "main":
            self.main_tab.pack_forget()
            self.settings_tab.pack(fill="both", expand=True)
            self._current_tab = "settings"
            if self.icon_back:
                self.settings_btn.configure(image=self.icon_back, text="")
            else:
                self.settings_btn.configure(text="Назад", text_color=("#e63946", "#e63946"))
        else:
            self.settings_tab.pack_forget()
            self.main_tab.pack(fill="both", expand=True)
            self._current_tab = "main"
            if self.icon_settings:
                self.settings_btn.configure(image=self.icon_settings, text="")
            else:
                self.settings_btn.configure(text="Settings", text_color=("gray40", "gray70"))

    def _save_url(self):
        url = self.url_entry.get().strip()
        if url:
            self.pipeline_state.reset()
            self.url_status.configure(text="URL збережено", text_color="#4cc9f0")
        else:
            self.url_status.configure(text="Введіть URL", text_color="#e63946")

    def _load_config_url(self):
        if config.COLAB_API_URL:
            self.url_entry.insert(0, config.COLAB_API_URL)

    # Керування фоновими завданнями

    def _reset_taskbar(self, status: str = "Ready"):
        self.task_state.stop()
        if self.task_state.tick_id is not None:
            self.after_cancel(self.task_state.tick_id)
            self.task_state.tick_id = None
        self.status_label.configure(text=status,  text_color="#a2a2d0")
        self.timer_label.configure(text="",        text_color="#a2a2d0")
        self.spinner_label.configure(image=None, text="")

    def _start_task(self, message: str):
        self._reset_taskbar(message)
        self.task_state.start()
        self._tick_taskbar()

    def _finish_task(self, success_msg: str = "", error_msg: str = "", show_timer: bool = True):
        self.task_state.stop()
        timer_text = self.task_state.elapsed_formatted if show_timer else ""

        if error_msg:
            self.status_label.configure(text=f"Помилка: {error_msg}", text_color="#ef233c")
            self.timer_label.configure(text=timer_text,                text_color="#ef233c")
            if self.icon_error:
                self.spinner_label.configure(image=self.icon_error, text="")
            else:
                self.spinner_label.configure(image=None, text="!")
        else:
            self.status_label.configure(text=success_msg, text_color="#a2a2d0")
            self.timer_label.configure(text=timer_text,   text_color="#a2a2d0")
            if self.icon_success:
                self.spinner_label.configure(image=self.icon_success, text="")
            else:
                self.spinner_label.configure(image=None, text="v")

    def _tick_taskbar(self):
        if not self.task_state.running:
            return
        self.timer_label.configure(text=self.task_state.elapsed_formatted)
        if self.spinner_frames:
            idx = self.task_state.next_frame_idx(len(self.spinner_frames))
            self.spinner_label.configure(image=self.spinner_frames[idx], text="")
        else:
            fallback = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            idx = self.task_state.next_frame_idx(len(fallback))
            self.spinner_label.configure(image=None, text=fallback[idx])
        self.task_state.tick_id = self.after(100, self._tick_taskbar)

    # Основна логіка

    def load_image(self):
        path = filedialog.askopenfilename(
            title="Оберіть сторінку коміксу",
            filetypes=[("Зображення", "*.jpg *.jpeg *.png *.webp"), ("Всі файли", "*.*")]
        )
        if not path:
            return

        self._reset_taskbar("Завантаження...")
        self.image_state.reset()
        self.image_state.path     = path
        self.image_state.original = Image.open(path)
        self.bubbles = []

        self.toggle_var.set(False)
        self.canvas.delete(self.placeholder)
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self._render_image(self.image_state.original)

        self.overlay_border.place(relx=1.0, rely=0.0, anchor="ne", x=-25, y=20)
        self._update_zoom_label()

        self.btn_ocr.configure(state="normal")
        self.btn_reset.configure(state="normal")
        self.btn_trans.configure(state="disabled")
        self.toggle.configure(state="disabled", button_color=("#a0a0a0", "#555555"))
        self.btn_save.configure(state="disabled")

        self._finish_task(success_msg=f"Завантажено: {os.path.basename(path)}", show_timer=False)
        self._set_report("")

    def run_ocr(self):
        if not self.image_state.loaded:
            return
        self._start_task("Розпізнавання тексту...")
        self.btn_ocr.configure(state="disabled")
        threading.Thread(target=self._ocr_worker, daemon=True).start()

    def _ocr_worker(self):
        try:
            self._ensure_pipeline()
            self.bubbles = self.pipeline_state.ocr.extract(self.image_state.path)

            if not self.bubbles:
                self.after(0, lambda: self._finish_task(error_msg="Текстових блоків не знайдено."))
                return

            report = "\n".join(f"[{i}] {b.get('text', '')}" for i, b in enumerate(self.bubbles, 1))
            count  = len(self.bubbles)
            self.after(0, lambda c=count: self._finish_task(success_msg=f"Розпізнано {c} баблів"))
            self.after(0, lambda r=report: self._set_report(r))
            self.after(0, lambda: self.btn_trans.configure(state="normal"))
        except Exception as exc:
            self.after(0, lambda e=exc: self._finish_task(error_msg=str(e)))
        finally:
            self.after(0, lambda: self.btn_ocr.configure(state="normal"))

    def run_translate(self):
        if not self.bubbles:
            return
        self._start_task("Переклад через сервер Dragoman...")
        self.btn_trans.configure(state="disabled")
        threading.Thread(target=self._translate_worker, daemon=True).start()

    def _translate_worker(self):
        try:
            self._ensure_pipeline()
            self.bubbles = self.pipeline_state.translator.translate_bubbles(self.bubbles)
            self._generate_overlay()

            lines = [
                f"[{i}] EN: {b.get('text', '')}\n     UK: {b.get('translation', '')}\n"
                for i, b in enumerate(self.bubbles, 1)
            ]
            report = "\n".join(lines)
            self.after(0, lambda: self._finish_task(success_msg="Переклад завершено"))
            self.after(0, lambda r=report: self._set_report(r))
            self.after(0, lambda: self.toggle.configure(state="normal", button_color=("#ffffff", "#cccccc")))
            self.after(0, lambda: self.btn_save.configure(state="normal"))
            if self.toggle_var.get():
                self.after(0, self.toggle_overlay)
        except Exception as exc:
            self.after(0, lambda e=exc: self._finish_task(error_msg=str(e)))
        finally:
            self.after(0, lambda: self.btn_trans.configure(state="normal"))

    def save_result(self):
        img = self.image_state.overlay or self.image_state.original
        if not img:
            return

        path = filedialog.asksaveasfilename(
            title="Зберегти результат",
            initialfile="translated_comic.png",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")]
        )
        if not path:
            return

        self._reset_taskbar("Збереження...")
        try:
            out = img.convert("RGB") if path.lower().endswith((".jpg", ".jpeg")) else img
            out.save(path)
            self._finish_task(success_msg=f"Збережено: {os.path.basename(path)}", show_timer=False)
        except Exception as exc:
            self._finish_task(error_msg=str(exc), show_timer=False)

    def reset_all(self):
        self.image_state.reset()
        self.pipeline_state.reset()
        self.bubbles = []
        self.toggle_var.set(False)

        self.overlay_border.place_forget()
        self.canvas.delete("all")
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

        self.placeholder = self.canvas.create_text(
            400, 300, fill="gray", justify="center", font=("Segoe UI", 13),
            text="Завантажте графічний файл для початку роботи\n\n"
                 "Ctrl + Колесо миші — Масштабування\n"
                 "ЛКМ (затиснути) — Переміщення картинки"
        )

        for btn in [self.btn_ocr, self.btn_trans, self.btn_save, self.btn_reset]:
            btn.configure(state="disabled")
        self.toggle.configure(state="disabled", button_color=("#a0a0a0", "#555555"))

        self._reset_taskbar("Ready")
        self._set_report("")

    # Внутрішні методи

    def _ensure_pipeline(self):
        if self.pipeline_state.ready:
            return
        url = self.url_entry.get().strip()
        if not url:
            raise ValueError("Не вказано URL Colab-сервера.")
        self.pipeline_state.initialize(url)

    def toggle_overlay(self):
        if not self.image_state.loaded:
            return
        self.image_state.show_overlay = self.toggle_var.get()
        img = (
            self.image_state.overlay
            if self.image_state.show_overlay and self.image_state.overlay
            else self.image_state.original
        )
        self._render_image(img)

    def _generate_overlay(self):
        if not self.image_state.loaded or not self.bubbles:
            return
        from pipeline.overlay import generate_overlay
        self.image_state.overlay = generate_overlay(self.image_state.original, self.bubbles)

    def _render_image(self, pil_image: Image.Image):
        self._current_display = pil_image
        self._redraw()

    def _redraw(self):
        if not hasattr(self, "_current_display"):
            return
        img = self._current_display
        cw  = max(800, self.canvas.winfo_width())
        ch  = max(600, self.canvas.winfo_height())

        ratio = min(cw / img.width, ch / img.height)
        nw = int(img.width  * ratio * self.image_state.zoom)
        nh = int(img.height * ratio * self.image_state.zoom)

        resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
        self._tk_image = ImageTk.PhotoImage(resized)

        self.canvas.delete("img")
        self.canvas.create_image(
            cw // 2, max(ch // 2, nh // 2),
            anchor="center", image=self._tk_image, tags="img"
        )
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        self._update_zoom_label()
        self.overlay_border.lift()

    def _on_canvas_resize(self, event):
        if not self.image_state.loaded:
            self.canvas.coords(self.placeholder, event.width / 2, event.height / 2)
        else:
            self._redraw()

    def _on_mouse_wheel(self, event):
        if not self.image_state.loaded:
            return
        ctrl_held = (event.state & 0x0004) != 0
        scroll_up = event.delta > 0
        if ctrl_held:
            delta = 0.15 if scroll_up else -0.15
            self.image_state.zoom = max(0.1, min(self.image_state.zoom + delta, 10.0))
            self._redraw()
        else:
            self.canvas.yview_scroll(-1 if scroll_up else 1, "units")

    def _on_drag_start(self, event):
        if self.image_state.loaded:
            self.canvas.scan_mark(event.x, event.y)

    def _on_drag_motion(self, event):
        if self.image_state.loaded:
            self.canvas.scan_dragto(event.x, event.y, gain=1)


if __name__ == "__main__":
    app = ComicsTranslatorApp()
    app.mainloop()