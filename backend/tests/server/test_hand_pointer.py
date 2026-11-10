from smartmirror.server.hand_pointer import HandPointer
from smartmirror.vision import GestureDetector
from tests.hands import hands, make_hand


def pointer_messages(pointer):
    detector = GestureDetector(gestures=[])

    def message(**hand_kwargs):
        result = detector.process_hands(hands(**hand_kwargs), timestamp=0)
        return pointer.message(result["signals"], result["hands"])

    return message


def test_pointer_follows_one_hand_and_only_sends_changes():
    message = pointer_messages(HandPointer(hand="right"))

    assert message() is None  # no hand yet, nothing to clear
    # make_hand puts the index fingertip at (x - 0.03, y - 0.1)
    assert message(right=make_hand(0.3, 0.6)) == {"type": "POINTER", "position": {"x": 0.27, "y": 0.5}, "pinching": False}
    assert message(right=make_hand(0.3, 0.6)) is None  # unchanged
    assert message(left=make_hand(0.7, 0.5)) == {"type": "POINTER", "position": None, "pinching": False}  # left hand ignored


def test_a_pinch_points_between_thumb_and_index_and_is_reported():
    message = pointer_messages(HandPointer(hand="right"))

    # make_hand(pinch=True) puts the thumb tip 0.01 left of the index tip (0.27, 0.5)
    assert message(right=make_hand(0.3, 0.6, pinch=True)) == {
        "type": "POINTER", "position": {"x": 0.265, "y": 0.5}, "pinching": True,
    }
    assert message(right=make_hand(0.3, 0.6)) == {"type": "POINTER", "position": {"x": 0.27, "y": 0.5}, "pinching": False}
