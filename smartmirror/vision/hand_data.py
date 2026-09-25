from dataclasses import dataclass
from typing import List, Optional, Tuple

Landmark = Tuple[float, float, float]  # (x, y, z), x/y normalized to 0..1
Point2D = Tuple[float, float]  # (x, y), normalized to 0..1
BBox = Tuple[float, float, float, float]  # (x_min, y_min, x_max, y_max)

SIDES = ("left", "right")

# MediaPipe hand landmark indices used across the vision module.
WRIST = 0
THUMB_TIP = 4
INDEX_PIP, INDEX_TIP = 6, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP = 9, 10, 12
RING_PIP, RING_TIP = 14, 16
PINKY_PIP, PINKY_TIP = 18, 20


@dataclass
class HandData:
    is_raised: bool
    # Everything below is None when the hand is not detected.
    landmarks: Optional[List[Landmark]]
    palm_center: Optional[Point2D]
    bbox: Optional[BBox]

    @classmethod
    def empty(cls) -> "HandData":
        return cls(is_raised=False, landmarks=None, palm_center=None, bbox=None)

    @property
    def detected(self) -> bool:
        return self.landmarks is not None
