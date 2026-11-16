from rest_framework.routers import DefaultRouter
from network.api.viewset import (
    AuthViewSet,
    UserViewSet,
    CategoryViewSet,
    DifficultyViewSet,
    NotionViewSet,
    QuestionViewSet,
    AnswerViewSet,
    TentativeQuestionViewSet,
)

router = DefaultRouter()

router.register(r'v1/users', UserViewSet, basename='user')
router.register(r'v1/auth', AuthViewSet, basename='auth')
router.register(r'v1/categories', CategoryViewSet, basename='category')
router.register(r'v1/difficulties', DifficultyViewSet, basename='difficulty')
router.register(r'v1/notions', NotionViewSet, basename='notion')
router.register(r'v1/questions', QuestionViewSet, basename='question')
router.register(r'v1/answers', AnswerViewSet, basename='answer')
router.register(r'v1/tentatives', TentativeQuestionViewSet, basename='tentative')

urlpatterns = router.urls