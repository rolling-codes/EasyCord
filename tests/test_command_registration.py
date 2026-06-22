"""Tests for upfront Discord command constraint validation."""
from __future__ import annotations

import pytest

from easycord._command_registration import _validate_command


# ---------------------------------------------------------------------------
# Name constraints
# ---------------------------------------------------------------------------

class TestCommandNameValidation:
    def test_name_within_limit_passes(self) -> None:
        # 32-char name is exactly at the limit — must not raise
        name = "a" * 32
        _validate_command(name, "A valid description.")

    def test_name_one_char_passes(self) -> None:
        _validate_command("a", "Fine.")

    def test_name_exceeds_32_chars_raises(self) -> None:
        name = "a" * 33
        with pytest.raises(ValueError) as exc_info:
            _validate_command(name, "Some description.")
        msg = str(exc_info.value)
        assert "33" in msg
        assert "32" in msg
        assert name in msg

    def test_name_exceeds_limit_error_message_format(self) -> None:
        name = "my_very_long_command_name_here_xx"  # 33 chars
        assert len(name) == 33
        with pytest.raises(ValueError, match=r"exceeds Discord's 32-character limit"):
            _validate_command(name, "desc")

    def test_name_with_invalid_chars_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            _validate_command("My Command!", "desc")

    def test_name_with_uppercase_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            _validate_command("MyCommand", "desc")

    def test_name_with_spaces_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            _validate_command("my command", "desc")

    def test_name_with_underscores_and_hyphens_passes(self) -> None:
        _validate_command("my_cmd-name", "desc")

    def test_name_with_digits_passes(self) -> None:
        _validate_command("cmd123", "desc")

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError):
            _validate_command("", "desc")


# ---------------------------------------------------------------------------
# Description constraints
# ---------------------------------------------------------------------------

class TestCommandDescriptionValidation:
    def test_description_within_limit_passes(self) -> None:
        desc = "x" * 100
        _validate_command("cmd", desc)

    def test_description_exactly_100_chars_passes(self) -> None:
        desc = "d" * 100
        assert len(desc) == 100
        _validate_command("cmd", desc)

    def test_description_exceeds_100_chars_raises(self) -> None:
        desc = "d" * 101
        with pytest.raises(ValueError) as exc_info:
            _validate_command("cmd", desc)
        msg = str(exc_info.value)
        assert "101" in msg
        assert "100" in msg
        assert "cmd" in msg

    def test_description_exceeds_limit_error_message_format(self) -> None:
        desc = "x" * 143
        with pytest.raises(ValueError, match=r"exceeds Discord's 100-character limit"):
            _validate_command("help", desc)

    def test_description_error_includes_command_name(self) -> None:
        long_desc = "y" * 150
        with pytest.raises(ValueError, match=r"for 'help'"):
            _validate_command("help", long_desc)


# ---------------------------------------------------------------------------
# Option count constraints
# ---------------------------------------------------------------------------

class TestOptionCountValidation:
    def _make_func_with_n_params(self, n: int):
        """Return a callable whose signature has `self` + n user parameters."""
        param_names = ", ".join(f"p{i}" for i in range(n))
        src = f"def cmd(self, {param_names}): pass"
        ns: dict = {}
        exec(src, ns)  # noqa: S102
        return ns["cmd"]

    def test_25_options_passes(self) -> None:
        func = self._make_func_with_n_params(25)
        _validate_command("cmd", "desc", func=func)

    def test_26_options_raises(self) -> None:
        func = self._make_func_with_n_params(26)
        with pytest.raises(ValueError) as exc_info:
            _validate_command("my_cmd", "desc", func=func)
        msg = str(exc_info.value)
        assert "26" in msg
        assert "25" in msg
        assert "my_cmd" in msg

    def test_option_count_error_message_format(self) -> None:
        func = self._make_func_with_n_params(27)
        with pytest.raises(ValueError, match=r"has 27 options; Discord allows at most 25"):
            _validate_command("my_cmd", "desc", func=func)

    def test_no_func_skips_option_check(self) -> None:
        # Should not raise when func is None
        _validate_command("cmd", "desc", func=None)

    def test_zero_options_passes(self) -> None:
        func = self._make_func_with_n_params(0)
        _validate_command("cmd", "desc", func=func)


# ---------------------------------------------------------------------------
# Choice count constraints
# ---------------------------------------------------------------------------

class TestChoiceCountValidation:
    def test_25_choices_passes(self) -> None:
        choices = {"color": list(range(25))}
        _validate_command("cmd", "desc", choices=choices)

    def test_26_choices_raises(self) -> None:
        choices = {"color": list(range(26))}
        with pytest.raises(ValueError) as exc_info:
            _validate_command("cmd", "desc", choices=choices)
        msg = str(exc_info.value)
        assert "26" in msg
        assert "25" in msg
        assert "color" in msg
        assert "cmd" in msg

    def test_choice_error_message_format(self) -> None:
        choices = {"size": list(range(30))}
        with pytest.raises(ValueError, match=r"has 30 choices; Discord allows at most 25"):
            _validate_command("cmd", "desc", choices=choices)

    def test_no_choices_skips_choice_check(self) -> None:
        _validate_command("cmd", "desc", choices=None)

    def test_empty_choices_dict_skips_check(self) -> None:
        _validate_command("cmd", "desc", choices={})

    def test_multiple_params_one_over_limit_raises(self) -> None:
        choices = {
            "color": list(range(10)),   # fine
            "size": list(range(26)),    # over limit
        }
        with pytest.raises(ValueError, match="size"):
            _validate_command("cmd", "desc", choices=choices)


# ---------------------------------------------------------------------------
# Valid command passes all checks
# ---------------------------------------------------------------------------

class TestValidCommandPasses:
    def test_typical_command_passes(self) -> None:
        def my_cmd(self, user: str, count: int = 1): ...
        _validate_command(
            "my_cmd",
            "A normal command that does something useful.",
            func=my_cmd,
            choices={"count": [1, 2, 3]},
        )

    def test_no_optional_args_passes(self) -> None:
        _validate_command("ping", "Pong!")
