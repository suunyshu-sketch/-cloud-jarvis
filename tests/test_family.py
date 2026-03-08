"""
JARVIS — Unit Tests: Family Utils
"""
import pytest
from backend.utils.family import (
    resolve_person, is_admin, get_admin_keys,
    get_family_info, get_all_members
)


class TestResolvePerson:
    def test_direct_key(self):
        display, member = resolve_person("lucky")
        assert display == "Lucky"
        assert member is not None
        assert member["role"] == "admin"

    def test_alias_mom(self):
        display, member = resolve_person("mom")
        assert display == "Sangeetha"

    def test_alias_amma(self):
        display, member = resolve_person("amma")
        assert display == "Sangeetha"

    def test_alias_nanna(self):
        display, member = resolve_person("nanna")
        assert display == "Krishna"

    def test_case_insensitive(self):
        display, member = resolve_person("LUCKY")
        assert display == "Lucky"

    def test_unknown_person(self):
        display, member = resolve_person("john doe")
        assert member is None

    def test_empty_string(self):
        display, member = resolve_person("")
        assert member is None


class TestIsAdmin:
    def test_lucky_is_admin(self):
        assert is_admin("lucky") is True
        assert is_admin("Lucky") is True
        assert is_admin("lakshmi narayana") is True

    def test_non_admin(self):
        assert is_admin("krishna") is False
        assert is_admin("sangeetha") is False

    def test_empty(self):
        assert is_admin("") is False


class TestFamilyData:
    def test_family_info_loaded(self):
        info = get_family_info()
        assert info["surname"] == "Battini"
        assert info["religion"] == "Hindu"

    def test_members_loaded(self):
        members = get_all_members()
        assert len(members) == 6
        keys = [m["key"] for m in members]
        assert "lucky" in keys
        assert "krishna" in keys
        assert "sangeetha" in keys
