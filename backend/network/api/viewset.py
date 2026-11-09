from rest_framework import viewsets
from network.models import Difficulty, Category, Notion, Question, Utilisateur, Answer, TentativeQuestion
from network.api.serializer import CategorySerializer, RegisterSerializer, DifficultySerializer, NotionSerializer, UtilisateurSerializer, QuestionSerializer, AnswerSerializer, TentativeQuestionSerializer
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated

class UserViewSet(ModelViewSet): 
    serializer_class = UtilisateurSerializer
    queryset = Utilisateur.objects.all()

class AuthViewSet(viewsets.GenericViewSet):

    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def register(self, request):

        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                'message': 'Inscription réussie.',
                'user': {
                    'id': user.id,
                    'username': user.username,
                }
            },
            status=status.HTTP_201_CREATED
        )