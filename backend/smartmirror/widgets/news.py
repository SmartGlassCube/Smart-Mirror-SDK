from .base import BaseWidget


class NewsWidget(BaseWidget):
    """News headline. Shows `content` when set, otherwise rotates the frontend's placeholder headlines."""

    type = "news"
