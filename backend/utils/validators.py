from collections.abc import Mapping


def string_value(values: Mapping[str, object], key: str) -> str:
    value = values.get(key)
    return value if isinstance(value, str) else ""


def is_valid_email(email: object) -> bool:
    if not isinstance(email, str) or email != email.strip() or any(
        character.isspace() for character in email
    ):
        return False
    if email.count("@") != 1:
        return False
    local, _, domain = email.partition("@")
    return bool(
        local
        and domain
        and "." in domain
        and not domain.startswith(".")
        and not domain.endswith(".")
    )


def is_valid_password(password: object, minimum_length: int = 8) -> bool:
    return isinstance(password, str) and len(password) >= minimum_length


def is_valid_profile(name: object, email: object) -> bool:
    return isinstance(name, str) and bool(name.strip()) and is_valid_email(email)


def is_valid_card_number(card_number: object) -> bool:
    return (
        isinstance(card_number, str)
        and len(card_number) == 16
        and card_number.isdigit()
    )


def is_valid_expiration_date(expiration_date: object) -> bool:
    if (
        not isinstance(expiration_date, str)
        or len(expiration_date) != 5
        or expiration_date[2] != "/"
        or not expiration_date[:2].isdigit()
        or not expiration_date[3:].isdigit()
    ):
        return False
    month, year = map(int, expiration_date.split("/"))
    return 1 <= month <= 12 and 0 <= year <= 99


def is_valid_cvv(cvv: object) -> bool:
    return isinstance(cvv, str) and len(cvv) == 3 and cvv.isdigit()
