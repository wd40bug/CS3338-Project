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

LTRS_Map_rev: Final[dict[int, str]] = {
        value: key for key, value in LTRS_Map.items()
    }


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

FIGS_Map_rev: Final[dict[int, str]] = {
    value: key for key, value in FIGS_Map.items()
}

@staticmethod
def ValidateChar(char: str) -> bool:
    return get_mapped(char) is not None

@dataclass
class MappedVal:
    code: int
    shift: Shift

@staticmethod
def get_mapped(char: str) -> MappedVal | None:
    up = char.upper()
    if val := LTRS_Map.get(up):
        return MappedVal(val, Shift.LTRS)
    elif val := FIGS_Map.get(up):
        return MappedVal(val, Shift.FIGS)
    else:
        return None

@staticmethod
def encode(
    letters: str, opts: BaudotOptions, initial_shift: Shift | None = None
) -> tuple[list[int], Shift]:
    replacement: MappedVal | None = None
    if opts.replace_invalid_with is not None:
        replacement = get_mapped(opts.replace_invalid_with)
        if replacement == None:
            raise ValueError(
                f"'{opts.replace_invalid_with}' is not a valid Baudot character"
            )

    mapped_values: list[MappedVal] = []
    for c in letters:
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
        if mapped.shift != shift:
            ret.extend([mapped.shift, mapped.code])
            shift = mapped.shift
        else:
            ret.append(mapped.code)
    return ret, shift



def decode(codes: list[int] | int, opts: BaudotOptions, shift: Shift | None = None) -> tuple[str, Shift]:

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
