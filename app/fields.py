from decimal import Decimal
from django.db import models

def decimal_field(required=False, decimal_places=2, **kwargs) -> models.DecimalField:
    required_fields = (
        {"db_default": Decimal("0.00"), "default": 0 , "blank": True, "null": True}
        if not required
        else {}
    )
    return models.DecimalField(
        max_digits=12, decimal_places=decimal_places, **required_fields, **kwargs
    )
