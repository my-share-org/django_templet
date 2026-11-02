from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from apps.authentication.v1.views import (
    RegisterView,
    LoginView,
    LogoutView,
    VerifyUserView,
    ChangePasswordView,
    ResetPasswordView,
)

app_name = "auth_v1"

urlpatterns = [
    path("register/",        RegisterView.as_view(),    name="register"),
    path("login/",           LoginView.as_view(),       name="login"),
    path("logout/",          LogoutView.as_view(),      name="logout"),
    path("token/refresh/",   TokenRefreshView.as_view(), name="token-refresh"),
    path("token/verify/",    TokenVerifyView.as_view(),  name="token-verify"),
    path("verify/",          VerifyUserView.as_view(),   name="verify"),
    path("password/change/", ChangePasswordView.as_view(), name="password-change"),
    path("password/reset/",  ResetPasswordView.as_view(),  name="password-reset"),
]
