from rtty_sdr.core.baudot import Shift, encode
import pytest

from rtty_sdr.core.options import BaudotOptions

def test_baudot_shift_logic():
    # Start in LTRS
    opts = BaudotOptions(initial_shift=Shift.LTRS)
    # 'A' (LTRS) -> '3' (FIGS) -> 'E' (LTRS)
    result, shift = encode("A3E", opts)
    assert result == [3, 27, 1, 31, 1]
    assert shift == Shift.LTRS


def test_baudot_invalid_replacement():
    opts = BaudotOptions(initial_shift=Shift.LTRS, replace_invalid_with=" ")
    # Accessing the mangled class name for the test

    # '@' is invalid, should be replaced by Space (4)
    result, shift = encode("5@B", opts)
    assert result == [27, 16, 4, 31, 25]
    assert shift == Shift.LTRS


def test_exclamation():
    opts = BaudotOptions(initial_shift=Shift.LTRS)
    ret, shift = encode("!", opts)
    assert ret == [27, 13]
    assert shift == Shift.FIGS


def test_baudot_exception():
    opts = BaudotOptions(initial_shift=Shift.LTRS)

    with pytest.raises(ValueError):
        encode("~", opts)

