from hands import hands, make_hand

from smartmirror.server.hand_pointer import HandPointer
from smartmirror.vision import GestureDetector


def test_pointer_follows_one_hand_and_only_sends_changes():
    detector = GestureDetector(gestures=[])
    pointer = HandPointer(hand="right")

    def message(**hand_kwargs):
        return pointer.message(detector.process_hands(hands(**hand_kwargs), timestamp=0)["signals"])

    assert message() is None  # no hand yet, nothing to clear
    # make_hand puts the index fingertip at (x - 0.03, y - 0.1)
    assert message(right=make_hand(0.3, 0.6)) == {"type": "POINTER", "position": {"x": 0.27, "y": 0.5}}
    assert message(right=make_hand(0.3, 0.6)) is None  # unchanged
    assert message(left=make_hand(0.7, 0.5)) == {"type": "POINTER", "position": None}  # left hand ignored
