# CCRABDashboard/permissions.py
from rest_framework.permissions import BasePermission


class HasPrivateApiAccess(BasePermission):
    message = "You do not have access to this endpoint."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        return user.groups.filter(name="private_api_access").exists()
