"""Widget data providers.

A data provider is any callable, sync or async, taking the widget (or nothing)
and returning the new `widget.data`. The server calls it every
`widget.refresh_interval` seconds.
"""

from .mongo_calendar import MongoCalendarProvider
from .open_meteo import OpenMeteoWeatherProvider
from .qr_catalog import QRCodeCatalogProvider

__all__ = ["MongoCalendarProvider", "OpenMeteoWeatherProvider", "QRCodeCatalogProvider"]
