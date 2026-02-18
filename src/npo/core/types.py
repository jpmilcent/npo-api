from typing import Annotated

from pydantic import AfterValidator, EmailStr

from npo.core.config import backend_settings
from npo.core.i18n import _


def validate_password_complexity(v: str) -> str:
    """Validate password complexity requirements."""
    errors = []
    special_chars = '!@#$%^&*(),.?":{}|<>'
    min_len = backend_settings.password_min_length
    rules = [
        (
            lambda s: len(s) >= min_len,
            _("Password must be at least {min_length} characters long.").format(min_length=min_len),
        ),
        (
            lambda s: any(c.isupper() for c in s),
            _("Password must contain at least one uppercase letter."),
        ),
        (
            lambda s: any(c.islower() for c in s),
            _("Password must contain at least one lowercase letter."),
        ),
        (lambda s: any(c.isdigit() for c in s), _("Password must contain at least one digit.")),
        (
            lambda s: any(c in special_chars for c in s),
            _("Password must contain at least one special character in : {special_chars}.").format(
                special_chars=special_chars
            ),
        ),
        (lambda s: " " not in s, _("Password must not contain spaces.")),
    ]

    for check, msg in rules:
        if not check(v):
            errors.append(msg)

    if errors:
        raise ValueError(" ".join(errors))

    return v


Password = Annotated[str, AfterValidator(validate_password_complexity)]


Email = Annotated[EmailStr, AfterValidator(lambda v: v.lower())]
