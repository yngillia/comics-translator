# pipeline/overlay.py
import os
import textwrap
from PIL import Image, ImageDraw, ImageFont

import config


def _get_font_path() -> str:
    if os.name == "nt" and os.path.exists(config.FONT_PATH_WIN):
        return config.FONT_PATH_WIN
    return config.FONT_PATH_LINUX


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(_get_font_path(), size)
    except (IOError, OSError):
        return ImageFont.load_default()


def _fit_text(
    draw: ImageDraw.Draw,
    text: str,
    inner_w: float,
    inner_h: float,
) -> tuple[list[str], ImageFont.FreeTypeFont, float]:
    best_lines: list[str] = [text]
    best_font       = _load_font(config.FONT_SIZE_MIN)
    best_line_h     = config.FONT_SIZE_MIN * config.LINE_HEIGHT_MULT
    found_match     = False

    for font_size in range(config.FONT_SIZE_MAX, config.FONT_SIZE_MIN - 1, -1):
        font        = _load_font(font_size)
        line_height = font_size * config.LINE_HEIGHT_MULT
        avg_char_w  = font_size * config.CHAR_WIDTH_RATIO
        chars_per_line = max(1, int(inner_w / avg_char_w))

        lines = textwrap.wrap(text, width=chars_per_line) or [text]

        max_line_w = 0.0
        for line in lines:
            try:
                lw = font.getlength(line)
            except AttributeError:
                lw = draw.textsize(line, font=font)[0]
            max_line_w = max(max_line_w, lw)

        total_h = line_height * len(lines)

        if total_h <= inner_h and max_line_w <= inner_w:
            best_lines  = lines
            best_font   = font
            best_line_h = line_height
            found_match = True
            break

    if not found_match:
        chars_per_line = max(1, int(inner_w / (config.FONT_SIZE_MIN * config.CHAR_WIDTH_RATIO)))
        best_lines  = textwrap.wrap(text, width=chars_per_line) or [text]
        best_font   = _load_font(config.FONT_SIZE_MIN)
        best_line_h = config.FONT_SIZE_MIN * config.LINE_HEIGHT_MULT

    return best_lines, best_font, best_line_h


def generate_overlay(original_image: Image.Image, bubbles: list[dict]) -> Image.Image:
    base  = original_image.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)

    for bubble in bubbles:
        if bubble.get("type", "dialogue") not in config.OVERLAY_TYPES:
            continue

        bbox     = bubble.get("text_box")
        raw_text = bubble.get("translation", "").strip()
        if not bbox or not raw_text:
            continue

        text = raw_text.upper() if config.TEXT_UPPER_CASE else raw_text

        ymin, xmin, ymax, xmax = bbox[0], bbox[1], bbox[2], bbox[3]
        box_w  = max(1, xmax - xmin)
        box_h  = max(1, ymax - ymin)
        radius = int(min(box_w, box_h) * config.BG_RADIUS_RATIO)

        draw.rounded_rectangle(
            [xmin, ymin, xmax, ymax],
            radius=radius,
            fill=(*config.BG_COLOR, config.BG_ALPHA),
        )

        pad_x   = box_w * config.PAD_X_RATIO
        pad_y   = box_h * config.PAD_Y_RATIO
        inner_w = box_w - pad_x * 2
        inner_h = box_h - pad_y * 2

        lines, font, line_height = _fit_text(draw, text, inner_w, inner_h)
        total_text_h = line_height * len(lines)
        current_y    = ymin + pad_y + (inner_h - total_text_h) / 2

        for line in lines:
            try:
                text_w = font.getlength(line)
            except AttributeError:
                text_w = draw.textsize(line, font=font)[0]

            x_pos = xmin + pad_x + (inner_w - text_w) / 2
            draw.text((x_pos, current_y), line, fill=config.TEXT_COLOR, font=font)
            current_y += line_height

    return Image.alpha_composite(base, layer)