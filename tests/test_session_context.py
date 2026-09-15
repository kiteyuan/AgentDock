"""Session context sliding window."""

from runtime.session.models import Session


def test_max_context_trims() -> None:
    s = Session(session_id="x", device_id="d", max_context=3)
    for i in range(5):
        s.add_turn("user", f"m{i}")
    assert len(s.context) == 3
    assert s.context[0]["text"] == "m2"
    assert s.context[-1]["text"] == "m4"


def test_max_context_unlimited() -> None:
    s = Session(session_id="x", device_id="d", max_context=0)
    for i in range(10):
        s.add_turn("user", f"m{i}")
    assert len(s.context) == 10
