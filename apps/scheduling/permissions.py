from rest_framework.permissions import BasePermission

class CanManageProviderSchedule(BasePermission):
    manage = "You can only manage your own schedule."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_business_admin:
            return True
        profile = getattr(user, "provider_profile", None)
        return profile is not None and str(profile.pk) == str(view.kwargs.get("provider_pk"))