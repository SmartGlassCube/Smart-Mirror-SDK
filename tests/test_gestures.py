from hands import hands, make_hand

from smartmirror.core import StateManager
from smartmirror.vision import (
    Gesture,
    GestureDetector,
    GestureEvent,
    PinchGesture,
    SwipeGesture,
    TwoFingersSwipeGesture,
    default_gesture_set,
)
from smartmirror.widgets import TextWidget


def run(detector, frames, start=0.0, step=0.03):
    """Feed `frames` (dicts of hands) and return the event names per frame."""
    return [
        [event.name for event in detector.process_hands(frame, timestamp=start + i * step)["events"]]
        for i, frame in enumerate(frames)
    ]


def flatten(per_frame):
    return [name for names in per_frame for name in names]


def test_pinch_lifecycle_reports_movement():
    detector = GestureDetector(gestures=[PinchGesture()])
    frames = [
        hands(right=make_hand(0.5, 0.5, pinch=True)),
        hands(right=make_hand(0.55, 0.5, pinch=True)),
        hands(right=make_hand(0.55, 0.5)),
    ]

    results = [detector.process_hands(frame, timestamp=i * 0.03)["events"] for i, frame in enumerate(frames)]

    assert [[e.name for e in r] for r in results] == [["pinch_start"], ["pinch_move"], ["pinch_end"]]
    assert abs(results[1][0].data["dx"] - 0.05) < 1e-9


def test_open_hand_swipe_is_mirrored_and_suppresses_return_motion():
    detector = GestureDetector(gestures=[SwipeGesture()])
    still = [hands(right=make_hand(0.8, 0.5))] * 6
    moving_left = [hands(right=make_hand(0.8 - 0.03 * i, 0.5)) for i in range(1, 8)]
    moving_back = [hands(right=make_hand(0.59 + 0.03 * i, 0.5)) for i in range(1, 8)]

    events = flatten(run(detector, still + moving_left + moving_back))

    # Moving toward screen-left in the mirrored frame is a "right" swipe; the
    # immediate return motion falls inside the cooldown and is ignored.
    assert events == ["swipe_right"]


def test_two_fingers_swipe_requires_its_posture():
    two_fingers = ("index", "middle")
    detector = GestureDetector(gestures=[SwipeGesture(), TwoFingersSwipeGesture()])
    frames = [hands(left=make_hand(0.3, 0.5, fingers_up=two_fingers))] * 6 + [
        hands(left=make_hand(0.3 + 0.03 * i, 0.5, fingers_up=two_fingers)) for i in range(1, 8)
    ]

    assert flatten(run(detector, frames)) == ["two_fingers_swipe_left"]


class FistGesture(Gesture):
    """A custom gesture emitting a custom event name, no enum edits needed."""

    name = "fist"

    def __init__(self):
        self._was_fist = False

    def detect(self, context):
        is_fist = context.signals["hand_count"] == 1 and not any(
            context.signals[finger][side]
            for finger in ("index_up", "middle_up", "ring_up", "pinky_up")
            for side in ("left", "right")
        )
        fired = is_fist and not self._was_fist
        self._was_fist = is_fist
        return [GestureEvent(type="fist", hand="right")] if fired else []


def test_custom_gesture_drives_page_navigation():
    detector = GestureDetector(gestures=default_gesture_set() + [FistGesture()])
    graph = {
        "nodes": [{"id": "home", "widgets": [TextWidget(content="hi")]}, {"id": "menu", "widgets": []}],
        "edges": [{"from": "home", "to": "menu", "gesture": "fist"}],
    }
    state = StateManager(graph=graph)

    result = detector.process_hands(hands(right=make_hand(fingers_up=())), timestamp=0.0)

    assert [event.name for event in result["events"]] == ["fist"]
    assert state.handle_gesture_events(result["events"], timestamp=0.0)
    assert state.current_node_id == "menu"
