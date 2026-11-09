from .base import (
    AssignmentNotPermitted,
    ProviderError,
    ProviderNotConfigured,
    Room,
    Seat,
    SeatProvider,
    SeatStatus,
)
from .mock import MockSeatProvider
from .official import OfficialSeatProvider


def create_provider(name: str, seed: int | None = None) -> SeatProvider:
    if name == "official":
        return OfficialSeatProvider()
    return MockSeatProvider(seed=seed)


__all__ = [
    "AssignmentNotPermitted",
    "MockSeatProvider",
    "OfficialSeatProvider",
    "ProviderError",
    "ProviderNotConfigured",
    "Room",
    "Seat",
    "SeatProvider",
    "SeatStatus",
    "create_provider",
]
