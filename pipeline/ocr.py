import requests
import base64
from pathlib import Path


class ComicOCR:
    def __init__(self, colab_url: str = ""):
        self.colab_url = colab_url.rstrip("/") if colab_url else ""

    def extract(self, image_path: str) -> list[dict]:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Зображення не знайдено: {image_path}")
        return self._extract_remote(image_path)

    def _extract_remote(self, image_path: str) -> list[dict]:
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()

        r = requests.post(
            f"{self.colab_url}/ocr",
            json={"image": encoded},
            timeout=60,
            headers={"ngrok-skip-browser-warning": "true"}
        )
        r.raise_for_status()
        data = r.json()

        if "error" in data:
            raise RuntimeError(data["error"])

        return data["bubbles"]