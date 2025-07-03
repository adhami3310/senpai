"""Welcome to Reflex! This file outlines the steps to create a basic app."""

from __future__ import annotations

import base64
import dataclasses
import enum
import pickle
import secrets
from typing import Any

from cryptography.hazmat.primitives.asymmetric import rsa
from reflex_qrcode import QRCode

import reflex as rx
from reflex.vars.base import Var

from .qreader import qrcode_reader

RSA_KEY_SIZE = 1024


def serialize(alice_likes_bob: bool, certificate: int) -> int:
    """Serialize the data."""
    secret_padding = secrets.token_bytes(32)
    return int.from_bytes(
        secret_padding
        + alice_likes_bob.to_bytes(1, "big")
        + certificate.to_bytes(32, "big"),
        "big",
    )


def deserialize(serialized_value: int) -> tuple[bool, int]:
    """Deserialize the data."""
    data = serialized_value.to_bytes(65, "big")
    _secret_padding = data[:32]
    alice_likes_bob = bool(data[32])
    certificate = int.from_bytes(data[33:], "big")
    return alice_likes_bob, certificate


@dataclasses.dataclass(frozen=True)
class AliceInitialState:
    """The private data of Alice."""

    N: int
    d: int
    e: int
    certificate: int
    x: int
    y: int

    @staticmethod
    def generate(alice_likes_bob: bool):
        """Generate the initial state."""
        key = rsa.generate_private_key(public_exponent=65537, key_size=RSA_KEY_SIZE)
        private_key = key.private_numbers()
        public_key = key.public_key().public_numbers()
        certificate = secrets.randbits(256)
        return AliceInitialState(
            public_key.n,
            private_key.d,
            public_key.e,
            certificate,
            serialize(False, certificate),
            serialize(alice_likes_bob, certificate),
        )


@dataclasses.dataclass(frozen=True)
class AliceWelcome:
    """The public data of Alice."""

    N: int
    e: int
    xe: int
    ye: int


@dataclasses.dataclass(frozen=True)
class BobInitialState:
    """The private data of Bob."""

    r: int


@dataclasses.dataclass(frozen=True)
class BobWelcomeBack:
    """The public data of Bob."""

    zere: int


@dataclasses.dataclass(frozen=True)
class AliceCalculation:
    """The private data of Alice."""

    zr: int


@dataclasses.dataclass(frozen=True)
class Result:
    """The public data of Bob."""

    s: int | None


@dataclasses.dataclass(frozen=True)
class AliceConfirmation:
    """The private data of Alice."""

    x: int


@dataclasses.dataclass
class AliceState:
    """The state of Alice."""

    like_bob: bool = False
    initial: AliceInitialState = dataclasses.field(
        default_factory=lambda: AliceInitialState.generate(False)
    )
    locked_initial: bool = False
    bob_welcome: BobWelcomeBack | None = None
    result: Result | None = None

    def calculate_welcome(self) -> AliceWelcome:
        """Calculate the welcome."""
        return AliceWelcome(
            self.initial.N,
            self.initial.e,
            pow(self.initial.x, self.initial.e, self.initial.N),
            pow(self.initial.y, self.initial.e, self.initial.N),
        )

    def alice_calculation(self) -> AliceCalculation:
        """Calculate the calculation."""
        if self.bob_welcome is None:
            msg = "Bob's welcome is not available"
            raise ValueError(msg)
        return AliceCalculation(
            pow(
                self.bob_welcome.zere,
                self.initial.d,
                self.initial.N,
            )
        )


@dataclasses.dataclass
class BobState:
    """The state of Bob."""

    like_alice: bool
    initial: BobInitialState
    locked_initial: bool = False
    alice_welcome: AliceWelcome | None = None
    alice_calculation: AliceCalculation | None = None
    alice_confirmation: AliceConfirmation | None = None

    def calculate_welcome_back(self, bob_likes_alice: bool) -> BobWelcomeBack:
        """Calculate the welcome back."""
        if self.alice_welcome is None:
            msg = "Alice's welcome is not available"
            raise ValueError(msg)
        return BobWelcomeBack(
            (
                pow(
                    self.initial.r,
                    self.alice_welcome.e,
                    self.alice_welcome.N,
                )
                * (self.alice_welcome.ye if bob_likes_alice else self.alice_welcome.xe)
            )
            % self.alice_welcome.N
        )

    def calculate_result(self) -> Result:
        """Calculate the result."""
        if self.alice_welcome is None:
            msg = "Alice's welcome is not available"
            raise ValueError(msg)
        if self.alice_calculation is None:
            msg = "Alice's calculation is not available"
            raise ValueError(msg)
        z = (
            self.alice_calculation.zr
            * pow(
                self.initial.r,
                -1,
                self.alice_welcome.N,
            )
        ) % self.alice_welcome.N

        like_each_other, certificate = deserialize(z)

        return Result(None) if like_each_other else Result(certificate)


