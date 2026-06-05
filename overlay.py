# pipeline/overlay.py
"""
Модуль для накладання перекладеного тексту на зображення коміксів.
Всі параметри зведені тут — редагуйте цей файл для налаштування вигляду.
"""

import os
import textwrap
from PIL import Image, ImageDraw, ImageFont


# ══════════════════════════════════════════════════════════════════
#  НАЛАШТУВАННЯ — редагуйте ці константи
# ══════════════════════════════════════════════════════════════════

# --- Шрифт ---
FONT_PATH_WIN   = "fonts/Comic_Sans_MS.ttf"   # Windows
FONT_PATH_LINUX = "DejaVuSans.ttf"            # Linux / Colab fallback
FONT_SIZE_MAX   = 55                          # максимальний розмір шрифту (px)
FONT_SIZE_MIN   = 12                           # мінімальний розмір шрифту (px)

# --- Текст ---
TEXT_UPPER_CASE  = True                       # переводити текст у ВЕРХНІЙ РЕГІСТР
CHAR_WIDTH_RATIO = 0.65                       # коефіцієнт ширини символу (для переносу)
LINE_HEIGHT_MULT = 1.15                       # міжрядковий інтервал (× розмір шрифту)

# --- Фон бульбашки ---
BG_COLOR         = (255, 255, 255)            # RGB колір фону
BG_ALPHA         = 230                        # прозорість фону (0=прозорий, 255=непрозорий)
BG_RADIUS_RATIO  = 0.15                       # заокруглення кутів (частка від меншої сторони)

# --- Текст ---
TEXT_COLOR       = (0, 0, 0, 255)            # RGBA колір тексту

# --- Відступи всередині бульбашки ---
PAD_X_RATIO      = 0.05                      # горизонтальний відступ (частка від ширини)
PAD_Y_RATIO      = 0.04                      # вертикальний відступ (частка від висоти)

# --- Типи бульбашок: для яких робити оверлей ---
# Можна прибрати 'narration', щоб не перекривати підписи
OVERLAY_TYPES    = {"dialogue", "narration", "thought", "caption"}

# ══════════════════════════════════════════════════════════════════


