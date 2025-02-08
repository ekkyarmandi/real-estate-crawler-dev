import re
from datetime import datetime as dt


class PreviousListing:
    def __init__(self, **kwargs):
        self.raw_data_id = kwargs.get("raw_data_id")
        self.price = kwargs.get("price")
        self.status = kwargs.get("status")
        self.short_description = kwargs.get("short_description")
        self.detail_description = kwargs.get("detail_description")
        self.validate_price()

    def validate_price(self):
        if self.price:
            if isinstance(self.price, str) and not re.search(r"\d+", self.price):
                self.price = -1
            else:
                try:
                    self.price = round(float(self.price), 2)
                except (ValueError, TypeError):
                    self.price = -1
