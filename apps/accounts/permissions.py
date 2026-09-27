from django.contrib.auth import get_user_model
from rest_framework.permissions import SAFE_METHODS, BasePermission

User = get_user_model()


def _has_role(user, role: str) -> bool:
    return bool(user and user.is_authenticated and user.role == role)


class IsCustomer(BasePermission):
    message = "Only customers can perform this action."

    def has_permission(self, request, view):
        return _has_role(request.user, User.Role.CUSTOMER)


class IsProvider(BasePermission):
    message = "Only providers can perform this action."

    def has_permission(self, request, view):
        # Role alone is not enough: the provider profile must exist too.
        return _has_role(request.user, User.Role.PROVIDER) and hasattr(
            request.user, "provider_profile"
        )


class IsBusinessAdmin(BasePermission):
    message = "Only business admins can perform this action."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_business_admin)


class IsBusinessAdminOrReadOnly(BasePermission):
    """Any authenticated user can read; only business admins can write."""

    message = "Only business admins can modify this resource."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or user.is_business_admin