from rest_framework.routers import DefaultRouter
from network.api.viewset import AuthViewSet, UserViewSet

router = DefaultRouter()

router.register(r'v1/users', UserViewSet, basename='user')
router.register(r'v1/auth', AuthViewSet, basename='auth')

urlpatterns = router.urls