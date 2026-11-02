from django.db.models import TextChoices

class EmailBodyType(TextChoices):
    HTML = 'html', 'HTML'
    TEXT = 'text', 'TEXT'

class EmailStatus(TextChoices):
    PENDING = 'pending', 'PENDING'
    SENT = 'sent', 'SENT'
    FAILED = 'failed', 'FAILED'
    SCHEDULED = 'scheduled', 'SCHEDULED'

class EmailPurpose(TextChoices):
    OTHERS = 'others', 'OTHERS'
    WELCOME = 'welcome', 'WELCOME'
    PASSWORD_RESET = 'password_reset', 'PASSWORD_RESET'
    REGISTRATION = 'registration', 'REGISTRATION'
    DISCOUNT_CODE = 'discount_code', 'DISCOUNT_CODE'
    OTP = 'otp', 'OTP'


