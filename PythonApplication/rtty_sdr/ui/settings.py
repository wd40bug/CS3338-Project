from typing import (
    Any,
    Iterable,
    Literal,
    Optional,
    Annotated,
    Final,
    TypeVar,
    assert_never,
)
from loguru import logger
from nicegui.defaults import DEFAULT_PROP
from nicegui.element import Element
from nicegui.elements.checkbox import Checkbox
from nicegui.elements.input import Input
from nicegui.elements.mixins.validation_element import ValidationDict
from nicegui.elements.number import Number
from nicegui.elements.select import Select
from pydantic import Field, BaseModel, ConfigDict

from rtty_sdr.comms.messages import Settings
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.core.options import Shift, SystemOpts
from nicegui import ui

T = TypeVar("T", bound=Element)


class SettingsCommon[T](BaseModel):
    name: str
    write_back: str
    input: T | None = None
    model_config = ConfigDict(arbitrary_types_allowed=True)


class NumberSetting(SettingsCommon[Number], BaseModel):
    is_int: bool = Field(default=False)
    kind: Literal["number"] = "number"
    min: Optional[float] = Field(default=None)
    max: Optional[float] = Field(default=None)


class String(SettingsCommon[Input], BaseModel):
    kind: Literal["string"] = "string"


class Selection(SettingsCommon[Select], BaseModel):
    selections: list[str] | dict[Any, str]
    kind: Literal["select"] = "select"


class CheckBox(SettingsCommon[Checkbox], BaseModel):
    kind: Literal["checkbox"] = "checkbox"


class Header(BaseModel):
    content: str
    kind: Literal["header"] = "header"


class Hidden(BaseModel):
    name: str
    children: list[SettingsRenders]
    kind: Literal["hidden"] = "hidden"


type SettingsRenders = Annotated[
    NumberSetting | String | Selection | CheckBox | Header | Hidden,
    Field(discriminator="kind"),
]


