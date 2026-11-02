from rest_framework.views import APIView
from rest_framework import status
from django.contrib.auth import get_user_model

from apps.core.utils.response import error_response, success_response
from apps.otp.choices import OtpPurpose

User = get_user_model()


class EmailOtpView(APIView):
    """Placeholder — wire into urls_v1.py when implemented."""

    def post(self, request):
        pass
