from rest_framework.routers import DefaultRouter
from api.viewset import UserViewSet

router = DefaultRouter()

router.register(r'v1/users', UserViewSet, basename='user')