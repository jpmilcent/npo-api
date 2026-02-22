from unittest.mock import patch

import pytest

from npo.core.types import validate_password_complexity


def test_validate_password_complexity_error_messages():
    """
    Test password complexity validation error messages.
    """
    min_length = 5
    with patch("npo.core.types.backend_settings") as mock_settings:
        mock_settings.password_min_length = min_length

        # Too short password
        too_short_pwd = "1aD|"
        with pytest.raises(ValueError, match=r"^Password") as exc_info:
            validate_password_complexity(too_short_pwd)
        assert str(exc_info.value) == f"Password must be at least {min_length} characters long."

        # Without lowercase letter
        without_lower_case_letter_pwd = "1ABC|"
        with pytest.raises(ValueError, match=r"^Password") as exc_info:
            validate_password_complexity(without_lower_case_letter_pwd)
        assert str(exc_info.value) == "Password must contain at least one lowercase letter."

        # Without uppercase letter
        without_upper_case_letter_pwd = "1abc|"
        with pytest.raises(ValueError, match=r"^Password") as exc_info:
            validate_password_complexity(without_upper_case_letter_pwd)
        assert str(exc_info.value) == "Password must contain at least one uppercase letter."

        # Without digit
        without_digit_pwd = "abCD|"
        with pytest.raises(ValueError, match=r"^Password") as exc_info:
            validate_password_complexity(without_digit_pwd)
        assert str(exc_info.value) == "Password must contain at least one digit."

        # Without special character
        special_chars = '!@#$%^&*(),.?":{}|<>'
        without_special_chars_pwd = "1abCD"
        with pytest.raises(ValueError, match=r"^Password") as exc_info:
            validate_password_complexity(without_special_chars_pwd)
        assert (
            str(exc_info.value)
            == f"Password must contain at least one special character in : {special_chars}."
        )

        # With space
        with_space_pwd = "1 bCD|"
        with pytest.raises(ValueError, match=r"^Password") as exc_info:
            validate_password_complexity(with_space_pwd)
        assert str(exc_info.value) == "Password must not contain spaces."

        # With several messages
        several_msg_pwd = "abc|"
        with pytest.raises(ValueError, match=r"^Password") as exc_info:
            validate_password_complexity(several_msg_pwd)
        assert str(exc_info.value) == (
            f"Password must be at least {min_length} characters long. "
            "Password must contain at least one uppercase letter. "
            "Password must contain at least one digit."
        )


def test_validate_password_complexity_ok():
    """
    Test password complexity validation success.
    """
    min_length = 5
    with patch("npo.core.types.backend_settings") as mock_settings:
        mock_settings.password_min_length = min_length

        # Too short password
        pwd_ok = "1abCD|"
        pwd_ok_output = validate_password_complexity(pwd_ok)
        assert pwd_ok_output == pwd_ok
