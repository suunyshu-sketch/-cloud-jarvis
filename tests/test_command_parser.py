"""
JARVIS — Unit Tests: Command Parser
Run: pytest tests/test_command_parser.py -v
"""
import pytest
from datetime import datetime, timezone
from backend.services.command_parser import (
    parse_reminder, parse_todo, parse_note, parse_birthday,
    is_weather_query, is_cricket_query, is_crypto_query,
    parse_show_todos, get_hindu_calendar, is_play_music_command
)


class TestReminderParser:
    def test_basic_reminder(self):
        r = parse_reminder("remind me at 6pm to call doctor")
        assert r is not None
        assert "call doctor" in r["task"]
        assert r["remind_at"].hour == 18

    def test_reminder_with_minutes(self):
        r = parse_reminder("remind me at 8:30am to take medicine")
        assert r is not None
        assert "take medicine" in r["task"]
        assert r["remind_at"].minute == 30

    def test_relative_reminder_hours(self):
        r = parse_reminder("remind me in 2 hours to check email")
        assert r is not None
        assert "check email" in r["task"]

    def test_relative_reminder_minutes(self):
        r = parse_reminder("remind me in 30 minutes to drink water")
        assert r is not None
        assert "drink water" in r["task"]

    def test_no_reminder(self):
        r = parse_reminder("what is the weather today")
        assert r is None


class TestTodoParser:
    def test_todo_prefix(self):
        t = parse_todo("todo: buy milk from the store")
        assert t is not None
        assert "buy milk" in t["task"]
        assert t["category"] == "shopping"

    def test_add_to_list(self):
        t = parse_todo("add to my list: call the doctor")
        assert t is not None
        assert "call the doctor" in t["task"]
        assert t["category"] == "health"

    def test_task_prefix(self):
        t = parse_todo("task: finish project report")
        assert t is not None
        assert "finish project report" in t["task"]
        assert t["category"] == "work"

    def test_no_todo(self):
        t = parse_todo("what time is it")
        assert t is None

    def test_show_todos(self):
        assert parse_show_todos("show my list") is True
        assert parse_show_todos("my todos") is True
        assert parse_show_todos("what time is it") is False


class TestNoteParser:
    def test_note_prefix(self):
        n = parse_note("note: meeting at 3pm tomorrow")
        assert n is not None
        assert "meeting at 3pm tomorrow" in n["content"]

    def test_save_note(self):
        n = parse_note("save note: important password is abc123")
        assert n is not None
        assert "important password" in n["content"]

    def test_remember_this(self):
        n = parse_note("remember this: my favorite color is blue")
        assert n is not None
        assert "favorite color" in n["content"]

    def test_no_note(self):
        n = parse_note("what is 2 + 2")
        assert n is None


class TestBirthdayParser:
    def test_month_day(self):
        b = parse_birthday("Dad's birthday is March 15")
        assert b is not None
        assert "Dad" in b["name"] or "dad" in b["name"].lower()
        assert "-03-15" in b["dob"]

    def test_full_date(self):
        b = parse_birthday("Krishna birthday is on 5th June 1965")
        assert b is not None
        assert "1965-06-05" == b["dob"]

    def test_no_birthday(self):
        b = parse_birthday("what is the weather")
        assert b is None


class TestQueryDetection:
    def test_weather_queries(self):
        assert is_weather_query("what is the weather today") is True
        assert is_weather_query("how hot is it") is True
        assert is_weather_query("play a song") is False

    def test_cricket_queries(self):
        assert is_cricket_query("cricket score today") is True
        assert is_cricket_query("IPL match result") is True
        assert is_cricket_query("what time is it") is False

    def test_crypto_queries(self):
        assert is_crypto_query("bitcoin price today") is True
        assert is_crypto_query("ethereum value in rupees") is True
        assert is_crypto_query("stock market news") is False

    def test_music_command(self):
        assert is_play_music_command("play Nadaniya song") == "nadaniya song"
        assert is_play_music_command("play AR Rahman hits") == "ar rahman hits"
        assert is_play_music_command("what time is it") is None


class TestHinduCalendar:
    def test_returns_string(self):
        result = get_hindu_calendar()
        assert isinstance(result, str)
        assert "Rahu Kalam" in result
        assert "Gulika" in result
        assert "Pooja" in result