def _get_font_path() -> str:
    """Повертає шлях до шрифту залежно від ОС."""
    if os.name == "nt" and os.path.exists(FONT_PATH_WIN):
        return FONT_PATH_WIN
    return FONT_PATH_LINUX


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Завантажує шрифт заданого розміру, з fallback на стандартний."""
    try:
        return ImageFont.truetype(_get_font_path(), size)
    except (IOError, OSError):
        return ImageFont.load_default()


def _fit_text(draw: ImageDraw.Draw, text: str,
              inner_w: float, inner_h: float) -> tuple[list[str], ImageFont.FreeTypeFont, float]:
    """
    Розумний підбір розміру шрифту та переносу рядків для коміксних баблів.
    Шукає баланс, щоб текст заповнював бокс пропорційно.
    """
    best_lines: list[str] = [text]
    best_font = _load_font(FONT_SIZE_MIN)
    best_line_height = FONT_SIZE_MIN * LINE_HEIGHT_MULT

    # Прапорець: чи знайшли ми бодай один варіант, який повністю вліз
    found_match = False

    # Ідемо від МАКСИМАЛЬНОГО шрифту до МІНІМАЛЬНОГО
    for font_size in range(FONT_SIZE_MAX, FONT_SIZE_MIN - 1, -1):
        font = _load_font(font_size)
        line_height = font_size * LINE_HEIGHT_MULT

        # 🎯 ГОЛОВНА ФІШКА: Динамічно підбираємо ширину переносу (в символах)
        # залежно від того, яка ширина боксу у пікселях для поточного розміру шрифту
        avg_char_w = font_size * CHAR_WIDTH_RATIO
        chars_per_line = max(1, int(inner_w / avg_char_w))

        # Робимо перенос рядків
        current_lines = textwrap.wrap(text, width=chars_per_line)
        if not current_lines:
            current_lines = [text]

        # Рахуємо реальну ширину найдовшого рядка у пікселях
        max_line_w = 0.0
        for line in current_lines:
            try:
                lw = font.getlength(line)
            except AttributeError:
                lw = draw.textsize(line, font=font)[0]
            max_line_w = max(max_line_w, lw)

        # Рахуємо загальну висоту всього блоку тексту
        total_h = line_height * len(current_lines)

        # Перевіряємо, чи вписується текст у рамки
        if total_h <= inner_h and max_line_w <= inner_w:
            # Оскільки ми йдемо від більшого шрифту до меншого,
            # перший варіант, який вліз — це і є наш ідеальний МАКСИМАЛЬНИЙ розмір!
            best_lines = current_lines
            best_font = font
            best_line_height = line_height
            found_match = True
            break  # Зупиняємо пошук, бо знайшли найкращий великий варіант

    # Якщо текст такий довгий, що навіть на мінімальному шрифті не вліз —
    # повертаємо останній прорахований варіант (щоб хоч щось намалювалось)
    if not found_match:
        chars_per_line = max(1, int(inner_w / (FONT_SIZE_MIN * CHAR_WIDTH_RATIO)))
        best_lines = textwrap.wrap(text, width=chars_per_line)
        best_font = _load_font(FONT_SIZE_MIN)
        best_line_height = FONT_SIZE_MIN * LINE_HEIGHT_MULT

    return best_lines, best_font, best_line_height


def generate_overlay(original_image: Image.Image, bubbles: list[dict]) -> Image.Image:
    """
    Накладає переклад на зображення з коректною напівпрозорістю фону.
    """
    # 1. Переводимо оригінал в RGBA
    base_image = original_image.convert("RGBA")

    # 2. Створюємо новий абсолютно прозорий шар ТАКОГО Ж розміру для малювання
    overlay_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay_layer)

    for bubble in bubbles:
        bubble_type = bubble.get("type", "dialogue")
        if bubble_type not in OVERLAY_TYPES:
            continue

        bbox = bubble.get("text_box")
        raw_text = bubble.get("translation", "").strip()

        if not bbox or not raw_text:
            continue

        text = raw_text.upper() if TEXT_UPPER_CASE else raw_text

        ymin, xmin, ymax, xmax = bbox[0], bbox[1], bbox[2], bbox[3]
        box_w = max(1, xmax - xmin)
        box_h = max(1, ymax - ymin)

        # --- Фон малюється на overlay_layer ---
        radius = int(min(box_w, box_h) * BG_RADIUS_RATIO)
        fill_color = (*BG_COLOR, BG_ALPHA)  # Тепер (255, 255, 255, 100) спрацює ідеально
        draw.rounded_rectangle(
            [xmin, ymin, xmax, ymax],
            radius=radius,
            fill=fill_color
        )

        # --- Відступи ---
        pad_x = box_w * PAD_X_RATIO
        pad_y = box_h * PAD_Y_RATIO
        inner_w = box_w - pad_x * 2
        inner_h = box_h - pad_y * 2

        # --- Підбір тексту ---
        lines, font, line_height = _fit_text(draw, text, inner_w, inner_h)
        total_text_h = line_height * len(lines)

        # Вертикальне центрування
        current_y = ymin + pad_y + (inner_h - total_text_h) / 2

        # --- Малювання тексту (також на overlay_layer) ---
        for line in lines:
            try:
                text_w = font.getlength(line)
            except AttributeError:
                text_w = draw.textsize(line, font=font)[0]

            x_pos = xmin + pad_x + (inner_w - text_w) / 2
            draw.text((x_pos, current_y), line, fill=TEXT_COLOR, font=font)
            current_y += line_height

    # 3. Ключовий крок: правильне математичне поєднання двох шарів з альфа-каналом
    result = Image.alpha_composite(base_image, overlay_layer)

    return result
