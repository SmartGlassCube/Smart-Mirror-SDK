from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List

from ..gesture_types import GestureEvent
from ..hand_data import HandData


@dataclass
class GestureContext:
    hands: Dict[str, HandData]
    signals: Dict[str, Any]
    timestamp: float


class Gesture(ABC):
    name = "gesture"

    @abstractmethod
    def detect(self, context: GestureContext) -> List[GestureEvent]:
        raise NotImplementedError

    def reset(self) -> None:
        return None


class StaticGesture(Gesture):
    pass


class DynamicGesture(Gesture):
    pass