import requests


class ComicTranslator:
    def __init__(self, colab_url: str):
        self.colab_url = colab_url.rstrip("/")

    def translate_bubbles(self, bubbles: list[dict]) -> list[dict]:
        if not bubbles:
            return []

        r = requests.post(
            f"{self.colab_url}/translate",
            json={"bubbles": bubbles},
            timeout=120,
            headers={"ngrok-skip-browser-warning": "true"}
        )
        r.raise_for_status()
        data = r.json()

        if "error" in data:
            raise RuntimeError(data["error"])

        return data["bubbles"]