from django.urls import path
from apps.otp.v1.views import GetOtpView

app_name = "otp_v1"

urlpatterns = [
    path("get-otp/", GetOtpView.as_view(), name="get-otp"),
]
