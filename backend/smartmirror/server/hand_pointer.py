from typing import Optional


class HandPointer:
    """Streams one hand's index fingertip to the frontend's cursor.

    Uses `signals["pointer_position"]`: the same 0..1 screen fractions the StateManager
    compares against widget positions, so the cursor shows exactly what a pinch would target.
    """

    def __init__(self, hand: str = "right", precision: int = 4):
        self.hand = hand
        self.precision = precision
        self._last = None

    def message(self, signals: dict) -> Optional[dict]:
        """Call for every processed frame; returns a `POINTER` message when the position changed."""
        point = signals["pointer_position"][self.hand]
        position = None if point is None else {
            "x": round(point[0], self.precision),
            "y": round(point[1], self.precision),
        }
        if position == self._last:
            return None
        self._last = position
        return {"type": "POINTER", "position": position}
