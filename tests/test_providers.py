import pytest

from app.providers import (
    AssignmentNotPermitted,
    MockSeatProvider,
    OfficialSeatProvider,
    ProviderError,
    ProviderNotConfigured,
    SeatStatus,
    create_provider,
)


def test_mock_rooms_are_demo(provider):
    rooms = provider.list_rooms()
    assert len(rooms) >= 1
    assert all(r.is_demo and "DEMO" in r.name for r in rooms)
    for r in rooms:
        assert len(provider.get_seats(r.id)) == r.total_seats


def test_mock_seed_is_reproducible():
    a = MockSeatProvider(seed=42, auto_tick_seconds=None)
    b = MockSeatProvider(seed=42, auto_tick_seconds=None)
    assert [s.status for s in a.get_seats("demo-a")] == [s.status for s in b.get_seats("demo-a")]


def test_mock_tick_changes_some_seats():
    p = MockSeatProvider(seed=3, change_rate=1.0, auto_tick_seconds=None)
    before = [s.status for s in p.get_seats("demo-a")]
    p.tick()
    after = [s.status for s in p.get_seats("demo-a")]
    assert before != after


def test_mock_fail_next(provider):
    provider.fail_next = 1
    with pytest.raises(ProviderError):
        provider.get_seats("demo-a")
    provider.get_seats("demo-a")  # 다음은 정상


def test_mock_unknown_room(provider):
    with pytest.raises(KeyError):
        provider.get_seats("nope")


def test_mock_assign_only_available(provider):
    provider.set_status("demo-a", "1", SeatStatus.OCCUPIED)
    with pytest.raises(ValueError):
        provider.assign_seat("demo-a", "1")
    provider.set_status("demo-a", "1", SeatStatus.AVAILABLE)
    assert provider.assign_seat("demo-a", "1").status == SeatStatus.OCCUPIED


def test_official_provider_is_disabled():
    p = OfficialSeatProvider()
    assert not p.supports_assignment and not p.is_demo
    with pytest.raises(ProviderNotConfigured):
        p.list_rooms()
    with pytest.raises(ProviderNotConfigured):
        p.get_seats("x")
    with pytest.raises(AssignmentNotPermitted):
        p.assign_seat("x", "1")


def test_create_provider():
    assert isinstance(create_provider("official"), OfficialSeatProvider)
    assert isinstance(create_provider("mock"), MockSeatProvider)
