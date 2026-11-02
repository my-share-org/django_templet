from django.db import models


class DeviceType(models.TextChoices):
    DESKTOP = "desktop", "Desktop"
    MOBILE = "mobile", "Mobile"
    TABLET = "tablet", "Tablet"
    UNKNOWN = "unknown", "Unknown"


class ActivityAction(models.TextChoices):
    PAGE_VIEW = "page_view", "Page View"
    RESOURCE_CREATED = "resource_created", "Resource Created"
    RESOURCE_UPDATED = "resource_updated", "Resource Updated"
    RESOURCE_DELETED = "resource_deleted", "Resource Deleted"
    SEARCH = "search", "Search"
    EXPORT = "export", "Export"
    LOGIN = "login", "Login"
    LOGOUT = "logout", "Logout"
    TOKEN_REFRESH = "token_refresh", "Token Refresh"
    PASSWORD_CHANGE = "password_change", "Password Change"
    PASSWORD_RESET = "password_reset", "Password Reset"
    OTP_REQUESTED = "otp_requested", "Otp Requested"
    FILE_UPLOAD = "file_upload", "File Upload"
    UNKNOWN = "unknown", "Unknown"
