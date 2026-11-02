from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from apps.core.utils.response import success_response, error_response
from apps.core.utils.general import get_or_400
from rest_framework import status

class test1(APIView): # Verify Otp
    permission_classes = [AllowAny]
    
    def post(self, request):
        flag, data = get_or_400(
            data=request.data,
            required=["purpose", "otp", "email"],
            keys={"purpose": str, "otp": str, "email": str}
        )

        if not flag:
            return data

        from apps.otp.services import OTPService
        is_verified = OTPService.verify(
            user=data['email'],
            submitted_otp=data['otp'],
            purpose=data['purpose']
        )

        if not is_verified:
            return error_response(
                message='OTP is not valid',
                status_code=status.HTTP_400_BAD_REQUEST
            )

        return success_response(
            message="OTP verified successfully",
            status_code=status.HTTP_200_OK
        )

class test2(APIView): # Test Logs
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.logs.services import (
            log_debug, log_info, log_success,
            log_warning, log_error, log_critical
        )

        # ─────────────────────────────────────────────────────────────
        # Scenario A: All log levels WITH service_name = "auth_service"
        # Expected DB result: service_name = "auth_service" on each row
        # ─────────────────────────────────────────────────────────────
        log_debug(
            event="svcA_debug",
            message="[Scenario A] Debug log — auth_service.",
            service_name="auth_service",
            metadata={"scenario": "A", "step": "debug"},
        )
        log_info(
            event="svcA_info",
            message="[Scenario A] Info log — auth_service.",
            service_name="auth_service",
        )
        log_success(
            event="svcA_success",
            message="[Scenario A] Success log — auth_service.",
            service_name="auth_service",
        )
        log_warning(
            event="svcA_warning",
            message="[Scenario A] Warning log — auth_service.",
            service_name="auth_service",
        )

        try:
            x = 1 / 0
        except Exception as e:
            log_error(
                event="svcA_error",
                message=f"[Scenario A] Error log — auth_service: {str(e)}",
                service_name="auth_service",
                traceback=True,
                metadata={"custom_key": "custom_value"},
            )
            log_critical(
                event="svcA_critical",
                message=f"[Scenario A] Critical log — auth_service: {str(e)}",
                service_name="auth_service",
                traceback=True,
            )

        # ─────────────────────────────────────────────────────────────
        # Scenario B: Logs WITHOUT service_name
        # Expected DB result: service_name = NULL on each row
        # ─────────────────────────────────────────────────────────────
        log_info(
            event="svcB_info",
            message="[Scenario B] Info log — NO service_name, should be null.",
        )
        log_warning(
            event="svcB_warning",
            message="[Scenario B] Warning log — NO service_name, should be null.",
        )

        return success_response(
            message="Test logs generated successfully",
            status_code=status.HTTP_200_OK
        )
