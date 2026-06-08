from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken


class UserRegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate_username(self, value):
        user_model = get_user_model()
        if user_model.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages)
        return value

    def create(self, validated_data):
        username = validated_data["username"]
        password = validated_data["password"]
        email = validated_data.get("email", "")

        user_model = get_user_model()
        user = user_model.objects.create_user(
            username=username,
            password=password,
            email=email,
        )
        return user


@api_view(["POST"])
@permission_classes([AllowAny])
def register_user_api(request):
    serializer = UserRegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()

    refresh = RefreshToken.for_user(user)
    payload = {
        "id": user.pk,
        "username": user.get_username(),
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }
    return Response(payload, status=status.HTTP_201_CREATED)
