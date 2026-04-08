from dataclasses import dataclass
from typing import Final

from rtty_sdr.core.options import BaudotOptions, Shift

# Letter shift mapping
LTRS_Map: Final[dict[str, int]] = {
    "A": 3,
    "B": 25,
    "C": 14,
    "D": 9,
    "E": 1,
    "F": 13,
    "G": 26,
    "H": 20,
    "I": 6,
    "J": 11,
    "K": 15,
    "L": 18,
    "M": 28,
    "N": 12,
    "O": 24,
    "P": 22,
    "Q": 23,
    "R": 10,
    "S": 5,
    "T": 16,
    "U": 7,
    "V": 30,
    "W": 19,
    "X": 29,
    "Y": 21,
    "Z": 17,
    " ": 4,
    "\n": 2,
    "\r": 8,
}

LTRS_Map_rev: Final[dict[int, str]] = {value: key for key, value in LTRS_Map.items()}


# Figure shift mapping
FIGS_Map: Final[dict[str, int]] = {
    "-": 3,
    "?": 25,
    ":": 14,
    "$": 9,
    "3": 1,
    "!": 13,
    "&": 26,
    "#": 20,
    "8": 6,
    "4": 11,
    "(": 15,
    ")": 18,
    ".": 28,
    ",": 12,
    "9": 24,
    "0": 22,
    "1": 23,
    "'": 10,
    "5": 16,
    "7": 7,
    ";": 30,
    "2": 19,
    "/": 29,
    "6": 21,
    '"': 17,
    " ": 4,
    "\n": 2,
    "\r": 8,
}

FIGS_Map_rev: Final[dict[int, str]] = {value: key for key, value in FIGS_Map.items()}

BOTH_Map: Final[dict[str, int]] = {
    char: code for char, code in LTRS_Map.items() if char in FIGS_Map
}


@staticmethod
def validate_char(char: str, case_sensitive: bool = False) -> bool:
    """
    Return if the char is a valid Baudot character
    Args:
        char (str): The character to validate
        case_sensitive (bool): Whether or not to be case sensitive (default False)

    Returns:
        bool: If the character is valid Baudot

    """
    return get_mapped(char, case_sensitive) is not None


@dataclass
class MappedVal:
    """Represents the code and shift of a Baudot character

    Attributes:
        code (int): The baudot-code (0-31)
        shift (Shift): Either LTRS, FIGS, or None (if both)
    """

    code: int
    shift: Shift | None


@staticmethod
def get_mapped(char: str, case_sensitive: bool = False) -> MappedVal | None:
    """
    Get the mapping for the char
    Args:
        char:
        case_sensitive:

    Returns: A MappedVal or None if it isn't mappable

    """
    cased = char.upper() if not case_sensitive else char
    if val := BOTH_Map.get(cased):
        return MappedVal(val, None)
    elif val := LTRS_Map.get(cased):
        return MappedVal(val, Shift.LTRS)
    elif val := FIGS_Map.get(cased):
        return MappedVal(val, Shift.FIGS)
    else:
        return None


@staticmethod
def encode(
    msg: str, opts: BaudotOptions, initial_shift: Shift | None = None
) -> tuple[list[int], Shift]:
    """Baudot Encoder

    Args:
        msg:
        opts:
        initial_shift: This will override the opts.initial_shift (intended for use saving state between calls)

    Returns:
        0: The codes
        1: The new shift value

    Raises:
        ValueError: If characters aren't valid and opts.replace_invalid_with isn't specified to a valid character
    """
    replacement: MappedVal | None = None
    if opts.replace_invalid_with is not None:
        replacement = get_mapped(opts.replace_invalid_with)
        if replacement == None:
            raise ValueError(
                f"'{opts.replace_invalid_with}' is not a valid Baudot character"
            )

    mapped_values: list[MappedVal] = []
    for c in msg:
        maps_val = get_mapped(c)
        if maps_val is None:
            if replacement is None:
                raise ValueError(
                    f"{c} is not a valid Baudot character and `opts.replace_invalid_with` was None"
                )
            mapped_values.append(replacement)
        else:
            mapped_values.append(maps_val)

    ret: list[int] = []
    shift = initial_shift if initial_shift is not None else opts.initial_shift
    for mapped in mapped_values:
        # For None shift (either) just use previous shift
        if mapped.shift is not None and mapped.shift != shift:
            ret.extend([mapped.shift, mapped.code])
            shift = mapped.shift
        else:
            ret.append(mapped.code)
    return ret, shift


def decode(
    codes: list[int] | int, opts: BaudotOptions, shift: Shift | None = None
) -> tuple[str, Shift]:
    """Baudot Decoder

    Args:
        codes: the code/codes to decode
        opts:
        shift: overrides opts.initial_shift, intended for use saving state between calls

    Returns:
        0: decoded msg
        1: the new state

    Raises:
        ValueError: If a code is invalid (above 31)
    """
    if not isinstance(codes, list):
        codes = [codes]

    ret = ""
    shift = shift if shift is not None else opts.initial_shift
    for code in codes:
        if code in Shift:
            shift = Shift(code)
            continue

        if shift == Shift.LTRS and (val := LTRS_Map_rev.get(code)):
            ret += val
        elif shift == Shift.FIGS and (val := FIGS_Map_rev.get(code)):
            ret += val
        else:
            raise ValueError(f"Unknown code: {code}")
    return ret, shift
