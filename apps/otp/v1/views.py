from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.core.utils.response import success_response
from apps.otp.services import OTPService
from apps.otp.services.rules import verify_otp_rules
from apps.otp.throttles import (
    OtpAnonRateThrottle,
    OtpUserRateThrottle,
    OtpTargetRateThrottle,
)

CONFIG = settings.CONFIG


class GetOtpView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [
        OtpAnonRateThrottle,
        OtpUserRateThrottle,
        OtpTargetRateThrottle,
    ]

    def post(self, request):
        ok, result = verify_otp_rules(request)
        if not ok:
            return result

        purpose = result["purpose"]
        user_identifier = result["user_identifier"]
        otp_channel = result["otp_channel"]

        OTPService.send(user=user_identifier, purpose=purpose, channel=otp_channel)

        return success_response(
            message=f"OTP sent successfully. Please check your {otp_channel}. Valid for {CONFIG.OTP_EXPIRY_MINUTES} minutes.",
            status_code=status.HTTP_200_OK,
        )
