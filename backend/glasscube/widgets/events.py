from .base import BaseWidget


class EventsWidget(BaseWidget):
    """Cards for the club's events and projects.

    `items` is a list of `{"id", "name", "description", "image"}`; `image` is an optional
    image URL, cards without one show a placeholder. Serialized as `data = {"items": [...]}`,
    so a `data_provider` (e.g. a database query) returning that shape replaces the list.
    """

    type = "events"

    def __init__(self, items=None, **kwargs):
        super().__init__(**kwargs)
        self.data = {"items": list(items or [])}
