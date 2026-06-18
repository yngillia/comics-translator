import os

# Сервер
COLAB_API_URL  = "https://thrower-sturdily-divisive.ngrok-free.dev"
PIPELINE_MODE  = "remote" if COLAB_API_URL else "local"

# Переклад
BATCH_SIZE     = 2
MAX_LENGTH     = 128
MAX_NEW_TOKENS = 128

# Шрифт оверлею
FONT_PATH_WIN   = "fonts/Comic_Sans_MS.ttf"
FONT_PATH_LINUX = "DejaVuSans.ttf"
FONT_SIZE_MAX   = 55
FONT_SIZE_MIN   = 12

# Текст оверлею
TEXT_UPPER_CASE  = True
CHAR_WIDTH_RATIO = 0.65
LINE_HEIGHT_MULT = 1.15

# Фон бульбашки
BG_COLOR        = (255, 255, 255)
BG_ALPHA        = 230
BG_RADIUS_RATIO = 0.15

# Колір тексту (RGBA)
TEXT_COLOR = (0, 0, 0, 255)

# Відступи всередині бульбашки
PAD_X_RATIO = 0.05
PAD_Y_RATIO = 0.04

# Типи бульбашок для рендерингу оверлею
OVERLAY_TYPES = {"dialogue", "narration", "thought", "caption"}

# Шляхи до ресурсів
ASSETS_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SPINNER_GIF     = os.path.join(ASSETS_DIR, "spinner.gif")
APP_ICON        = os.path.join(ASSETS_DIR, "app_icon.ico")
ICON_SETTINGS   = os.path.join(ASSETS_DIR, "settings.png")
ICON_BACK       = os.path.join(ASSETS_DIR, "back_arrow.png")
ICON_SUCCESS    = os.path.join(ASSETS_DIR, "success.png")
ICON_ERROR      = os.path.join(ASSETS_DIR, "error.png")

# Вікно
WINDOW_TITLE    = "Comics Translator"
WINDOW_GEOMETRY = "1100x800"
WINDOW_MINSIZE  = (700, 500)
CANVAS_BG       = "#11111e"