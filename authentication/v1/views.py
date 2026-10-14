from rest_framework.views import APIView
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from core.utils.response import success_response, error_response
from core.utils.general import get_or_400
from authentication.throttles import (
    RegisterThrottle,
    LoginThrottle,
    LoginTargetThrottle,
    ChangePasswordThrottle,
    ResetPasswordThrottle,
    ResetPasswordTargetThrottle,
)
from authentication.v1.serializers import RegisterSerializer, LoginSerializer
from authentication.services import change_password, reset_password
from otp.v1.serializers import OtpVerifySerializer
from otp.choices import OtpPurpose


class RegisterView(APIView):
    throttle_classes = [RegisterThrottle]
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Invalid registration data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return success_response(
            message="User registered successfully",
            data={
                "email": user.email,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status_code=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_classes = [LoginThrottle, LoginTargetThrottle]
    permission_classes = [permissions.AllowAny]


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return error_response(
                message="Refresh token is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            if hasattr(request, "user") and request.user.is_authenticated:
                from activity.services import end_all_user_sessions
                end_all_user_sessions(request.user)
                request._session_ended = True
                request.activity_session = None
            return success_response(
                message="Logged out successfully",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return error_response(
                message="Invalid or already blacklisted token",
                errors=e,
                status_code=status.HTTP_400_BAD_REQUEST,
            )


class VerifyUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        return success_response(
            message="User verified successfully",
            data={
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        )


class ResetPasswordView(APIView):
    """
    Complete a password reset after OTP verification.
    Flow: POST /v1/otp/get-otp/ (purpose=password_reset) → POST /v1/auth/password/reset/
    """
    throttle_classes = [ResetPasswordThrottle, ResetPasswordTargetThrottle]
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ok, result = get_or_400(
            data=request.data,
            keys={"email": str, "otp": str, "new_password": str},
            required=["email", "otp", "new_password"],
        )
        if not ok:
            return result

        email       = result["email"]
        otp         = result["otp"]
        new_password = result["new_password"]

        otp_serializer = OtpVerifySerializer(data={
            "identifier": email,
            "otp": otp,
            "purpose": OtpPurpose.PASSWORD_RESET,
        })
        if not otp_serializer.is_valid():
            return error_response(
                message="Invalid OTP data",
                errors=otp_serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not otp_serializer.verify():
            return error_response(
                message="Invalid or expired OTP",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            reset_password(email, new_password)
        except Exception as e:
            return error_response(
                message="Password reset failed",
                errors=e,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return success_response(
            message="Password reset successfully",
            status_code=status.HTTP_200_OK,
        )


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ChangePasswordThrottle]

    def post(self, request):
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not old_password or not new_password:
            return error_response(
                message="Both old_password and new_password are required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.check_password(old_password):
            return error_response(
                message="Current password is incorrect",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            change_password(request.user, new_password)
        except Exception as e:
            return error_response(
                message="Password change failed",
                errors=e,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return success_response(
            message="Password changed successfully",
            status_code=status.HTTP_200_OK,
        )
