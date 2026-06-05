import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import threading
import os
import time

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ComicsTranslatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Comics Translator")
        self.geometry("1100x800")
        self.minsize(700, 500)

        # Базовий стан програми
        self.original_image = None
        self.overlay_image = None
        self.tk_image = None
        self.zoom_factor = 1.0
        self.bubbles = []
        self.show_overlay = False
        self.image_path = None

        # Стан фонових тасок
        self.task_running = False
        self.task_start_time = 0.0
        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_idx = 0

        # Модулі бекенду
        self._pipeline_ready = False
        self._ocr = None
        self._translator = None

        # Поточна вкладка ("main" або "settings")
        self._current_tab = "main"

        self._build_ui()

    # ═══════════════════════════════════════════════════════════════ UI ═══════

    def _build_ui(self):
        # 1. Нижній статусний рядок
        self.taskbar = ctk.CTkFrame(self, height=35, corner_radius=0, fg_color=("#e9ecef", "#141423"))
        self.taskbar.pack(side="bottom", fill="x")
        self.taskbar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.taskbar, text=" Ready",
            font=("Segoe UI", 12), text_color="gray"
        )
        self.status_label.pack(side="left", padx=15)

        self.timer_label = ctk.CTkLabel(
            self.taskbar, text="0.0s",
            font=("Consolas", 12, "bold"), text_color="#a2a2d0"
        )
        self.timer_label.pack(side="right", padx=15)

        self.spinner_label = ctk.CTkLabel(self.taskbar, text="⚙️", font=("Segoe UI", 13))
        self.spinner_label.pack(side="right", padx=5)

        # 2. Ліва панель — заголовок + шестерня + вміст вкладок
        self.left_panel = ctk.CTkFrame(self, width=240, corner_radius=10)
        self.left_panel.pack(side="left", fill="y", padx=10, pady=10)
        self.left_panel.pack_propagate(False)

        # ── Заголовок з кнопкою налаштувань ──────────────────────────────────
        header = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 0))

        ctk.CTkLabel(
            header, text="Control Center",
            font=("Segoe UI", 16, "bold")
        ).pack(side="left")

        self.settings_btn = ctk.CTkButton(
            header,
            text="⚙",
            width=32,
            height=32,
            font=("Segoe UI", 16),
            fg_color="transparent",
            hover_color=("#d0d0d0", "#2a2a3a"),
            text_color=("gray40", "gray70"),
            command=self._toggle_tab,
        )
        self.settings_btn.pack(side="right")

        # ── Фрейм для вкладки «Головна» ───────────────────────────────────────
        self.main_tab = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.main_tab.pack(fill="both", expand=True)

        self.btn_open  = self._add_btn(self.main_tab, "📁 Відкрити сторінку", self.load_image)
        self.btn_ocr   = self._add_btn(self.main_tab, "🔍 Запустити OCR", self.run_ocr,
                                       color=("#1d3557", "#132237"), state="disabled")
        self.btn_trans = self._add_btn(self.main_tab, "🌐 Перекласти репліки", self.run_translate,
                                       color=("#1d3557", "#132237"), state="disabled")
        self.btn_save  = self._add_btn(self.main_tab, "💾 Зберегти результат", self.save_result,
                                       color=("#6b4226", "#4a2c17"), state="disabled")
        self.btn_reset = self._add_btn(self.main_tab, "🔄 Скинути все", self.reset_all,
                                       color="transparent", state="disabled")
        self.btn_reset.configure(border_width=1)

        self.toggle_var = ctk.BooleanVar(value=False)
        self.toggle = ctk.CTkSwitch(
            self.main_tab, text="Показати переклад",
            variable=self.toggle_var,
            command=self.toggle_overlay,
            state="disabled"
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

        # ── Фрейм для вкладки «Налаштування» (прихований спочатку) ───────────
        self.settings_tab = ctk.CTkFrame(self.left_panel, fg_color="transparent")

        ctk.CTkLabel(
            self.settings_tab,
            text="⚙  Налаштування",
            font=("Segoe UI", 14, "bold"),
        ).pack(padx=15, pady=(20, 4), anchor="w")

        ctk.CTkFrame(self.settings_tab, height=1, fg_color="#333").pack(fill="x", padx=15, pady=(0, 16))

        ctk.CTkLabel(
            self.settings_tab,
            text="Remote Server URL:",
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
            self.settings_tab,
            text="💾  Зберегти URL",
            height=36,
            font=("Segoe UI", 12, "bold"),
            command=self._save_url,
        )
        self.save_url_btn.pack(padx=15, fill="x")

        self.url_status = ctk.CTkLabel(
            self.settings_tab, text="",
            font=("Segoe UI", 10), text_color="#4cc9f0"
        )
        self.url_status.pack(padx=15, pady=(6, 0), anchor="w")

        # 3. Права панель — Canvas
        right_panel = ctk.CTkFrame(self, corner_radius=10)
        right_panel.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)
        right_panel.grid_rowconfigure(0, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(right_panel, bg="#11111e", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        v_scroll = ctk.CTkScrollbar(right_panel, orientation="vertical", command=self.canvas.yview)
        v_scroll.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=v_scroll.set)

        self.placeholder = self.canvas.create_text(
            400, 300, fill="gray", justify="center", font=("Segoe UI", 13),
            text="Завантажте графічний файл для початку роботи\n\n"
                 "🔍 Ctrl + Коліщатко — Масштабування\n↕️ Коліщатко — Прокрутка сторінки"
        )

        self.canvas.bind("<Configure>", self.on_resize)
        self.bind("<MouseWheel>", self.on_mouse_wheel)

    # ── Допоміжний метод для швидкого створення уніфікованих кнопок ───────
    def _add_btn(self, master, text, command, color=None, state="normal"):
        btn = ctk.CTkButton(
            master,
            text=text,
            command=command,
            state=state,
            height=38,
            font=("Segoe UI", 12, "bold")
        )
        if color is not None:
            btn.configure(fg_color=color)
        btn.pack(padx=15, pady=5, fill="x")
        return btn

    # ═══════════════════════════════════════════ Перемикання вкладок ══════════

    def _toggle_tab(self):
        if self._current_tab == "main":
            self.main_tab.pack_forget()
            self.settings_tab.pack(fill="both", expand=True)
            self._current_tab = "settings"
            self.settings_btn.configure(text="✕", text_color=("#e63946", "#e63946"))
        else:
            self.settings_tab.pack_forget()
            self.main_tab.pack(fill="both", expand=True)
            self._current_tab = "main"
            self.settings_btn.configure(text="⚙", text_color=("gray40", "gray70"))

    def _save_url(self):
        url = self.url_entry.get().strip()
        if url:
            self._pipeline_ready = False  # скидаємо щоб перепідключитись
            self.url_status.configure(text="✓ URL збережено", text_color="#4cc9f0")
        else:
            self.url_status.configure(text="⚠ Введіть URL", text_color="#e63946")

    # ═══════════════════════════════════════ Система керування завданнями ════

    def _start_async_task(self, msg):
        self.task_running = True
        self.task_start_time = time.time()
        self.status_label.configure(text=f"⏳ {msg}", text_color=("#0077b6", "#90e0ef"))
        self._tick_taskbar()

    def _stop_async_task(self, success_msg, error_msg=None):
        self.task_running = False
        elapsed = time.time() - self.task_start_time if self.task_start_time else 0.0

        if error_msg:
            self.status_label.configure(text=f"❌ Помилка: {error_msg}", text_color="#ef233c")
            self.spinner_label.configure(text="⚠️")
            self.timer_label.configure(text=f"Fail ({elapsed:.1f}s)", text_color="#ef233c")
        else:
            self.status_label.configure(text=f"✅ {success_msg}", text_color=("#2d6a4f", "#757bc8"))
            self.spinner_label.configure(text="✨")
            self.timer_label.configure(text=f"{elapsed:.1f}s", text_color="#4cc9f0")

    def _tick_taskbar(self):
        if not self.task_running:
            return
        elapsed = time.time() - self.task_start_time
        self.timer_label.configure(text=f"{elapsed:.1f}s")
        self.spinner_label.configure(text=self.spinner_frames[self.spinner_idx])
        self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_frames)
        self.after(100, self._tick_taskbar)

    # ════════════════════════════════════════════════════ Логіка процесів ════

    def load_image(self):
        path = filedialog.askopenfilename(
            title="Оберіть сторінку коміксу",
            filetypes=[("Зображення", "*.jpg *.jpeg *.png *.webp"), ("Всі файли", "*.*")]
        )
        if not path:
            return

        self.image_path = path
        self.original_image = Image.open(path)
        self.overlay_image = None
        self.bubbles = []
        self.zoom_factor = 1.0
        self.show_overlay = False
        self.toggle_var.set(False)

        self.canvas.delete(self.placeholder)
        self._show_image(self.original_image)

        self.btn_ocr.configure(state="normal")
        self.btn_reset.configure(state="normal")
        self.btn_trans.configure(state="disabled")
        self.toggle.configure(state="disabled")
        self.btn_save.configure(state="disabled")

        self._stop_async_task(f"Завантажено: {os.path.basename(path)}")
        self._set_report("")

    def run_ocr(self):
        if not self.image_path:
            return
        self._start_async_task("Обробка зображення, розпізнавання баблів за допомогою OCR...")
        self.btn_ocr.configure(state="disabled")
        threading.Thread(target=self._ocr_worker, daemon=True).start()

    def _ocr_worker(self):
        try:
            self._ensure_pipeline()
            self.bubbles = self._ocr.extract(self.image_path)

            if not self.bubbles:
                self.after(0, lambda: self._stop_async_task("Завершено", error_msg="Текстових блоків не знайдено."))
                self.after(0, lambda: self.btn_ocr.configure(state="normal"))
                return

            report = "\n".join(f"[{i}] {b.get('text', '')}" for i, b in enumerate(self.bubbles, 1))
            self.after(0, lambda: self._stop_async_task(f"Успішно розпізнано {len(self.bubbles)} баблів"))
            self.after(0, lambda: self._set_report(report))
            self.after(0, lambda: self.btn_trans.configure(state="normal"))
        except Exception as e:
            self.after(0, lambda: self._stop_async_task("", error_msg=str(e)))
        finally:
            self.after(0, lambda: self.btn_ocr.configure(state="normal"))

    def run_translate(self):
        if not self.bubbles:
            return
        self._start_async_task("Зв'язок із сервером LLM Dragoman. Виконується контекстний переклад...")
        self.btn_trans.configure(state="disabled")
        threading.Thread(target=self._translate_worker, daemon=True).start()

    def _translate_worker(self):
        try:
            self._ensure_pipeline()
            self.bubbles = self._translator.translate_bubbles(self.bubbles)
            self._generate_overlay()

            lines = []
            for i, b in enumerate(self.bubbles, 1):
                lines.append(f"[{i}] EN: {b.get('text', '')}\n     UK: {b.get('translation', '')}\n")

            self.after(0, lambda: self._stop_async_task("Переклад успішно інтегровано в інтерфейс!"))
            self.after(0, lambda: self._set_report("\n".join(lines)))
            self.after(0, lambda: self.toggle.configure(state="normal"))
            self.after(0, lambda: self.btn_save.configure(state="normal"))
            if self.toggle_var.get():
                self.after(0, self.toggle_overlay)
        except Exception as e:
            self.after(0, lambda: self._stop_async_task("", error_msg=str(e)))
        finally:
            self.after(0, lambda: self.btn_trans.configure(state="normal"))

    def save_result(self):
        img = self.overlay_image if self.overlay_image else self.original_image
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

        try:
            save_img = img.convert("RGB") if path.lower().endswith((".jpg", ".jpeg")) else img
            save_img.save(path)
            self._stop_async_task(f"Файл збережено: {os.path.basename(path)}")
        except Exception as e:
            self._stop_async_task("", error_msg=str(e))

    def reset_all(self):
        self.original_image = None
        self.overlay_image = None
        self.tk_image = None
        self.zoom_factor = 1.0
        self.bubbles = []
        self.show_overlay = False
        self.image_path = None
        self._pipeline_ready = False

        self.canvas.delete("all")
        self.placeholder = self.canvas.create_text(
            400, 300, fill="gray", justify="center", font=("Segoe UI", 13),
            text="Завантажте графічний файл для початку роботи"
        )

        self.toggle_var.set(False)
        for btn in [self.btn_ocr, self.btn_trans, self.btn_save, self.btn_reset]:
            btn.configure(state="disabled")
        self.toggle.configure(state="disabled")
        self.status_label.configure(text=" Ready", text_color="gray")
        self.timer_label.configure(text="0.0s", text_color="#a2a2d0")
        self.spinner_label.configure(text="⚙️")
        self._set_report("")

    # ══════════════════════════════════════════════════════ Внутрішні хелпери ═

    def _ensure_pipeline(self):
        if self._pipeline_ready:
            return
        from pipeline.ocr import ComicOCR
        from pipeline.translator import ComicTranslator

        url = self.url_entry.get().strip()
        if not url:
            raise ValueError("Помилка конфігурації: Не вказано віддалений серверний URL (Colab Link).")

        self._ocr = ComicOCR(colab_url=url)
        self._translator = ComicTranslator(colab_url=url)
        self._pipeline_ready = True

    def _load_config_url(self):
        try:
            from config import COLAB_API_URL
            if COLAB_API_URL:
                self.url_entry.insert(0, COLAB_API_URL)
        except ImportError:
            pass

    def toggle_overlay(self):
        if not self.original_image:
            return
        self.show_overlay = self.toggle_var.get()
        self._show_image(
            self.overlay_image if (self.show_overlay and self.overlay_image)
            else self.original_image
        )

    def _generate_overlay(self):
        if not self.original_image or not self.bubbles:
            return
        from pipeline.overlay import generate_overlay
        self.overlay_image = generate_overlay(self.original_image, self.bubbles)

    def _show_image(self, pil_image: Image.Image):
        self.current_display_image = pil_image
        self._redraw()

    def _redraw(self):
        if not hasattr(self, "current_display_image"):
            return
        cw = max(800, self.canvas.winfo_width())
        ch = max(600, self.canvas.winfo_height())
        img = self.current_display_image
        ratio = min(cw / img.width, ch / img.height)
        nw = int(img.width  * ratio * self.zoom_factor)
        nh = int(img.height * ratio * self.zoom_factor)

        resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)

        self.canvas.delete("img")
        self.canvas.create_image(
            cw // 2, max(ch // 2, nh // 2),
            anchor="center", image=self.tk_image, tags="img"
        )
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def on_resize(self, event):
        if not self.original_image:
            self.canvas.coords(self.placeholder, event.width / 2, event.height / 2)
        else:
            self._redraw()

    def on_mouse_wheel(self, event):
        if not self.original_image:
            return
        ctrl = (event.state & 0x0004) != 0
        up = event.delta > 0
        if ctrl:
            self.zoom_factor = max(0.1, min(self.zoom_factor + (0.15 if up else -0.15), 10.0))
            self._redraw()
        else:
            self.canvas.yview_scroll(-1 if up else 1, "units")

    def _set_report(self, text: str):
        self.report_box.configure(state="normal")
        self.report_box.delete("1.0", "end")
        self.report_box.insert("end", text)
        self.report_box.configure(state="disabled")


if __name__ == "__main__":
    app = ComicsTranslatorApp()
    app.mainloop()