from django.contrib.auth import authenticate, login as dj_login, logout as dj_logout
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    user = authenticate(request, username=username, password=password)
    print("Authenticating user:", user , username)
    if not user:
        return Response({"ok": False, "error": "invalid_credentials"}, status=400)
    dj_login(request, user)
    return Response({"ok": True, "user": {"id": user.pk, "username": user.get_username()}})

@api_view(["POST"])
def logout(request):
    dj_logout(request)
    return Response({"ok": True})

@api_view(["GET"])
def me(request):
    u = request.user
    return Response({"authenticated": u.is_authenticated, "user": None if not u.is_authenticated else {"id": u.pk, "username": u.get_username()}})
