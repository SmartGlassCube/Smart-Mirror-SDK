from typing import Dict, List, Union

from .base_widget import BaseWidget


class TextWidget(BaseWidget):
    def __init__(self, position=None, gestures=None, content=None, data=None, data_provider=None, refresh_interval=300):
        super().__init__(
            widget_type="text",
            position=position,
            gestures=gestures,
            content=content,
            data=data,
            data_provider=data_provider,
            refresh_interval=refresh_interval,
        )

        self._source: Union[str, List[str], Dict[str, List[str]]] = ""
        self._content_mode = "string"
        self._keys = []
        self._key_index = 0
        self._item_index = 0

        self._set_source(content)
        self._normalize_content_model()
        self._sync_content_from_indices()

    def _set_source(self, content):
        if content is None:
            self._source = ""
            return
        self._source = content

    def _normalize_content_model(self):
        if isinstance(self._source, dict):
            normalized = {
                key: [str(item) for item in value]
                for key, value in self._source.items()
                if isinstance(value, list) and value
            }
            if normalized:
                self._source = normalized
                self._content_mode = "dict"
                self._keys = list(normalized.keys())
                return

        if isinstance(self._source, list):
            normalized = [str(item) for item in self._source if str(item).strip() != ""]
            if normalized:
                self._source = normalized
                self._content_mode = "list"
                return

        self._source = str(self._source)
        self._content_mode = "string"

    def _dict_source(self):
        return self._source if isinstance(self._source, dict) else {}

    def _list_source(self):
        return self._source if isinstance(self._source, list) else []

    def _sync_content_from_indices(self):
        if self._content_mode == "dict":
            active_key = self._keys[self._key_index]
            items = self._dict_source().get(active_key, [])
            if not items:
                self.content = ""
                return
            self._item_index %= len(items)
            self.content = items[self._item_index]
            return

        if self._content_mode == "list":
            list_source = self._list_source()
            if not list_source:
                self.content = ""
                return
            self._item_index %= len(list_source)
            self.content = list_source[self._item_index]
            return

        self.content = self._source

    def apply_navigation(self, horizontal_steps=0, vertical_steps=0):
        if self._content_mode == "string":
            return False

        changed = False

        if self._content_mode == "dict" and vertical_steps:
            previous_key_index = self._key_index
            self._key_index = (self._key_index + vertical_steps) % len(self._keys)
            if self._key_index != previous_key_index:
                self._item_index = 0
                changed = True

        if horizontal_steps:
            if self._content_mode == "dict":
                active_key = self._keys[self._key_index]
                active_items = self._dict_source().get(active_key, [])
                if active_items:
                    previous_item_index = self._item_index
                    self._item_index = (self._item_index + horizontal_steps) % len(active_items)
                    changed = changed or (self._item_index != previous_item_index)
            elif self._content_mode == "list":
                list_source = self._list_source()
                if not list_source:
                    return changed
                previous_item_index = self._item_index
                self._item_index = (self._item_index + horizontal_steps) % len(list_source)
                changed = changed or (self._item_index != previous_item_index)

        if changed:
            self._sync_content_from_indices()
            self.metadata = self._build_metadata()
        return changed

    def _build_metadata(self):
        metadata = {
            "contentMode": self._content_mode,
            "itemIndex": self._item_index,
        }

        if self._content_mode == "dict":
            active_key = self._keys[self._key_index]
            metadata.update(
                {
                    "keyIndex": self._key_index,
                    "key": active_key,
                    "keys": self._keys,
                    "activeItemCount": len(self._dict_source().get(active_key, [])),
                }
            )
        elif self._content_mode == "list":
            metadata.update({"activeItemCount": len(self._list_source())})

        return metadata

    def serialize(self):
        self.metadata = self._build_metadata()
        return super().serialize()
