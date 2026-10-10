"""
accounts.permissions
=====================
Two equivalent ways to guard an Admin-only view — a mixin for
class-based views and a decorator for function-based ones. This project
only uses the decorator (every view in materials/views.py is a plain
function), but the mixin is kept available since it's the more natural
fit if a class-based view is added later; both share `_is_admin` so the
actual rule is defined exactly once.

Both draw the same distinction, deliberately:

  * Not logged in at all       -> redirect to the login page (like
                                   Django's own @login_required — the
                                   visitor might just need to sign in).
  * Logged in, but not Admin   -> 403 Forbidden (logging in again
                                   wouldn't help; a Student account is
                                   never going to pass this check).

An earlier version of `admin_required` raised a bare 403 for anonymous
visitors too, which meant a signed-out student clicking "Upload" got a
dead-end error page instead of a login prompt. Kept as a documented
example: the same mistake is easy to reintroduce if a future admin-only
view is guarded by hand instead of reusing these.
"""
from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def _is_admin(user) -> bool:
    return user.is_authenticated and getattr(user, "role", None) == user.Role.ADMIN


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Class-based-view mixin: only Admin accounts may proceed."""

    def test_func(self):
        return _is_admin(self.request.user)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()  # LoginRequiredMixin's redirect-to-login
        raise PermissionDenied("You must be an administrator to access this page.")


def admin_required(view_func):
    """Function-based-view decorator equivalent of AdminRequiredMixin."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not _is_admin(request.user):
            raise PermissionDenied("You must be an administrator to access this page.")
        return view_func(request, *args, **kwargs)

    return _wrapped
