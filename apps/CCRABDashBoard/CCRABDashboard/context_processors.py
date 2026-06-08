from rest_framework_simplejwt.tokens import RefreshToken


def frontend_api_auth(request):
    token = ""
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        refresh = RefreshToken.for_user(user)
        token = str(refresh.access_token)

    context = {
        "api_access_token": token,
    }
    return context
