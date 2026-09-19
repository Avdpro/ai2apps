"""Shared account password policy for Local request validation."""

from typing import Annotated

from pydantic import AfterValidator, SecretStr

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
PASSWORD_SCHEMA = {
    "minLength": PASSWORD_MIN_LENGTH,
    "maxLength": PASSWORD_MAX_LENGTH,
    "description": (
        "Must contain 8 to 128 UTF-8 bytes; minLength and maxLength are client "
        "hints and Local enforces encoded byte length"
    ),
}


def validate_password(value: str | SecretStr):
    """Validate the Cloud password contract without retaining plaintext."""

    plaintext = value.get_secret_value() if isinstance(value, SecretStr) else value
    byte_length = len(plaintext.encode("utf-8"))
    if not PASSWORD_MIN_LENGTH <= byte_length <= PASSWORD_MAX_LENGTH:
        raise ValueError("password must contain 8 to 128 UTF-8 bytes")
    return value


Password = Annotated[str, AfterValidator(validate_password)]
SecretPassword = Annotated[SecretStr, AfterValidator(validate_password)]
