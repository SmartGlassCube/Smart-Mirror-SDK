from .base import BaseWidget


class TextWidget(BaseWidget):
    """Text that can be navigated with the default swipe/scroll bindings.

    `content` can be:
      - a string: static text;
      - a list of strings: swipe left/right cycles items;
      - a dict of lists: swipe up/down (or scroll) changes section, left/right cycles items.
    """

    type = "text"

    def __init__(self, content=None, **kwargs):
        super().__init__(content=content, **kwargs)
        self._keys = []
        self._key_index = 0
        self._item_index = 0
        self._source = self._normalize(content)
        self._sync_content()

    def _normalize(self, content):
        if isinstance(content, dict):
            sections = {
                str(key): [str(item) for item in items]
                for key, items in content.items()
                if isinstance(items, list) and items
            }
            if sections:
                self._keys = list(sections)
                return sections

        if isinstance(content, list):
            items = [str(item) for item in content if str(item).strip()]
            if items:
                return items

        return "" if content is None else str(content)

    @property
    def content_mode(self) -> str:
        if isinstance(self._source, dict):
            return "dict"
        if isinstance(self._source, list):
            return "list"
        return "string"

    def _active_items(self):
        if isinstance(self._source, dict):
            return self._source[self._keys[self._key_index]]
        if isinstance(self._source, list):
            return self._source
        return []

    def _sync_content(self):
        items = self._active_items()
        self.content = items[self._item_index % len(items)] if items else self._source

    def apply_navigation(self, horizontal_steps=0, vertical_steps=0) -> bool:
        previous = (self._key_index, self._item_index)

        if vertical_steps and self._keys:
            self._key_index = (self._key_index + vertical_steps) % len(self._keys)
            if self._key_index != previous[0]:
                self._item_index = 0

        items = self._active_items()
        if horizontal_steps and items:
            self._item_index = (self._item_index + horizontal_steps) % len(items)

        changed = (self._key_index, self._item_index) != previous
        if changed:
            self._sync_content()
        return changed

    def serialize(self):
        serialized = super().serialize()
        navigation = {"contentMode": self.content_mode, "itemIndex": self._item_index}
        if self.content_mode != "string":
            navigation["activeItemCount"] = len(self._active_items())
        if self.content_mode == "dict":
            navigation.update(keyIndex=self._key_index, key=self._keys[self._key_index], keys=self._keys)
        serialized["metadata"] = {**self.metadata, **navigation}
        return serialized
