from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from ..api_views import register_user_api

urlpatterns = [
    path("register/", register_user_api, name="user_register"),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("", include("projects_catalog.api_urls")),
    path("", include("platforms_app.api_urls")),
]
