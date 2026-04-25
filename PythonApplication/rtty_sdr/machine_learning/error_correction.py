from copy import replace
import multiprocessing
import queue
import random
import threading
import os
from loguru import logger

from rtty_sdr.comms.messages import FinalMessage, ReceivedMessage, Settings, Shutdown
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.core.baudot import (
    decode,
    LTRS_Map,
    FIGS_Map,
    Shift,
    LTRS_Map_rev,
    FIGS_Map_rev,
    validate_code,
)
from rtty_sdr.core.options import RTTYOpts, Shift, SystemOpts
from rtty_sdr.core.protocol import RecvMessage
from rtty_sdr.machine_learning.model import SRUModel
import torch
import os

LTRS = [
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "I",
    "J",
    "K",
    "L",
    "M",
    "N",
    "O",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
    "Z",
    "\r",
    " ",
    "\n",
    "FIGS",
    "LTRS",
    "<PAD>",
    "<MASK>",
]  # LTRS for RTTY transmission

FIGS = [
    "-",
    "?",
    ":",
    "$",
    "3",
    "!",
    "&",
    "#",
    "8",
    "4",
    "(",
    ")",
    ".",
    ",",
    "9",
    "0",
    "1",
    "'",
    "5",
    "7",
    ";",
    "2",
    "/",
    "6",
    '"',
    "\n",
    " ",
    "\r",
    "FIGS",
    "LTRS",
    "<PAD>",
    "<MASK>",
]  # FIGS for RTTY transmission

RTTY_Chars = list(
    dict.fromkeys(LTRS + FIGS)
)  # all unique characters in LTRS and FIGS, needed for tokenizer
PAD_TOKEN = RTTY_Chars.index("<PAD>")  # index for padding token, needed for collate_fn

LTRS_Bin = [
    "00011",
    "11001",
    "01110",
    "01001",
    "00001",
    "01101",
    "11010",
    "10100",
    "00110",
    "01011",
    "01111",
    "10010",
    "11100",
    "01100",
    "11000",
    "10110",
    "10111",
    "01010",
    "00101",
    "10000",
    "00111",
    "11110",
    "10011",
    "11101",
    "10101",
    "10001",
    "00010",
    "00100",
    "01000",
    "11011",
    "11111",
]

FIGS_Bin = [
    "00011",
    "11001",
    "01110",
    "01001",
    "00001",
    "01101",
    "11010",
    "10100",
    "00110",
    "01011",
    "01111",
    "10010",
    "11100",
    "01100",
    "11000",
    "10110",
    "10111",
    "01010",
    "10000",
    "00111",
    "11110",
    "10011",
    "11101",
    "10101",
    "10001",
    "00010",
    "00100",
    "01000",
    "11011",
    "11111",
]

LTRS_TO_BIN = {
    char: b for char, b in zip(LTRS, LTRS_Bin)
}  # dictionary to convert LTRS characters to binary strings for bit flips
FIGS_TO_BIN = {
    char: b for char, b in zip(FIGS, FIGS_Bin)
}  # dictionary to convert FIGS characters to binary strings for bit flips
CHAR_TO_BIN = {
    **LTRS_TO_BIN,
    **FIGS_TO_BIN,
}  # combine dictionaries (unpacking) to convert all RTTY characters to binary strings for bit flips
LTRS_BIN_TO_CHAR = {
    b: char for char, b in zip(LTRS, LTRS_Bin)
}  # dictionary to convert binary strings back to LTRS characters after bit flips
FIGS_BIN_TO_CHAR = {
    b: char for char, b in zip(FIGS, FIGS_Bin)
}  # dictionary to convert binary strings back to FIGS characters after bit flips

CHAR_TO_CODE = {**LTRS_Map, **FIGS_Map}
CODE_TO_CHAR = {v: k for k, v in CHAR_TO_CODE.items()}

MAX_LEN = 255


def run_inference(model, tokens, PAD_TOKEN):
    with torch.no_grad():
        out = model(tokens)
        preds = out.argmax(-1).squeeze(0).tolist()
    return [p for p in preds if p != PAD_TOKEN]


def pad_tokens(tokens: list[int]) -> list[int]:
    if len(tokens) > MAX_LEN:
        return tokens[:MAX_LEN]
    return tokens + [PAD_TOKEN] * (MAX_LEN - len(tokens))


def tokens_to_codes_with_shift(pred_tokens, inv_tokenizer, initial_shift):
    codes = []
    shift = initial_shift

    for t in pred_tokens:
        char = inv_tokenizer.get(t)

        if char in {"<PAD>", "<MASK>", None}:
            continue

        if char == "LTRS":
            if shift != Shift.LTRS:
                shift = Shift.LTRS
                codes.append(int(Shift.LTRS))
            continue

        elif char == "FIGS":
            if shift != Shift.FIGS:
                shift = Shift.FIGS
                codes.append(int(Shift.FIGS))
            continue

        # Map character to code
        if shift == Shift.LTRS:
            code = LTRS_Map.get(char)
            if code is None:
                code = FIGS_Map.get(char)  # fallback
        else:
            code = FIGS_Map.get(char)
            if code is None:
                code = LTRS_Map.get(char)  # fallback

        if code is not None:
            codes.append(code)

    return codes


