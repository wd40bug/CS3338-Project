from rtty_sdr.core.baudot import BaudotEncoder, Shift
import pytest

def test_baudot_shift_logic():
    # Start in LTRS
    encoder = BaudotEncoder(Shift.LTRS)

    # 'A' (LTRS) -> '3' (FIGS) -> 'E' (LTRS)
    result = encoder.encode("A3E")
    assert result == [3, 27, 1, 31, 1]


def test_baudot_invalid_replacement():
    encoder = BaudotEncoder(Shift.LTRS)
    # Accessing the mangled class name for the test

    # '@' is invalid, should be replaced by Space (4)
    result = encoder.encode("A@B", replace_invalid_with=" ")
    assert result == [3, 4, 25]


def test_exclamation():
    encoder = BaudotEncoder()
    ret = encoder.encode("!")
    assert ret == [27, 13]


def test_baudot_exception():
    encoder = BaudotEncoder(Shift.LTRS)

    with pytest.raises(ValueError):
        encoder.encode("~")

