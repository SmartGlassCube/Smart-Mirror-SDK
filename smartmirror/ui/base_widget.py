class BaseWidget:
    def __init__(
        self,
        widget_type,
        position=None,
        gestures=None,
        content=None,
        data=None,
        data_provider=None,
        refresh_interval=300,
        metadata=None,
    ):
        self.type = widget_type
        self.position = position or {}
        self.gestures = gestures or []
        self.content = content
        self.data = data
        self.data_provider = data_provider
        self.refresh_interval = refresh_interval
        self.metadata = metadata or {}
        self._last_data_update = 0.0
        self._is_dragging = False

    def handle_gesture(self, _event):
        return False

    def serialize(self):
        return {
            "type": self.type,
            "position": self.position,
            "gestures": [g.serialize() for g in self.gestures if hasattr(g, "serialize")],
            "content": self.content,
            "data": self.data,
            "metadata": self.metadata,
            "dragging": self._is_dragging,
        }

