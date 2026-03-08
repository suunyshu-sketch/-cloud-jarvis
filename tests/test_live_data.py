"""
JARVIS — Unit Tests: Live Data Helpers (no network required)
Tests only the pure helper functions that don't need network calls.
"""
import pytest
from backend.services.command_parser import (
    is_currency_query, is_weather_query, is_cricket_query,
    is_crypto_query, is_stock_query, is_url
)


class TestCurrencyQueryParser:
    def test_usd_to_inr_with_amount(self):
        is_q, fc, tc, amt = is_currency_query("convert 100 usd to inr")
        assert is_q is True
        assert fc == "USD"
        assert tc == "INR"
        assert amt == 100.0

    def test_dollar_to_rupee(self):
        is_q, fc, tc, amt = is_currency_query("1 dollar in rupees")
        assert is_q is True
        assert fc == "USD"
        assert tc == "INR"

    def test_exchange_rate_keyword(self):
        is_q, fc, tc, amt = is_currency_query("what is the exchange rate today")
        assert is_q is True

    def test_non_currency(self):
        is_q, fc, tc, amt = is_currency_query("what is the weather today")
        assert is_q is False

    def test_eur_to_inr(self):
        is_q, fc, tc, amt = is_currency_query("50 euros to inr")
        assert is_q is True
        assert fc == "EUR"
        assert tc == "INR"
        assert amt == 50.0


class TestQueryDetectors:
    def test_weather_yes(self):
        assert is_weather_query("what is the weather today") is True
        assert is_weather_query("how hot is it outside") is True
        assert is_weather_query("will it rain tomorrow") is True

    def test_weather_no(self):
        assert is_weather_query("play a song") is False
        assert is_weather_query("hello how are you") is False

    def test_cricket_yes(self):
        assert is_cricket_query("cricket score today") is True
        assert is_cricket_query("IPL match result") is True

    def test_cricket_no(self):
        assert is_cricket_query("what time is it") is False

    def test_crypto_yes(self):
        assert is_crypto_query("bitcoin price today") is True
        assert is_crypto_query("ethereum in rupees") is True
        assert is_crypto_query("dogecoin rate") is True

    def test_crypto_no(self):
        assert is_crypto_query("cricket news") is False

    def test_stock_yes(self):
        assert is_stock_query("reliance share price today") is True
        assert is_stock_query("nifty 50 today") is True
        assert is_stock_query("sensex current level") is True

    def test_url_detection(self):
        url = is_url("can you summarize https://bbc.com/news/article123")
        assert url == "https://bbc.com/news/article123"

    def test_url_no_summarize_keyword(self):
        url = is_url("check https://google.com")
        assert url is None
