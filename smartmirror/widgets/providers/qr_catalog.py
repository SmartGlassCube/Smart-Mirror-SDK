class QRCodeCatalogProvider:
    def __init__(self, categories):
        self.categories = categories or {}

    def __call__(self, _widget=None):
        return {"categories": self.categories}