ENCODING_SCHEME = "ascii"


def send_to_network(data: Any) -> str:
    """Send data to the network."""
    return base64.b64encode(pickle.dumps(data)).decode(ENCODING_SCHEME, errors="ignore")


def receive_from_network(data: str) -> Any:
    """Receive data from the network."""
    return pickle.loads(
        base64.decodebytes(data.encode(ENCODING_SCHEME, errors="ignore"))
    )


class Compatability(enum.Enum):
    """The compatability of the two users."""

    LIKE = "LIKE"
    DISLIKE = "DISLIKE"


class Identity(enum.Enum):
    """The identity of the user."""

    ALICE = "Alice"
    BOB = "Bob"


class State(rx.State):
    """The app state."""

    identity: Identity | None = None
    _alice_state: AliceState | None = None
    _bob_state: BobState | None = None

    @rx.event
    def switch(self) -> None:
        """Switch the current user."""
        self.identity = (
            Identity.ALICE if self.identity == Identity.BOB else Identity.BOB
        )

        if self.is_alice:
            self._alice_state = AliceState()
            self._bob_state = None
        else:
            self._alice_state = None
            self._bob_state = None

    @rx.event
    def set_alice(self) -> None:
        """Set the user as Alice."""
        self.identity = Identity.ALICE
        self._alice_state = AliceState()
        self._bob_state = None

    @rx.event
    def set_bob(self) -> None:
        """Set the user as Bob."""
        self.identity = Identity.BOB
        self._alice_state = None
        self._bob_state = BobState(False, BobInitialState(secrets.randbits(256)))

    @rx.event
    def reset_state(self) -> None:
        """Reset the state."""
        self.identity = None
        self._alice_state = None
        self._bob_state = None

    @rx.var
    def alice_welcome(self) -> str | None:
        """The welcome of Alice."""
        if (
            self.identity == Identity.ALICE
            and self._alice_state
            and self._alice_state.bob_welcome is None
            and self._alice_state.locked_initial
        ):
            return send_to_network(self._alice_state.calculate_welcome())
        return None

    @rx.var
    def bob_welcome_back(self) -> str | None:
        """The welcome back of Bob."""
        if (
            self.identity == Identity.BOB
            and self._bob_state
            and self._bob_state.alice_calculation is None
            and self._bob_state.locked_initial
        ):
            return send_to_network(
                self._bob_state.calculate_welcome_back(self._bob_state.like_alice)
            )
        return None

    @rx.var
    def waiting_for_lock(self) -> bool:
        """Whether the user has not locked in their like status."""
        return self.identity is not None and (
            (
                self.identity == Identity.ALICE
                and self._alice_state is not None
                and not self._alice_state.locked_initial
            )
            or (
                self.identity == Identity.BOB
                and self._bob_state is not None
                and self._bob_state.alice_welcome is not None
                and not self._bob_state.locked_initial
            )
        )

    @rx.var
    def alice_calculation(self) -> str | None:
        """The calculation of Alice."""
        if (
            self.identity == Identity.ALICE
            and self._alice_state
            and self._alice_state.bob_welcome is not None
        ):
            return send_to_network(self._alice_state.alice_calculation())
        return None

    @rx.var
    def result(self) -> Compatability | str | None:
        """The result of the calculation."""
        if (
            self.identity == Identity.BOB
            and self._bob_state
            and self._bob_state.alice_calculation is not None
        ):
            result = self._bob_state.calculate_result()
            return Compatability.LIKE if result.s is None else send_to_network(result)
        return None

    @rx.var
    def alice_confirmation(self) -> str | None:
        """The confirmation of Alice."""
        if (
            self.identity == Identity.ALICE
            and self._alice_state is not None
            and self._alice_state.result is not None
            and self._alice_state.result.s is not None
        ):
            if self._alice_state.result.s != self._alice_state.initial.certificate:
                return "INVALID"
            return send_to_network(AliceConfirmation(self._alice_state.initial.x))
        return None

    @rx.var
    def alice_was_faithful(self) -> str | None:
        """Whether Alice was faithful."""
        if (
            self.identity == Identity.BOB
            and self._bob_state is not None
            and self._bob_state.alice_confirmation is not None
            and self._bob_state.alice_welcome is not None
        ):
            if (
                pow(
                    self._bob_state.alice_confirmation.x,
                    self._bob_state.alice_welcome.e,
                    self._bob_state.alice_welcome.N,
                )
                == self._bob_state.alice_welcome.xe
            ):
                return "FAITHFUL"
            return "UNFAITHFUL"
        return None

    @rx.event
    def handle_alice_welcome_upload(self, text: str):
        """Handle the uploaded file."""
        if (
            self.identity != Identity.BOB
            or self._bob_state is None
            or self._bob_state.alice_welcome is not None
            or not text
        ):
            return None

        alice_welcome = receive_from_network(text)

        if not isinstance(alice_welcome, AliceWelcome):
            return rx.toast("Invalid QR code")

        self._bob_state = dataclasses.replace(
            self._bob_state,
            alice_welcome=alice_welcome,
        )
        return None

    @rx.event
    def handle_bob_welcome_back_upload(self, text: str):
        """Handle the uploaded file."""
        if (
            self.identity != Identity.ALICE
            or self._alice_state is None
            or self._alice_state.bob_welcome is not None
            or not text
        ):
            return None

        bob_welcome_back = receive_from_network(text)

        if not isinstance(bob_welcome_back, BobWelcomeBack):
            return rx.toast("Invalid QR code")

        self._alice_state = dataclasses.replace(
            self._alice_state,
            bob_welcome=bob_welcome_back,
        )
        return None

    @rx.event
    def handle_alice_calculation(self, text: str):
        """Handle the uploaded file."""
        if (
            self.identity != Identity.BOB
            or self._bob_state is None
            or self._bob_state.alice_calculation is not None
            or not text
        ):
            return None

        alice_calculation = receive_from_network(text)

        if not isinstance(alice_calculation, AliceCalculation):
            return rx.toast("Invalid QR code")

        self._bob_state = dataclasses.replace(
            self._bob_state,
            alice_calculation=alice_calculation,
        )
        return None

    @rx.event
    def handle_bob_result(self, text: str):
        """Handle the uploaded file."""
        if (
            self.identity != Identity.ALICE
            or self._alice_state is None
            or self._alice_state.result is not None
            or not text
        ):
            return None

        result = receive_from_network(text)

        if not isinstance(result, Result):
            return rx.toast("Invalid QR code")

        self._alice_state = dataclasses.replace(
            self._alice_state,
            result=result,
        )
        return None

    @rx.event
    def handle_alice_confirmation(self, text: str):
        """Handle the uploaded file."""
        if (
            self.identity != Identity.BOB
            or self._bob_state is None
            or self._bob_state.alice_confirmation is not None
            or not text
        ):
            return None

        alice_confirmation = receive_from_network(text)

        if not isinstance(alice_confirmation, AliceConfirmation):
            return rx.toast("Invalid QR code")

        self._bob_state = dataclasses.replace(
            self._bob_state,
            alice_confirmation=alice_confirmation,
        )
        return None

    @rx.event
    def lock_in(self, like_other: bool) -> None:
        """Toggle the like status of Bob."""
        if self.identity == Identity.ALICE and self._alice_state:
            self._alice_state = AliceState(
                like_bob=like_other,
                initial=AliceInitialState.generate(like_other),
                locked_initial=True,
            )
        elif self.identity == Identity.BOB and self._bob_state:
            self._bob_state = BobState(
                like_alice=like_other,
                initial=self._bob_state.initial,
                alice_welcome=self._bob_state.alice_welcome,
                locked_initial=True,
            )


