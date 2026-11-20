from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def has_staff_flag(user, flag):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(settings, "STAFF_TEST_MODE", False):
        return True
    if user.is_superuser:
        return True
    if not user.is_staff:
        return False
    profile = getattr(user, "club_profile", None)
    return bool(profile and getattr(profile, flag, False))


def can_manage_quick(user):
    return has_staff_flag(user, "can_manage_quick")


def can_manage_large(user):
    return has_staff_flag(user, "can_manage_large")


def can_edit_rulebook(user):
    return has_staff_flag(user, "can_edit_rulebook")


def can_edit_rules(user):
    return has_staff_flag(user, "can_edit_rules")


def can_manage_listings(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(settings, "STAFF_TEST_MODE", False):
        return True
    return bool(getattr(user, "is_superuser", False))


def staff_flags(user):
    listings = can_manage_listings(user)
    return {
        "quick": can_manage_quick(user),
        "large": can_manage_large(user),
        "rulebook": can_edit_rulebook(user),
        "rules": can_edit_rules(user),
        "listings": listings,
        "any": has_staff_flag(user, "can_manage_quick")
        or has_staff_flag(user, "can_manage_large")
        or has_staff_flag(user, "can_edit_rulebook")
        or has_staff_flag(user, "can_edit_rules")
        or listings
        or getattr(user, "is_superuser", False),
    }


def require_staff_flag(flag):
    def decorator(view):
        @login_required(login_url="profile")
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not has_staff_flag(request.user, flag):
                messages.error(request, "اجازه این کار را ندارید.")
                return redirect("home")
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
