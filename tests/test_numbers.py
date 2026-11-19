from app.numbers import first_int, numbers_in


def test_first_int_word():
    assert first_int("There are four mugs") == 4


def test_first_int_digits_first():
    assert first_int("12 mugs, maybe 13") == 12


def test_first_int_none():
    assert first_int("none visible") is None


def test_numbers_in_digits():
    assert numbers_in("every 30 days or 2.5 weeks") == {"30", "2.5"}


def test_numbers_in_word():
    assert numbers_in("four times") == {"4"}


def test_numbers_in_thousands_separator():
    assert numbers_in("1,101") == {"1101"}
    assert numbers_in("1101") == {"1101"}
    assert numbers_in("1,101 and 2,500,000") == {"1101", "2500000"}


def test_numbers_in_list_comma_is_not_separator():
    assert numbers_in("1, 2 and 3") == {"1", "2", "3"}
