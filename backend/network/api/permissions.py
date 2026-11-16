from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Autorise la consultation en lecture seule aux utilisateurs authentifiés,
    et réserve la création, la modification et la suppression aux
    administrateurs (is_staff=True).

    - GET, HEAD, OPTIONS  : utilisateur authentifié
    - POST, PUT, PATCH, DELETE : administrateur uniquement
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_staff)
