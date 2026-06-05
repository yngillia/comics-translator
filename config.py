import os

# Моделі
BASE_MODEL_ID  = "mistralai/Mistral-7B-v0.1"
LORA_PATH      = "/content/drive/MyDrive/models/LoRA-Dragoman"
GEMINI_API_KEY = "AQ.Ab8RN6KdisuTgfV4V9JbG5d-CKimimRhYZ_-RK7cezPsOHjt4A"

# OCR
OCR_ENGINE     = "easyocr"  # або "paddleocr"

# Переклад
BATCH_SIZE     = 2
MAX_LENGTH     = 128
MAX_NEW_TOKENS = 128

# Рендеринг
FONT_PATH      = "fonts/Comic_Sans_MS.ttf"
FONT_SIZE      = 14
TEXT_COLOR     = (0, 0, 0)       # чорний
BG_COLOR       = (255, 255, 255) # білий

COLAB_API_URL  = "https://thrower-sturdily-divisive.ngrok-free.dev"
PIPELINE_MODE  = "remote" if COLAB_API_URL else "local"