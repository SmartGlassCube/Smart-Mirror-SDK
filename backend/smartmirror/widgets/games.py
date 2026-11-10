from .base import BaseWidget


class GamesWidget(BaseWidget):
    """Grid of computer-vision game tiles.

    `games` is a list of `{"id", "title", "icon"}`; `icon` is an optional image URL,
    tiles without one show a placeholder. Serialized as `data = {"games": [...]}`.
    """

    type = "games"

    def __init__(self, games=None, **kwargs):
        super().__init__(**kwargs)
        self.data = {"games": list(games or [])}
