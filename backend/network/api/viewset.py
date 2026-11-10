from rest_framework import viewsets
from network.models import Difficulty, Category, Notion, Question, Utilisateur, Answer, TentativeQuestion
from rest_framework_simplejwt.tokens import RefreshToken
from network.api.serializer import CategorySerializer, RegisterSerializer, DifficultySerializer, NotionSerializer, UtilisateurSerializer, QuestionSerializer, AnswerSerializer, TentativeQuestionSerializer
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class UserViewSet(ModelViewSet): 
    serializer_class = UtilisateurSerializer
    queryset = Utilisateur.objects.all()

class AuthViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]

    def get_auth_response(self, utilisateur, message, status_code, refresh=None):
        if refresh is None:
            refresh = RefreshToken.for_user(utilisateur)

        access = refresh.access_token

        data = {
            "message": message,
            "user": {
                "username": utilisateur.username,
                "email": utilisateur.email,
            },
        }

        if self.request.headers.get("X-Client-Type") == "mobile":
            data["access"] = str(access)
            data["refresh"] = str(refresh)
            return Response(data, status=status_code)

        response = Response(
            {**data, "access": str(access)},
            status=status_code
        )

        response.set_cookie(
            key="refresh_token",
            value=str(refresh),
            httponly=True,
            secure=True,
            samesite="Lax",
            path="/api/auth/",
        )

        return response



    # Pour l'inscription
    @action(detail=False, methods=['post'])
    
    def register(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()


        return self.get_auth_response(
            utilisateur=user,
            message="Inscription réussie.",
            status_code=status.HTTP_201_CREATED,
        )

    # Pour la connexion
    @action(detail=False, methods=["post"])
    def login(self, request):
        serializer = TokenObtainPairSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh = serializer.validated_data["refresh"]
        utilisateur = serializer.user

        return self.get_auth_response(
            utilisateur=utilisateur,
            message="Connexion réussie.",
            status_code=status.HTTP_200_OK,
            refresh=RefreshToken(refresh),
        )