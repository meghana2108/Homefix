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


EQ = "Error E21 means the water did not drain"


def test_wrong_code_refused():
    assert verify("Use E22.", EQ, PAGES, 1, 92).reason == "code_not_in_quote"


def test_code_in_quote_ok():
    assert verify("E21 means it did not drain.", EQ, PAGES, 1, 92).ok


def test_code_invented_refused():
    v = verify("It needs a 9V battery.", Q, PAGES, 1, 92)
    assert v.reason == "code_not_in_quote"


def test_code_case_insensitive():
    v = verify("Error E21 shows when it can't drain.", "error e21 means the water did not drain",
               PAGES, 1, 92)
    assert v.ok


UP = ["Plug the washer into a 230 V outlet. Use a 5mm hex key on the feet.",
      "Plug the washer into a 230V outlet."]


def test_unit_glued_answer_spaced_quote():
    assert verify("Use a 230V outlet.", "Plug the washer into a 230 V outlet", UP, 1, 92).ok


def test_unit_spaced_answer_glued_quote():
    assert verify("Use a 230 V outlet.", "Plug the washer into a 230V outlet", UP, 2, 92).ok


def test_mm_spacing():
    assert verify("Use a 5 mm hex key.", "Use a 5mm hex key on the feet", UP, 1, 92).ok


def test_wrong_size_refused():
    assert not verify("Use a 6mm hex key.", "Use a 5mm hex key on the feet", UP, 1, 92).ok


def test_plain_number_still_checked():
    v = verify("There are 4 mugs.", Q, PAGES, 1, 92)
    assert v.reason == "number_not_in_quote"


def test_ordinal_refused():
    assert not verify("The 2nd foot.", "turn the front feet", PAGES, 2, 92).ok


def test_or_is_not_a_unit():
    v = verify("Clean it 2 or 3 times a month.", "Clean it 2 to 3 times a month",
               ["Clean it 2 to 3 times a month."], 1, 92)
    assert v.ok


def test_in_is_not_a_unit():
    v = verify("Use 3 in the slot.", "put 3 in the slot", ["Then put 3 in the slot."], 1, 92)
    assert v.ok


def test_article_a_is_not_amps():
    v = verify("Buy 2 a week.", "Buy 2 every week", ["Buy 2 every week or so."], 1, 92)
    assert v.ok


def test_degree_sign_ignored():
    pages = ["Set it to 40 °C for cotton."]
    assert verify("Set it to 40 C.", "Set it to 40 °C", pages, 1, 92).ok
    assert not verify("Set it to 60 C.", "Set it to 40 °C", pages, 1, 92).ok


FUSE = ["Use a 10A fuse in the plug.", "Use a 10 A fuse in the plug."]


def test_amps_spaced_answer_glued_quote():
    assert verify("Fit a 10 A fuse.", "Use a 10A fuse", FUSE, 1, 92).ok


def test_amps_glued_answer_spaced_quote():
    assert verify("Fit a 10A fuse.", "Use a 10 A fuse", FUSE, 2, 92).ok


def test_wrong_amps_refused():
    assert not verify("Fit a 15 A fuse.", "Use a 10A fuse", FUSE, 1, 92).ok


QPAGES = [
    "Error E21 means the water did not drain. Clean the drain pump filter.",
    "The programme was not finished properly. Restart the programme.",
]


def test_question_code_not_in_quote():
    v = verify("The programme did not finish.", "The programme was not finished properly", QPAGES, 2, 92,
               question="What does error code E21 mean?")
    assert not v.ok and v.reason == "question_code_not_in_quote"


def test_question_code_in_quote_ok():
    v = verify("The water did not drain.", "Error E21 means the water did not drain", QPAGES, 1, 92,
               question="What does error code E21 mean?")
    assert v.ok


def test_quote_not_in_pages_with_question():
    v = verify("Check it.", "my washer won't drain", QPAGES, 1, 92, question="Why won't my washer drain?")
    assert not v.ok


def test_quote_echoes_question():
    pages = ["The washer won't drain. Clean the filter."]
    v = verify("Clean it.", "The washer won't drain.", pages, 1, 92,
               question="The washer won't drain. What do I do?")
    assert not v.ok and v.reason == "quote_from_question"


def test_short_quote_no_fuzzy():
    v = verify("Clean it.", "Clean the drain pump hose", QPAGES, 1, 92)
    assert not v.ok and v.reason == "quote_not_found"


def test_long_quote_typo_still_fuzzy():
    pages = ["Remove the detergent drawer and rinse it under running water every month to stop build up."]
    v = verify("Rinse it.", "Remove the detergent drawer and rinse it under runing water every month",
               pages, 1, 92)
    assert v.ok


def test_question_none_unchanged():
    assert verify("Clean it.", "Clean the drain pump filter", QPAGES, 1, 92, question=None).ok


def test_hyphen_code_in_question_not_in_quote():
    v = verify("The programme did not finish.", "The programme was not finished properly", QPAGES, 2, 92,
               question="What does E-21 mean?")
    assert not v.ok and v.reason == "question_code_not_in_quote"


def test_hyphen_code_matches_plain_code():
    v = verify("The water did not drain.", "Error E21 means the water did not drain", QPAGES, 1, 92,
               question="What does E-21 mean?")
    assert v.ok


def test_plain_question_code_matches_hyphen_quote():
    pages = ["Error F-05 shows a blocked pump. Clean it."]
    v = verify("The pump is blocked.", "Error F-05 shows a blocked pump", pages, 1, 92,
               question="What is F05?")
    assert v.ok


def test_nine_volt_is_not_a_code():
    from app.text.verify import codes_in
    assert codes_in("use a 9 volt battery") == set()
