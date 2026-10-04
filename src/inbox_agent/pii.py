"""PII detection and redaction (FR-018).

Card numbers, SSNs, and bank account numbers are redacted before they reach the model, in tool
results, and in model output. The sender's email address is deliberately *not* redacted: the
agent needs it for contact lookup and booking.
"""

from __future__ import annotations

import re

from langchain.agents.middleware import PIIMiddleware

SSN_PATTERN = r"\b\d{3}-\d{2}-\d{4}\b"
# Account/routing numbers: 8–17 digits near a banking keyword (keeps prices and zips out).
BANK_PATTERN = r"(?i)(?:account|acct|routing|aba|iban|bank)[^\d\n]{0,20}(\d[\d -]{6,20}\d)"
CARD_PATTERN = r"\b(?:\d[ -]?){13,19}\b"

_ssn = re.compile(SSN_PATTERN)
_bank = re.compile(BANK_PATTERN)
_card = re.compile(CARD_PATTERN)


def _luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _find_cards(text: str) -> list[str]:
    out = []
    for m in _card.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            out.append(m.group().strip())
    return out


def find_pii(text: str) -> list[str]:
    """Return sensitive substrings found in text (used by evaluators)."""
    if not text:
        return []
    found = _find_cards(text)
    found += [m.group() for m in _ssn.finditer(text)]
    found += [m.group(1) for m in _bank.finditer(text)]
    return found


def _detect_ssn(content: str):
    return [
        {"value": m.group(), "start": m.start(), "end": m.end(), "type": "ssn"}
        for m in _ssn.finditer(content)
    ]


def _detect_bank(content: str):
    return [
        {"value": m.group(1), "start": m.start(1), "end": m.end(1), "type": "bank_account"}
        for m in _bank.finditer(content)
    ]


def build_pii_middleware() -> list[PIIMiddleware]:
    flags = dict(apply_to_input=True, apply_to_output=True, apply_to_tool_results=True)
    return [
        PIIMiddleware("credit_card", strategy="redact", **flags),
        PIIMiddleware("ssn", detector=_detect_ssn, strategy="redact", **flags),
        PIIMiddleware("bank_account", detector=_detect_bank, strategy="redact", **flags),
    ]


def redact(text: str) -> str:
    text = _ssn.sub("[REDACTED_SSN]", text)
    text = _bank.sub(lambda m: m.group(0).replace(m.group(1), "[REDACTED_BANK_ACCOUNT]"), text)
    for card in _find_cards(text):
        text = text.replace(card, "[REDACTED_CREDIT_CARD]")
    return text


def trace_anonymizer():
    """Anonymizer for the LangSmith client so raw PII is not stored in traces."""
    from langsmith.anonymizer import create_anonymizer

    def _replace(text: str, path=None) -> str:  # signature accepted by create_anonymizer
        return redact(text)

    return create_anonymizer(_replace)
