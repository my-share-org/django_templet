from django.core.exceptions import ValidationError
import phonenumbers
from phonenumbers import NumberParseException


def validate_phone(phone: str, region: str = None) -> str:
    """
    Validate and normalize international phone numbers.

    :param phone: Phone number string (e.g., +8801712345678)
    :param region: Optional default region (e.g., 'BD', 'US')
    :return: Normalized E.164 formatted number
    """
    try:
        parsed = phonenumbers.parse(phone, region)
    except NumberParseException:
        raise ValidationError("Invalid phone number format")

    if not phonenumbers.is_valid_number(parsed):
        raise ValidationError("Invalid phone number")

    return phonenumbers.format_number(
        parsed,
        phonenumbers.PhoneNumberFormat.E164
    )

class DataSerializer:
    def __init__(self, data):
        self.data = data
    
    def bool(self):
        if isinstance(self.data, bool):
            return self.data
        elif isinstance(self.data, int):
            return bool(self.data)
        elif isinstance(self.data, str):
            if self.data.lower() in ["true", "1", "t", "y", "yes"]:
                return True
            elif self.data.lower() in ["false", "0", "f", "n", "no"]:
                return False
            else:
                raise ValueError(f"Invalid boolean value [{self.data}]")
        else:
            raise ValueError(f"Invalid boolean value [{self.data}]")
            
        