from app.text.verify import estimate_tokens, normalize, verify

PAGES = [
    "Error E21 means the water did not drain. Clean the drain pump filter every month.",
    "To level the washer, turn the front feet. Use a spirit level on the lid.",
]
Q = "Clean the drain pump filter every month"


def test_exact_quote():
    v = verify("Clean the drain pump filter.", Q, PAGES, 1, 92)
    assert (v.ok, v.page, v.score, v.reason) == (True, 1, 100.0, "ok")


def test_wrong_cited_page_still_found():
    v = verify("Clean the drain pump filter.", Q, PAGES, 2, 92)
    assert v.ok and v.page == 1


def test_paraphrase_rejected():
    v = verify("Clean it.", "wash the pump screen monthly", PAGES, 1, 92)
    assert not v.ok and v.reason == "quote_not_found"


def test_number_must_be_in_quote():
    assert verify("Every 30 days.", Q, PAGES, 1, 92).reason == "number_not_in_quote"


def test_short_quote():
    assert verify("Clean it.", "drain pump", PAGES, 1, 92).reason == "quote_too_short"


def test_curly_quotes_and_dashes():
    pages = ["Don’t overload the drum — max 8 kg."]
    v = verify("8 kg max.", "Don't overload the drum - max 8 kg", pages, 1, 92)
    assert v.ok


def test_null_answer():
    assert verify(None, None, PAGES, None, 92).reason == "no_answer"


def test_thousands_separator_matches():
    pages = ["The study counted 1,101 tumors in the sample group."]
    v = verify("About 1101 tumors.", "counted 1,101 tumors in the sample", pages, 1, 92)
    assert v.ok


def test_normalize_and_tokens():
    assert normalize("  It’s  “A” – B\n") == "it's \"a\" - b"
    assert estimate_tokens("a b c d e f g h i j") == 13
