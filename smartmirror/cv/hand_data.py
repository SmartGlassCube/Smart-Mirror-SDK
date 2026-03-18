from dataclasses import dataclass
from typing import List, Tuple, Optional

Landmark = Tuple[float, float, float] #each landmark is (x,y,z)
Point2D = Tuple[float, float] #(x,y) coordinates of the palm center, can be used for gesture recognition and hand tracking
BBox = Tuple[float, float, float, float] #(x_min, y_min, x_max, y_max) coordinates of the bounding box around the hand, can be used for gesture recognition and hand tracking

@dataclass
class HandData:
    is_raised: bool #raised or not ?
    # all those are optional because no hand => nth else
    landmarks: Optional[List[Landmark]]
    palm_center: Optional[Point2D]
    bbox: Optional[BBox]