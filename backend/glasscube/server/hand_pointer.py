from typing import Optional

from ..vision.hand_data import INDEX_TIP, THUMB_TIP


class HandPointer:
    """Streams one hand's index fingertip, and whether it pinches, to the frontend's cursor.

    Uses `signals["pointer_position"]`: the same 0..1 screen fractions the StateManager
    compares against widget positions, so the cursor shows exactly what a pinch would target.
    While the hand pinches (the drawing page's pen is down), the position is the point
    between the thumb and index tips instead: it stays put while the fingers open to let
    go, where the fingertip alone would trail off and leave a hook at the stroke's end.
    """

    def __init__(self, hand: str = "right", precision: int = 4):
        self.hand = hand
        self.precision = precision
        self._last = (None, False)  # (position, pinching) last sent; starts as "no hand"

    def message(self, signals: dict, hands: Optional[dict] = None) -> Optional[dict]:
        """Call for every processed frame (`hands` = the detector's `hands`); returns a
        `POINTER` message when the position or the pinch changed."""
        point = signals["pointer_position"][self.hand]
        pinching = point is not None and bool(signals["pinching"][self.hand])
        if pinching and hands is not None:
            point = _between_thumb_and_index(hands[self.hand]) or point
        position = None if point is None else {
            "x": round(point[0], self.precision),
            "y": round(point[1], self.precision),
        }
        if (position, pinching) == self._last:
            return None
        self._last = (position, pinching)
        return {"type": "POINTER", "position": position, "pinching": pinching}


def _between_thumb_and_index(hand):
    if not hand.landmarks:
        return None
    thumb, index = hand.landmarks[THUMB_TIP], hand.landmarks[INDEX_TIP]
    return ((thumb[0] + index[0]) / 2, (thumb[1] + index[1]) / 2)
