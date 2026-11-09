from rest_framework import viewsets
from network.models import Difficulty, Category, Notion, Question, Utilisateur, Answer, TentativeQuestion
from rest_framework_simplejwt.tokens import RefreshToken
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

    def get_auth_response(self, utilisateur, message, status_code):
        refresh = RefreshToken.for_user(utilisateur)
        access = refresh.access_token
        data = {
            "message": message,
            "user": {
                "id": utilisateur.id,
                "username": utilisateur.username,
            },
        }

        # Si le client est mobile, on renvoie le refresh token dans la réponse JSON, sinon on le met dans un cookie httpOnly pour les clients web.
        if self.request.headers.get("X-Client-Type") == "mobile":
            data["access"] = str(access)
            data["refresh"] = str(refresh)

            return Response(data, status=status_code)

        # Si le client est web, on renvoie le refresh token dans un cookie httpOnly pour plus de sécurité, et l'access token dans la réponse JSON.
        response = Response(
            {
                **data,
                "access": str(access)
            },
            status=status_code
        )

        # C'est pour mettre le refresh token dans un cookie httpOnly pour les clients web, ce qui est plus sécurisé que de le renvoyer dans la réponse JSON.
        response.set_cookie(
            key="refresh_token",
            value=str(refresh),
            httponly=True,
            secure=True,
            samesite="Lax",
            path="/api/auth/",
        )
        return response
    permission_classes = [AllowAny]


    # Pour l'inscription
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