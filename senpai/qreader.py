"""A simple wrapper around the html5-qrcode library."""

from typing import TypedDict

import reflex as rx
from reflex.event import EventType, passthrough_event_spec
from reflex.vars.base import Var


class Dimensions(TypedDict):
    """A simple type for dimensions."""

    width: int
    height: int


class QrcodeReader(rx.Component):
    """A simple wrapper around the html5-qrcode library."""

    library = "/public/html5-qrcode"

    tag = "Html5QrcodePlugin"

    lib_dependencies: list[str] = ["html5-qrcode"]

    fps: Var[int]

    qrbox: Var[int | Dimensions]

    disable_flip: Var[bool]

    qr_code_success_callback: rx.EventHandler[passthrough_event_spec(str)]


def qrcode_reader(
    fps: int | Var[int] = 10,
    disable_flip: bool | Var[bool] = False,
    qrbox: int | Var[int] | Dimensions | Var[Dimensions] | None = None,
    on_read: EventType[str] | EventType[()] | None = None,
    **kwargs,
) -> QrcodeReader:
    """Create a new QrcodeReader component."""
    return QrcodeReader.create(
        fps=fps,
        qrbox=qrbox,
        disable_flip=disable_flip,
        qr_code_success_callback=on_read,
        **kwargs,
    )
