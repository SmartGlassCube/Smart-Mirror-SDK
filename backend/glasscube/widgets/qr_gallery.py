from .base import BaseWidget


class QRGalleryWidget(BaseWidget):
    """QR codes by category. Expects `data = {"categories": {name: [{"title", "imageUrl", "url"}]}}`."""

    type = "qr_gallery"
