import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.language_detection import LanguageDetectionService


def test_english():
    svc = LanguageDetectionService()
    assert svc.detect("Book appointment with cardiologist tomorrow") == "en"


def test_hindi_heuristic():
    svc = LanguageDetectionService()
    assert svc.detect("मुझे कल डॉक्टर से मिलना है") == "hi"


def test_tamil_heuristic():
    svc = LanguageDetectionService()
    assert svc.detect("நாளை மருத்துவரை பார்க்க வேண்டும்") == "ta"
