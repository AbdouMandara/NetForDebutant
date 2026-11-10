from django.db import IntegrityError, transaction
from rest_framework import viewsets
from network.models import Difficulty, Category, Notion, Question, Utilisateur, Answer, TentativeQuestion
from rest_framework_simplejwt.tokens import RefreshToken
from network.api.serializer import CategorySerializer, RegisterSerializer, DifficultySerializer, NotionSerializer, UtilisateurSerializer, QuestionSerializer, AnswerSerializer, TentativeQuestionSerializer, GoogleAuthSerializer, LogoutSerializer
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from network.services.google_oauth import verify_google_id_token
from rest_framework.throttling import ScopedRateThrottle

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
    @action(detail=False, methods=['post'], throttle_classes=[ScopedRateThrottle])
    def register(self, request):
        self.throttle_scope = "auth_register"
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()


        return self.get_auth_response(
            utilisateur=user,
            message="Inscription réussie.",
            status_code=status.HTTP_201_CREATED,
        )

    # Pour la connexion
    @action(detail=False, methods=["post"], throttle_classes=[ScopedRateThrottle])
    def login(self, request):
        self.throttle_scope = "auth_login"
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

    @action(detail=False, methods=["post"], throttle_classes=[ScopedRateThrottle])
    def google_oauth(self, request):
        self.throttle_scope = "auth_google"
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["id_token"]

        try:
            google_user_info = verify_google_id_token(token)
        except ValueError:
            return Response(
                {"detail": "Jeton Google invalide ou expiré."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        google_sub = google_user_info["sub"]
        email = google_user_info["email"]
        username = google_user_info.get("name") or email.split("@")[0]
        photo = google_user_info.get("picture")

        if google_user_info.get("email_verified") is not True:
            return Response(
                {"detail": "L'adresse e-mail Google n'est pas vérifiée."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1. Rechercher un compte Google existant
        utilisateur = Utilisateur.objects.filter(
            google_sub=google_sub
        ).first()

        if utilisateur:
            return self.get_auth_response(
                utilisateur=utilisateur,
                message="Connexion via Google réussie.",
                status_code=status.HTTP_200_OK,
            )

        # 2. Vérifier si l'e-mail appartient déjà à un compte
        if Utilisateur.objects.filter(email=email).exists():
            return Response(
                {
                    "detail": (
                        "Un compte existe déjà avec cette adresse e-mail. "
                        "Connectez-vous avec votre méthode habituelle "
                        "pour associer votre compte Google."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        # 3. Créer un nouvel utilisateur
        try:
            with transaction.atomic():
                utilisateur = Utilisateur.objects.create_user(
                    username=username,
                    email=email,
                    google_sub=google_sub,
                    photo=photo,
                )
                utilisateur.set_unusable_password()
                utilisateur.save(update_fields=["password"])

        except IntegrityError:
            return Response(
                {
                    "detail": (
                        "Un compte avec ces informations existe déjà. "
                        "Réessayez de vous connecter."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        # 4. Générer les JWT
        return self.get_auth_response(
            utilisateur=utilisateur,
            message="Inscription via Google réussie.",
            status_code=status.HTTP_201_CREATED,
        )


    @action(
    detail=False,
    methods=["post"],
    permission_classes=[AllowAny],
    authentication_classes=[],
)
    def logout(self, request):
        is_mobile = request.headers.get("X-Client-Type") == "mobile"

        refresh_token = (
            request.data.get("refresh")
            if is_mobile
            else request.COOKIES.get("refresh_token")
        )

        serializer = LogoutSerializer(
            data={"refresh": refresh_token}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response = Response(
            {"message": "Déconnexion réussie."},
            status=status.HTTP_200_OK,
        )

        if not is_mobile:
            response.delete_cookie(
                key="refresh_token",
                path="/api/auth/",
                samesite="Lax",
            )

        return response