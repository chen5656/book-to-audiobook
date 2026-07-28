import re

CONTEXT_RADIUS = 40
_SENTENCE_END = (".", "!", "?")

_ACRONYM = re.compile(r"\b[A-Z]{2,}\b")
_NUMBER = re.compile(r"\b\d[\d.,]*\b")
_CAPITALIZED_WORD = re.compile(r"\b[A-ZÀ-Ý][a-zà-ÿ]{2,}\b")


def _is_mid_sentence(text: str, offset: int) -> bool:
    prefix = text[:offset].rstrip()
    if not prefix:
        return False
    return prefix[-1] not in _SENTENCE_END


def flag_risky_tokens(text: str) -> list:
    raw = []

    for match in _ACRONYM.finditer(text):
        raw.append(_build_flag(text, match, "acronym"))

    for match in _NUMBER.finditer(text):
        raw.append(_build_flag(text, match, "number"))

    for match in _CAPITALIZED_WORD.finditer(text):
        if _is_mid_sentence(text, match.start()):
            raw.append(_build_flag(text, match, "foreign_name"))

    raw.sort(key=lambda f: f["char_offset"])

    deduped = {}
    for flag in raw:
        key = (flag["token"], flag["reason"])
        if key not in deduped:
            deduped[key] = {**flag, "count": 1}
        else:
            deduped[key]["count"] += 1

    return sorted(deduped.values(), key=lambda f: f["char_offset"])


def _build_flag(text: str, match, reason: str) -> dict:
    offset = match.start()
    start = max(0, offset - CONTEXT_RADIUS)
    end = min(len(text), offset + CONTEXT_RADIUS)
    return {
        "token": match.group(0),
        "reason": reason,
        "char_offset": offset,
        "context": text[start:end],
    }