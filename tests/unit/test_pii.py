from inbox_agent.pii import find_pii, redact


def test_detects_card_ssn_bank():
    text = (
        "Card 4111 1111 1111 1111, SSN 123-45-6789, routing 021000021 and "
        "account number 123456789012 for the deposit."
    )
    found = find_pii(text)
    assert any("4111" in f for f in found)
    assert "123-45-6789" in found
    assert any("123456789012" in f for f in found)
    red = redact(text)
    assert "4111" not in red and "123-45-6789" not in red and "123456789012" not in red


def test_ignores_emails_prices_and_listing_data():
    text = (
        "Hi, I'm maya.chen@example.com. Is 42 Oak St still $489,000 with a $285 HOA? "
        "Zip 97999, 1850 sqft, built 2004. Call 503-555-0142."
    )
    assert find_pii(text) == []
