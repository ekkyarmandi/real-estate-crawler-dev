class TestOutputStructurePipeline:
    REQUIRED_STRUCTURE = {
        "listing_id": str,
        "source_id": (str, type(None)),
        "title": (str, type(None)),
        "short_description": (str, type(None)),
        "detail_description": (str, type(None)),
        "price": (str, int, float, type(None)),
        "price_currency": (str, type(None)),
        "status": str,
        "valid_from": (str, type(None)),
        "valid_to": (str, type(None)),
        "total_views": (str, int, type(None)),
        "url": str,
        "raw_data": dict,
        "property": {
            "property_type": (str, type(None)),
            "building_type": (str, type(None)),
            "size_m2": (str, int, float, type(None)),
            "floor_number": (str, int, type(None)),
            "total_floors": (str, int, type(None)),
            "rooms": (str, int, type(None)),
            "property_state": (str, type(None)),
        },
        "address": {
            "city": (str, type(None)),
            "municipality": (str, type(None)),
            "micro_location": (str, type(None)),
            "latitude": (float, type(None)),
            "longitude": (float, type(None)),
        },
        "source": {
            "id": str,
            "name": str,
            "base_url": str,
        },
        "seller": {
            "source_seller_id": (str, int, type(None)),
            "name": (str, type(None)),
            "seller_type": (str, type(None)),
            "primary_phone": (str, type(None)),
            "primary_email": (str, type(None)),
            "website": (str, type(None)),
        },
        "images": list,
    }

    def _validate_structure(self, data, structure, path=""):
        """Recursively validate the structure of the data against the required structure."""
        if isinstance(structure, dict):
            if not isinstance(data, dict):
                raise ValueError(f"Expected dict at {path}, got {type(data)}")

            # Check for missing required fields
            for key, expected_type in structure.items():
                if key not in data:
                    raise ValueError(f"Missing required field: {path + key}")

                new_path = f"{path}{key}." if path else f"{key}."
                self._validate_structure(data[key], expected_type, new_path)

        elif isinstance(structure, tuple):
            if not isinstance(data, structure):
                raise ValueError(
                    f"Invalid type at {path[:-1]}: expected {structure}, got {type(data)}"
                )
        else:
            if not isinstance(data, structure):
                raise ValueError(
                    f"Invalid type at {path[:-1]}: expected {structure}, got {type(data)}"
                )

    def process_item(self, item, spider):
        """Process and validate the scraped item."""
        try:
            self._validate_structure(item, self.REQUIRED_STRUCTURE)
            return item
        except ValueError as e:
            raise ValueError(f"Output structure validation failed: {str(e)}")