def codes_to_tokens_with_shift(codes, tokenizer, initial_shift):
    tokens = []
    shift = initial_shift

    for code in codes:
        # Handle shift codes directly
        if code == int(Shift.LTRS) or code == int(Shift.FIGS):
            shift = Shift(code)
            tokens.append(tokenizer[shift.name])  # "LTRS" or "FIGS"
            continue

        # Decode based on current shift
        if shift == Shift.LTRS:
            char = LTRS_Map_rev.get(code)
        else:
            char = FIGS_Map_rev.get(code)

        if char is None:
            char = "<MASK>"

        tokens.append(tokenizer[char] if char in tokenizer else tokenizer["<MASK>"])

    return tokens


def error_correction(in_codes: list[int], model, initial_shift, debug=False):
    # Find invalid codes (0) and replaces with one of the closest valid characters (one bit flipped)
    in_codes = [
        code if validate_code(code) else 1 << random.randint(0, RTTYOpts.data_bits)
        for code in in_codes
    ]
    tokenizer = {c: i for i, c in enumerate(RTTY_Chars)}
    inv_tokenizer = {i: c for c, i in tokenizer.items()}

    tokens = codes_to_tokens_with_shift(in_codes, tokenizer, initial_shift)
    padded_tokens = pad_tokens(tokens)

    pred_tokens = run_inference(
        model=model,
        tokens=torch.tensor(padded_tokens).unsqueeze(0),
        PAD_TOKEN=tokenizer["<PAD>"],
    )

    out_codes = tokens_to_codes_with_shift(pred_tokens, inv_tokenizer, initial_shift)

    if debug:
        logger.debug(
            f"\n"
            f"RAW CODES:     {in_codes[:50]}\n"
            f"TOKENS IN:     {[inv_tokenizer[t] for t in tokens[:50]]}\n"
            f"TOKENS PADDED: {[inv_tokenizer[t] for t in padded_tokens[:50]]}\n"
            f"TOKENS OUT:    {[inv_tokenizer[t] for t in pred_tokens[:50]]}\n"
            f"CODES OUT:     {out_codes[:50]}\n"
        )

    return out_codes


# NEWER IMPLEMENTATION
class ErrorCorrection(multiprocessing.Process):
    def __init__(self, initial_settings: SystemOpts):
        super().__init__()
        self.__opts = initial_settings
        self.__pubsub: PubSub | None = None
        self.ai_model = None

    def load_model(self):
        if self.ai_model is None:
            embedding_dim = 128
            hidden_dim = 256
            dropout = 0.0
            num_layers = 3
            bidirectional = True
            vocab_size = len(RTTY_Chars)

            self.ai_model = SRUModel(
                vocab_size,
                embedding_dim=embedding_dim,
                hidden_dim=hidden_dim,
                num_layers=num_layers,
                dropout=dropout,
                bidirectional=bidirectional,
            )

            model_path = os.path.join(os.path.dirname(__file__), "256_SRU_7268.pt")
            self.ai_model.load_state_dict(torch.load(model_path, map_location="cpu"))
            self.ai_model.to("cpu")
            self.ai_model.eval()

    def run(self):
        self.__pubsub = PubSub(module_name="Error Correction")
        self.ai_model = self.load_model()

        msg_queue: queue.Queue[RecvMessage] = queue.Queue()
        stop_event: threading.Event = threading.Event()

        def on_settings_change(msg: Settings):
            self.__opts = msg.settings

        def on_shutdown(_: Shutdown):
            stop_event.set()
            return "stop"

        def on_recv(msg: ReceivedMessage):
            msg_queue.put(msg.msg)

        self.__pubsub.subscribe(Settings, on_settings_change)
        self.__pubsub.subscribe(Shutdown, on_shutdown)
        self.__pubsub.subscribe(ReceivedMessage, on_recv)

        self.__pubsub.run_receive()
        self.load_model()

        while not stop_event.is_set():
            try:
                msg = msg_queue.get(timeout=0.1)
                logger.debug(f"Processing message: {msg}")

                if msg.valid_checksum or not self.__opts.error_correction:
                    self.__pubsub.publish(FinalMessage(msg))
                    continue

                msg_codes = msg.codes[
                    msg.msg_start_idx : msg.msg_start_idx + msg.msg_codes_len
                ]
                recovered_codes = error_correction(
                    msg_codes,
                    self.ai_model,
                    self.__opts.baudot.initial_shift,
                    debug=True,
                )
                target_len = msg.msg_codes_len

                if len(recovered_codes) > target_len:
                    recovered_codes = recovered_codes[:target_len]
                elif len(recovered_codes) < target_len:
                    recovered_codes += msg_codes[len(recovered_codes) :]

                corrected_codes = msg.codes
                corrected_codes[
                    msg.msg_start_idx : msg.msg_start_idx + msg.msg_codes_len
                ] = recovered_codes
                decode_baudot_opts = replace(
                    self.__opts.baudot, replace_invalid_with="�"
                )
                corrected_msg, _ = decode(recovered_codes, decode_baudot_opts)

                corrected = RecvMessage.create(
                    corrected_msg,
                    msg.callsign,
                    corrected_codes,
                    msg.msg_codes_len,
                    msg.checksum,
                    received_codes=msg.codes,
                )

                self.__pubsub.publish(FinalMessage(corrected))

            except queue.Empty:
                continue

        logger.info("Shutting down Error Correction")
