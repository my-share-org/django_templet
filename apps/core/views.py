from django.db import connection
from django.shortcuts import render
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.services import health_report
from apps.core.throttles import HealthThrottle


class HealthCheckView(APIView):
    """
    Lightweight health check endpoint for Docker, load balancers, and container orchestration.
    Returns HTTP 200 with {"status": "healthy"} when core DB is reachable.
    Returns HTTP 503 if the database is unavailable.
    """
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request, *args, **kwargs):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
            return Response({"status": "healthy"}, status=status.HTTP_200_OK)
        except Exception:
            return Response(
                {"status": "unhealthy"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class HealthReportView(APIView):
    """
    Detailed developer diagnostic dashboard.
    Only enabled in DEBUG mode via conditional URL routing.
    """
    permission_classes = [AllowAny]
    throttle_classes = [HealthThrottle]

    def get(self, request, *args, **kwargs):
        health = health_report()
        return render(request, "health_report.html", health)