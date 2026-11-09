from network.models import Difficulty, Category, Notion, Question, Utilisateur, Answer, TentativeQuestion
from api.serializer import CategorySerializer, DifficultySerializer, NotionSerializer, UtilisateurSerializer, QuestionSerializer, AnswerSerializer, TentativeQuestionSerializer
from rest_framework.viewsets import ModelViewSet

class UserViewSet(ModelViewSet): 
    serializer_class = UtilisateurSerializer
    queryset = Utilisateur.objects.all()
    