def qr_code(value: Var[str]) -> rx.Component:
    """A QR code component."""
    return rx.box(
        QRCode(
            title=rx.Var.create("Alice's Welcome"),
            value=value,
            size=rx.Var.create(512),
            style=rx.Style(
                width="100%",
                height="auto",
            ),
        ),
        padding="1rem",
        background_color="white",
    )


def you_are(who: str) -> rx.Component:
    """A heading to show who the user is."""
    return rx.hstack(
        rx.heading(f"You are {who}", align="center"),
        rx.button("Reset?", on_click=State.reset_state),
        justify="between",
        width="100%",
    )


def upload_form(id: str, on_drop: Any) -> rx.Component:
    """A form to upload files."""
    return qrcode_reader(
        fps=10,
        on_read=on_drop,
        style=rx.Style(
            width="100%",
            height="auto",
        ),
    )


def alice_ui() -> rx.Component:
    """The UI for Alice."""
    return rx.fragment(
        you_are("Alice"),
        rx.cond(
            State.alice_confirmation,
            rx.box(
                rx.cond(
                    State.alice_confirmation == "INVALID",
                    rx.text("Invalid certificate! Bob was unfaithful!"),
                    rx.vstack(
                        rx.text(
                            "Bob was faithful! So sad that you don't like each other!"
                        ),
                        qr_code(State.alice_confirmation.to(str)),
                    ),
                ),
            ),
            rx.cond(
                State.alice_calculation,
                rx.vstack(
                    "Show this to Bob! They can unencrypt the value to get the certificate and the result!",
                    qr_code(State.alice_calculation.to(str)),
                    upload_form("bob_result", State.handle_bob_result),
                ),
                rx.cond(
                    State.alice_welcome,
                    rx.fragment(
                        rx.vstack(
                            "Show this to Bob! This is your modulus, public exponent, and two encrypted values",
                            rx.cond(
                                State.alice_welcome,
                                qr_code(State.alice_welcome.to(str)),
                            ),
                        ),
                        upload_form(
                            "bob_welcome_back", State.handle_bob_welcome_back_upload
                        ),
                    ),
                    rx.fragment(
                        "Do you like Bob?",
                        rx.hstack(
                            rx.button(
                                "Yes",
                                on_click=State.lock_in(True),
                            ),
                            rx.button(
                                "No",
                                on_click=State.lock_in(False),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def bob_ui() -> rx.Component:
    """The UI for Bob."""
    return rx.fragment(
        you_are("Bob"),
        rx.cond(
            State.alice_was_faithful,
            rx.cond(
                State.alice_was_faithful == "FAITHFUL",
                rx.heading(
                    "Alice was faithful! So sad that you don't like each other!",
                    align="center",
                ),
                rx.heading(
                    "Alice was unfaithful! You both dislike each other now! Congratulations!",
                    align="center",
                ),
            ),
            rx.cond(
                State.result,
                rx.box(
                    "Result: ",
                    rx.cond(
                        State.result == Compatability.LIKE,
                        rx.heading(
                            "You both like each other! Congratulations!",
                            align="center",
                        ),
                        rx.vstack(
                            "You don't like each other :( Here is the certificate, show this to Alice to prove it!",
                            qr_code(State.result.to(str)),
                            upload_form(
                                "alice_confirmation", State.handle_alice_confirmation
                            ),
                        ),
                    ),
                ),
                rx.cond(
                    State.bob_welcome_back,
                    rx.fragment(
                        rx.vstack(
                            "Show this to Alice! This is your decision, encrypted with her public key",
                            qr_code(State.bob_welcome_back.to(str)),
                        ),
                        upload_form(
                            "alice_calculation", State.handle_alice_calculation
                        ),
                    ),
                    rx.cond(
                        State.waiting_for_lock,
                        rx.fragment(
                            "Do you like Alice?",
                            rx.hstack(
                                rx.button(
                                    "Yes",
                                    on_click=State.lock_in(True),
                                ),
                                rx.button(
                                    "No",
                                    on_click=State.lock_in(False),
                                ),
                            ),
                        ),
                        upload_form("alice_welcome", State.handle_alice_welcome_upload),
                    ),
                ),
            ),
        ),
    )


def index() -> rx.Component:
    """The main page of the app."""
    return rx.container(
        rx.vstack(
            rx.match(
                State.identity,
                (Identity.ALICE, alice_ui()),
                (Identity.BOB, bob_ui()),
                rx.fragment(
                    rx.heading("Senpai Protocol", align="center", width="100%"),
                    rx.hstack(
                        rx.button("Alice", on_click=State.set_alice),
                        rx.button("Bob", on_click=State.set_bob),
                        justify="center",
                        width="100%",
                    ),
                ),
            ),
        ),
    )


app = rx.App(theme=rx.theme(accent_color="gray"))
app.add_page(index)
