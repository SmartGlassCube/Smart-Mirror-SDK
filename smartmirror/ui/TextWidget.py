class TextWidget:
    def __init__(self, position=None, gestures=None, content=None):
        self.type = "text"
        self.position = position or {}
        self.gestures = gestures or []
        self.content = content

    def serialize(self):
        return {
            "type": self.type,
            "position": self.position,
            "gestures": [g.serialize() for g in self.gestures],
            "content": self.content,
        }
