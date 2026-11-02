from django.db.models import TextChoices

class OtpPurpose(TextChoices):
    OTHER = 'other', 'OTHER'
    LOGIN = 'login', 'LOGIN'
    REGISTRATION = 'registration', 'REGISTRATION'
    PASSWORD_CHANGE = 'password_change', 'PASSWORD CHANGE'
    PASSWORD_RESET = 'password_reset', 'PASSWORD RESET'
    VERIFICATION = 'verification', 'VERIFICATION'
    CHANGE_USERNAME = 'change_username', 'CHANGE USERNAME'
    CHANGE_EMAIL = 'change_email', 'CHANGE EMAIL'
    CHANGE_PHONE = 'change_phone', 'CHANGE PHONE'
    
class OtpChannel(TextChoices):
    ALL = 'all', 'ALL'
    EMAIL = 'email', 'EMAIL'
    PHONE = 'phone', 'PHONE'