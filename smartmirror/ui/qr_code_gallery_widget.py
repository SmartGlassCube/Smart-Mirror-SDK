class QRCodeGalleryWidget:
    def __init__(self, position=None, gestures=None, content=None, data=None, data_provider=None, refresh_interval=300):
        self.type = "qr_gallery"
        self.position = position or {}
        self.gestures = gestures or []
        self.content = content
        self.data = data
        self.data_provider = data_provider
        self.refresh_interval = refresh_interval
        self._last_data_update = 0.0

    def serialize(self):
        return {
            "type": self.type,
            "position": self.position,
            "gestures": [g.serialize() for g in self.gestures if hasattr(g, "serialize")],
            "content": self.content,
            "data": self.data,
        }
