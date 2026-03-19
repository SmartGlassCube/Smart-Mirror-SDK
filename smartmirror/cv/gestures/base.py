class StaticGesture:
    def detect(self, hand: list) -> bool:
        raise NotImplementedError


class DynamicGesture:
    def update(self, hands) -> str | None:
        raise NotImplementedError