from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.otp.choices import OtpPurpose
from apps.otp.v1.serializers import OtpVerifySerializer

User = get_user_model()
CONFIG = settings.CONFIG


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    otp = serializers.CharField(
        write_only=True,
        max_length=CONFIG.OTP_LENGTH,
        min_length=CONFIG.OTP_LENGTH,
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "password", "otp")

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        otp_serializer = OtpVerifySerializer(data={
            "identifier": attrs["email"],
            "otp": attrs["otp"],
            "purpose": OtpPurpose.REGISTRATION,
        })
        otp_serializer.is_valid(raise_exception=True)

        if not otp_serializer.verify():
            raise serializers.ValidationError({"otp": ["Invalid or expired OTP."]})

        return attrs

    def create(self, validated_data):
        validated_data.pop("otp")
        return User.objects.create_user(**validated_data)


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = {
            "id": self.user.id,
            "email": self.user.email,
        }
        return data
