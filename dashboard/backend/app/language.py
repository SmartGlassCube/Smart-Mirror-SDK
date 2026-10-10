"""Non-blocking English check for long text fields (langdetect, skip strings < 20 chars)."""

from langdetect import LangDetectException, detect

MIN_LENGTH = 20


def english_warnings(fields: dict) -> list[str]:
    """fields: {field_name: text}. Returns warning strings for fields that don't look like English."""
    warnings = []
    for name, text in fields.items():
        if not text or len(text) < MIN_LENGTH:
            continue
        try:
            language = detect(text)
        except LangDetectException:
            continue
        if language != "en":
            warnings.append(f"Field '{name}' doesn't look like English (detected: {language}).")
    return warnings
