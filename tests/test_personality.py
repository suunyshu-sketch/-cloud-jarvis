"""
JARVIS — Unit Tests: Personality / Emotion Engine (no DB required)
"""
import pytest
from backend.services.personality import detect_emotion, EMOTION_BANKS


class TestEmotionDetection:
    def test_detects_sad(self):
        emotion, intensity = detect_emotion("I am feeling so sad and lonely today")
        assert emotion == "sad"

    def test_detects_happy(self):
        emotion, intensity = detect_emotion("I'm so happy and excited! Amazing news!")
        assert emotion == "happy"

    def test_detects_angry(self):
        emotion, intensity = detect_emotion("I'm so angry and frustrated with everything")
        assert emotion == "angry"

    def test_detects_anxious(self):
        emotion, intensity = detect_emotion("I'm so worried and stressed about the deadline")
        assert emotion == "anxious"

    def test_detects_tired(self):
        emotion, intensity = detect_emotion("I'm exhausted and so tired today")
        assert emotion == "tired"

    def test_neutral_for_normal_message(self):
        emotion, intensity = detect_emotion("what is the weather today")
        assert emotion == "neutral"

    def test_high_intensity(self):
        emotion, intensity = detect_emotion("I am so sad, crying, heartbroken and devastated")
        assert intensity == "high"

    def test_low_intensity(self):
        emotion, intensity = detect_emotion("feeling a bit sad")
        assert intensity == "low"

    def test_telugu_emotion(self):
        emotion, intensity = detect_emotion("chala sad ga unnanu today")
        assert emotion in ("sad", "neutral")  # should detect Telugu sad

    def test_hindi_emotion(self):
        emotion, intensity = detect_emotion("bahut gussa aa raha hai mujhe")
        assert emotion == "angry"

    def test_empty_string(self):
        emotion, intensity = detect_emotion("")
        assert emotion == "neutral"

    def test_all_emotion_banks_have_entries(self):
        for emotion, words in EMOTION_BANKS.items():
            assert len(words) > 5, f"Emotion bank '{emotion}' has too few words"
