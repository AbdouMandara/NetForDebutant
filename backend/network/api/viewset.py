from rest_framework import viewsets
from network.models import Difficulty, Category, Notion, Question, Utilisateur, Answer, TentativeQuestion
from rest_framework_simplejwt.tokens import RefreshToken
from network.api.serializer import CategorySerializer, RegisterSerializer, DifficultySerializer, NotionSerializer, UtilisateurSerializer, QuestionSerializer, AnswerSerializer, TentativeQuestionSerializer, GoogleAuthSerializer
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from network.services.google_oauth import verify_google_id_token


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

    # AUth avec Google OAuth
    @action(detail=False, methods=["post"])
    def google_oauth(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_token = serializer.validated_data["id_token"]
        google_user_info = verify_google_id_token(id_token)
        email = google_user_info.get("email")
        username = google_user_info.get("name")
        google_sub = google_user_info.get("sub")
        photo = google_user_info.get("picture")

        utilisateur = Utilisateur.objects.filter(
            google_sub=google_sub
        ).first()

        if not utilisateur:
            utilisateur = Utilisateur.objects.create(
                username=username,
                email=email,
                google_sub=google_sub,
                photo=photo
            )
            return self.get_auth_response(
                utilisateur=utilisateur,
                message="Inscription via Google OAuth réussie.",
                status_code=status.HTTP_201_CREATED,
            )

        return self.get_auth_response(
            utilisateur=utilisateur,
            message="Connexion via Google OAuth réussie.",
            status_code=status.HTTP_200_OK,
        )