def setattr_nested(obj: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    setattr(obj, parts[-1], value)


def getattr_nested(obj: Any, path: str) -> Any:
    parts = path.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    return getattr(obj, parts[-1])


def hasattr_nested(obj: Any, path: str) -> bool:
    parts = path.split(".")
    for part in parts:
        if not hasattr(obj, part):
            return False
        obj = getattr(obj, part)
    return True


class SettingsMenu:
    render_list: Final[tuple[SettingsRenders, ...]] = (
        Header(content="General"),
        String(name="Callsign", write_back="callsign"),
        Selection(
            name="Engine",
            selections={"goertzel": "Goertzel", "envelope": "Envelope"},
            write_back="engine",
        ),
        Selection(
            name="Source",
            selections={"internal": "Debug", "microphone": "Microphone"},
            write_back="source",
        ),
        String(name="Port (empty for None)", write_back="port"),
        CheckBox(name="Error correction", write_back="error_correction"),
        NumberSetting(
            min=0,
            max=1,
            name="Corruption Probability (out of 1)",
            write_back="corruption",
        ),
        Header(content="RTTY"),
        NumberSetting(name="Baud", min=10, max=200, write_back="rtty.baud"),
        NumberSetting(
            name="Mark Frequency",
            min=50,
            max=23720,
            is_int=True,
            write_back="rtty.mark",
        ),
        NumberSetting(
            name="Shift", min=50, max=500, is_int=True, write_back="rtty.shift"
        ),
        NumberSetting(name="Stop Bits", min=1, max=2, write_back="rtty.stop_bits"),
        Hidden(
            name="Advanced RTTY Options",
            children=[
                NumberSetting(
                    name="Pre Message Stops",
                    min=0,
                    max=50,
                    is_int=True,
                    write_back="rtty.pre_msg_stops",
                ),
                NumberSetting(
                    name="Post Message Stops",
                    min=0,
                    max=50,
                    is_int=True,
                    write_back="rtty.post_msg_stops",
                ),
            ],
        ),
        Header(content="Signal"),
        NumberSetting(
            name="Fs", min=100, max=48440, is_int=True, write_back="signal.Fs"
        ),
        Header(content="Decode"),
        NumberSetting(
            name="Oversampling",
            min=1,
            max=10,
            is_int=True,
            write_back="decode.oversampling",
        ),
        Header(content="Baudot"),
        Selection(
            name="Initial Shift",
            selections={shift.value: shift.name for shift in Shift},
            write_back="baudot.initial_shift",
        ),
        Header(content="Goertzel"),
        NumberSetting(
            name="Overlap Ratio", min=0.125, max=2, write_back="goertzel.overlap_ratio"
        ),
        NumberSetting(
            name="DFT Length",
            min=128,
            max=2048,
            is_int=True,
            write_back="goertzel.dft_len",
        ),
        Header(content="Envelope"),
        NumberSetting(
            name="Order", is_int=True, min=2, max=50, write_back="envelope.order"
        ),
        NumberSetting(
            name="Envelope Order",
            is_int=True,
            min=2,
            max=50,
            write_back="envelope.envelopes_order",
        ),
        Header(content="Squelch"),
        NumberSetting(name="Lower Threshold", min=0, write_back="squelch.lower_thresh"),
        NumberSetting(name="Upper Threshold", min=0, write_back="squelch.upper_thresh"),
        NumberSetting(name="Order", min=1, is_int=True, write_back="squelch.order"),
        NumberSetting(
            name="Envelope Order",
            min=1,
            is_int=True,
            write_back="squelch.envelopes_order",
        ),
        NumberSetting(
            name="Bandwidth Safety Margin",
            min=0.125,
            write_back="squelch.bw_safety_margin",
        ),
        Header(content="Decode Strem"),
        NumberSetting(
            name="Squelch Grace Percent",
            min=0.125,
            max=1,
            write_back="stream.squelch_grace_percent",
        ),
        NumberSetting(name="Idle Bits", min=0, write_back="stream.idle_bits"),
        NumberSetting(name="None Friction", min=0, write_back="stream.none_friction"),
    )

    opts: SystemOpts

    def __init__(self, initial_settings: SystemOpts, pubsub: PubSub) -> None:
        self.opts = initial_settings
        self.__pubsub = pubsub

    def render(self) -> None:
        with ui.dialog() as dialog, ui.card().classes("min-w-[400px]"):
            ui.label("Settings").classes("text-h5 font-bold mb-4")

            def build_renderable(items: Iterable[SettingsRenders]):
                for renderable in items:
                    match renderable:
                        case Header(content=content):
                            ui.label(content).classes("text-h8 font-bold mb-0, pb-0")
                        case NumberSetting(
                            is_int=is_int,
                            min=min,
                            max=max,
                            name=name,
                            write_back=write_back,
                        ):
                            precision = 0 if is_int else None
                            step = 1 if is_int else None
                            elem = ui.number(
                                name,
                                min=min,
                                max=max,
                                precision=precision,
                                step=step,
                                value=getattr_nested(self.opts, write_back),
                            ).classes("w-full mb-0")
                            renderable.input = elem
                        case String(name=name, write_back=write_back):
                            elem = ui.input(
                                name,
                                value=getattr_nested(self.opts, write_back),
                            ).classes("w-full mb-0")
                            renderable.input = elem
                        case Selection(
                            name=name,
                            selections=selections,
                            write_back=write_back,
                        ):
                            renderable.input = ui.select(
                                selections,
                                label=name,
                                value=getattr_nested(self.opts, write_back),
                            ).classes("w-full mb-0")
                        case CheckBox(name=name, write_back=write_back):
                            renderable.input = ui.checkbox(
                                name, value=getattr_nested(self.opts, write_back)
                            ).classes("mb-0 w-full")
                        case Hidden(name=name, children=sub_items):
                            with ui.expansion(name).classes(
                                "w-full border rounded mt-2"
                            ):
                                build_renderable(sub_items)
                        case _:
                            assert_never(renderable)

            build_renderable(self.render_list)

            def apply_and_close() -> None:

                def gather_updates(items: Iterable[SettingsRenders]) -> dict[str, Any]:
                    proposed_changes: dict[str, Any] = {}
                    for render in items:
                        if isinstance(render, Hidden):
                            proposed_changes.update(gather_updates(render.children))
                        elif (
                            isinstance(render, SettingsCommon)
                            and render.input is not None
                        ):
                            proposed_changes[render.write_back] = (
                                render.input.value
                                if not isinstance(render, NumberSetting)
                                or not render.is_int
                                else int(render.input.value)
                            )
                    return proposed_changes

                proposed_changes = gather_updates(self.render_list)
                mark = proposed_changes.get(
                    "rtty.mark", getattr_nested(self.opts, "rtty.mark")
                )
                shift = proposed_changes.get(
                    "rtty.shift", getattr_nested(self.opts, "rtty.shift")
                )
                Fs = proposed_changes.get(
                    "signal.Fs", getattr_nested(self.opts, "signal.Fs")
                )

                # Nyquist
                if (mark + shift) > (Fs / 2):
                    ui.notify(
                        f"Validation Error: Mark ({mark}) + Shift ({shift}) must be ≤ Fs/2 ({Fs / 2})",
                        type="negative",
                        position="top",
                    )
                    return

                upper = proposed_changes.get(
                    "squelch.upper_thresh",
                    getattr_nested(self.opts, "squelch.upper_thresh"),
                )
                lower = proposed_changes.get(
                    "squelch.lower_thresh",
                    getattr_nested(self.opts, "squelch.lower_thresh"),
                )

                if lower > upper:
                    ui.notify(
                        f"Validation Error: Lower threshold ({lower}) must be ≤ Upper Threshold ({upper})"
                    )
                    return

                source = proposed_changes.get(
                    "source", getattr_nested(self.opts, "source")
                )
                port = proposed_changes.get("port", getattr_nested(self.opts, "port"))

                if source == "microphone" and port == "":
                    ui.notify(f"Validation Error: Source=microphone requires a port")
                    return

                for write_back, new_val in proposed_changes.items():
                    if not hasattr_nested(self.opts, write_back):
                        logger.error(f"SystemOpts has no attribute: {write_back}")
                    setattr_nested(self.opts, write_back, new_val)
                    logger.trace(f"Updated setting: {write_back}: {new_val}")
                dialog.close()
                self.__pubsub.publish(Settings(self.opts))

            with ui.row().classes("w-full justify-end mt-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat color=grey")
                ui.button("Apply", on_click=apply_and_close).props("color=primary")

        dialog.open()
