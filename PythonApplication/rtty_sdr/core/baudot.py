from dataclasses import dataclass
from typing import Final
from enum import IntEnum


class Shift(IntEnum):
    LTRS = 31
    FIGS = 27


class BaudotEncoder:
    __state: Shift

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

    @staticmethod
    def ValidateChar(char: str) -> bool:
        return BaudotEncoder.__in_maps(char) is not None

    @dataclass
    class __MappedVal:
        code: int
        shift: Shift

    @staticmethod
    def __in_maps(char: str) -> BaudotEncoder.__MappedVal | None:
        up = char.upper()
        if val := BaudotEncoder.LTRS_Map.get(up):
            return BaudotEncoder.__MappedVal(val, Shift.LTRS)
        elif val := BaudotEncoder.FIGS_Map.get(up):
            return BaudotEncoder.__MappedVal(val, Shift.FIGS)
        else:
            return None

    def __init__(self, initial_shift: Shift = Shift.LTRS):
        self.__state = initial_shift
        pass

    def set_shift(self, new_shift: Shift):
        self.__state = new_shift

    def encode(
        self,
        letters: str,
        replace_invalid_with: None | str = None,
    ) -> list[int]:
        replacement: BaudotEncoder.__MappedVal | None = None
        if replace_invalid_with is not None:
            replacement = BaudotEncoder.__in_maps(replace_invalid_with)
            if replacement == None:
                raise ValueError(
                    f"'{replace_invalid_with}' is not a valid Baudot character"
                )

        mapped_values: list[BaudotEncoder.__MappedVal] = []
        for c in letters:
            maps_val = BaudotEncoder.__in_maps(c)
            if maps_val is None:
                if replacement is None:
                    raise ValueError(
                        f"{c} is not a valid Baudot character and `replace_invalid_with` was None"
                    )
                mapped_values.append(replacement)
            else:
                mapped_values.append(maps_val)

        ret: list[int] = []
        for mapped in mapped_values:
            if mapped.shift != self.__state:
                ret.extend([mapped.shift, mapped.code])
                self.__state = mapped.shift
            else:
                ret.append(mapped.code)
        return ret

class BaudotDecoder():
    __state: Shift

    # Reversed maps from BaudotEncoder
    LTRS_Map: Final[dict[int, str]] = {value: key for key,value in BaudotEncoder.LTRS_Map.items()}
    FIGS_Map: Final[dict[int, str]] = {value: key for key,value in BaudotEncoder.FIGS_Map.items()}

    def __init__(self, initial_shift: Shift) -> None:
        self.__state = initial_shift

    def set_shift(self, new_shift) -> None:
        self.__state = new_shift

    def decode(self, codes: list[int] | int) -> str:

        if isinstance(codes, int):
            codes = [codes]

        ret = ""
        for code in codes:
            if code in Shift:
                self.__state = Shift(code)
                continue
            
            if self.__state == Shift.LTRS and (val := BaudotDecoder.LTRS_Map.get(code)):
               ret += val 
            elif self.__state == Shift.FIGS and (val := BaudotDecoder.FIGS_Map.get(code)):
                ret += val
            else:
                raise ValueError(f"Unknown code: {code}")
        return ret
