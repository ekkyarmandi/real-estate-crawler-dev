import re
from datetime import datetime as dt


class PreviousListing:
    def __init__(self, **kwargs):
        self.raw_data_id = kwargs.get("raw_data_id")
        self.price = kwargs.get("price")
        self.status = kwargs.get("status")
        self.valid_from = kwargs.get("valid_from")
        self.valid_to = kwargs.get("valid_to")
        self.short_description = kwargs.get("short_description")
        self.detail_description = kwargs.get("detail_description")
        self.validate_price()
        self.validate_valid_from()
        self.validate_valid_to()

    def validate_price(self):
        if self.price:
            try:
                self.price = round(float(self.price), 2)
            except (ValueError, TypeError):
                self.price = -1

    def validate_valid_from(self):
        if self.valid_from:
            date = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", self.valid_from)
            if date:
                date = dt.strptime(date.group(0), r"%Y-%m-%dT%H:%M:%S")
                self.valid_from = date.strftime(r"%Y-%m-%dT%H:%M:%S")
            else:
                self.valid_from = None
        else:
            self.valid_from = None

    def validate_valid_to(self):
        if self.valid_to:
            date = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", self.valid_to)
            if date:
                date = dt.strptime(date.group(0), r"%Y-%m-%dT%H:%M:%S")
                self.valid_to = date.strftime(r"%Y-%m-%dT%H:%M:%S")
            else:
                self.valid_to = None
        else:
            self.valid_to = None
