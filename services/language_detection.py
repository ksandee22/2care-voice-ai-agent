import logging
from typing import Optional

from langdetect import DetectorFactory, detect_langs

DetectorFactory.seed = 0

logger = logging.getLogger(__name__)

LANG_MAP = {
    "en": "en",
    "hi": "hi",
    "ta": "ta",
    "english": "en",
    "hindi": "hi",
    "tamil": "ta",
}

SUPPORTED = {"en", "hi", "ta"}


class LanguageDetectionService:
    def detect(self, text: str) -> str:
        if not text or not text.strip():
            return "en"

        try:
            langs = detect_langs(text)
            if langs:
                code = langs[0].lang
                if code in SUPPORTED:
                    return code
                if code == "mr" or code == "ne":
                    return "hi"
        except Exception as e:
            logger.debug("langdetect failed: %s", e)

        return self._heuristic(text)

    def _heuristic(self, text: str) -> str:
        for ch in text:
            if "\u0900" <= ch <= "\u097F":
                return "hi"
            if "\u0B80" <= ch <= "\u0BFF":
                return "ta"
        return "en"

    def normalize(self, code: Optional[str]) -> str:
        if not code:
            return "en"
        return LANG_MAP.get(code.lower(), code if code in SUPPORTED else "en")

    def display_name(self, code: str) -> str:
        return {"en": "English", "hi": "Hindi", "ta": "Tamil"}.get(code, "English")
