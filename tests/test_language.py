"""
JARVIS — Unit Tests: Language Detection
"""
import pytest
from backend.utils.language import detect_language, detect_lang_change, get_lang_instruction


class TestLanguageDetection:
    def test_english_default(self):
        assert detect_language("hello how are you") == "english"

    def test_telugu_script(self):
        assert detect_language("నమస్కారం ఏమి చేస్తున్నారు") == "telugu"

    def test_hindi_script(self):
        assert detect_language("नमस्ते कैसे हो") == "hindi"

    def test_telugu_transliteration(self):
        # Common Telugu words in Roman
        assert detect_language("ela undi bro chala badhaga") == "telugu"

    def test_hindi_transliteration(self):
        assert detect_language("kya hua bhai bahut thaka") == "hindi"

    def test_empty_string(self):
        assert detect_language("") == "english"


class TestLangChange:
    def test_switch_to_telugu(self):
        assert detect_lang_change("speak in telugu") == "telugu"
        assert detect_lang_change("reply in Telugu please") == "telugu"

    def test_switch_to_hindi(self):
        assert detect_lang_change("speak in hindi") == "hindi"

    def test_switch_to_english(self):
        assert detect_lang_change("speak in english") == "english"

    def test_no_switch(self):
        assert detect_lang_change("what is the weather today") is None


class TestLangInstruction:
    def test_telugu_instruction(self):
        inst = get_lang_instruction("telugu")
        assert "Telugu" in inst
        assert "తెలుగు" in inst

    def test_hindi_instruction(self):
        inst = get_lang_instruction("hindi")
        assert "Hindi" in inst
        assert "हिंदी" in inst

    def test_english_instruction(self):
        inst = get_lang_instruction("english")
        assert "English" in inst
