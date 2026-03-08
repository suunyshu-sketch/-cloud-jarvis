"""
JARVIS — Test Configuration
Shared fixtures. DB tests require a live Supabase connection (skip in CI without DB).
"""
import pytest
import os


@pytest.fixture(scope="session")
def sample_messages():
    return [
        {"role": "user",      "content": "Hey JARVIS what is the weather today"},
        {"role": "assistant", "content": "Current weather in Hyderabad: Partly cloudy, 32°C, Humidity 65%"},
        {"role": "user",      "content": "remind me at 6pm to call doctor"},
    ]


@pytest.fixture(scope="session")
def sample_family_members():
    return ["lucky", "krishna", "sangeetha", "thapaswini", "dhruva", "prajwal"]


@pytest.fixture(scope="session")
def admin_token():
    """Returns a fake token for testing — not valid against real DB."""
    return "test_token_not_for_real_use"
