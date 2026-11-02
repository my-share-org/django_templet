from rest_framework import serializers
from django.conf import settings
from apps.otp.choices import OtpPurpose
from apps.otp.services import OTPService

CONFIG = settings.CONFIG


class OtpVerifySerializer(serializers.Serializer):
    otp        = serializers.CharField(write_only=True, max_length=CONFIG.OTP_LENGTH, min_length=CONFIG.OTP_LENGTH)
    identifier = serializers.CharField(write_only=True)
    purpose    = serializers.ChoiceField(write_only=True, choices=OtpPurpose.choices)

    _otp_service = OTPService()

    def verify(self) -> bool:
        return self._otp_service.verify(
            user=self.validated_data["identifier"],
            purpose=self.validated_data["purpose"],
            submitted_otp=self.validated_data["otp"],
        )
