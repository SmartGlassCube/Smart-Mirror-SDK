class WeatherWidget:
    def __init__(self, position=None, gestures=None):
        self.type = "weather"
        self.position = position or {}
        self.gestures = gestures or []

    def serialize(self):
        return {
            "type": self.type,
            "position": self.position,
            "gestures": [g.serialize() for g in self.gestures],
        }