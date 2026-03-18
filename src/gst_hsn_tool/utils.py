import re


def normalize_text(value: str) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_hsn_digits(value: str) -> str:
    if value is None:
        return ""
    digits = re.sub(r"\D", "", str(value))
    return digits
