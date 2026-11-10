import inspect
import logging
import time

from ..core.callables import call_flexibly

logger = logging.getLogger(__name__)


async def refresh_widget_data(widgets):
    """Call the data providers that are due; return True if any widget's data changed."""
    now = time.time()
    changed = False

    for widget in widgets:
        provider = widget.data_provider
        if provider is None or now - widget._last_data_update < widget.refresh_interval:
            continue

        widget._last_data_update = now
        try:
            new_data = call_flexibly(provider, ((widget,), {}), ((), {}))
            if inspect.isawaitable(new_data):
                new_data = await new_data
        except Exception as error:
            logger.warning("Failed to refresh %s widget %s: %s", widget.type, widget.id, error)
            continue

        if new_data != widget.data:
            widget.data = new_data
            changed = True

    return changed
