from network.models import Difficulty, Category, Notion, Question, Utilisateur, Answer, TentativeQuestion
from network.api.serializer import CategorySerializer, DifficultySerializer, NotionSerializer, UtilisateurSerializer, QuestionSerializer, AnswerSerializer, TentativeQuestionSerializer
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

class UserViewSet(ReadOnlyModelViewSet) :
    serializer_class = UtilisateurSerializer
    queryset = Utilisateur.objects.all()
