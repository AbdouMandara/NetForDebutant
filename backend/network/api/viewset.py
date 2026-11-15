from django.db import IntegrityError, transaction
from rest_framework import viewsets
from network.models import Difficulty, Category, Notion, Question, Utilisateur, Answer, TentativeQuestion
from rest_framework_simplejwt.tokens import RefreshToken
from network.api.serializer import CategorySerializer, RegisterSerializer, DifficultySerializer, NotionSerializer, UtilisateurSerializer, QuestionSerializer, AnswerSerializer, TentativeQuestionSerializer, GoogleAuthSerializer, LogoutSerializer
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from network.services.google_oauth import verify_google_id_token
from rest_framework.throttling import ScopedRateThrottle
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator

class UserViewSet(ModelViewSet):
    serializer_class = UtilisateurSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Utilisateur.objects.all()

        return Utilisateur.objects.filter(id=user.id)

    def get_permissions(self):
        if self.action in ["create", "destroy"]:
            if not self.request.user.is_staff:
                return [IsAdminUser()]

        return [IsAuthenticated()]

class AuthViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    # Necessaire pour afficher dans la documentation de l'API
    def get_serializer_class(self):
        serializers = {
            "register": RegisterSerializer,
            "login": TokenObtainPairSerializer,
            "google_oauth": GoogleAuthSerializer,
            "logout": LogoutSerializer,
        }

        return serializers.get(self.action)
    
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
            path="/api/v1/auth/",
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


    @action( detail=False, methods=["post"], permission_classes=[AllowAny], authentication_classes=[])
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
                path="/api/v1/auth/",
                samesite="Lax",
            )
        print("CLIENT :", request.headers.get("X-Client-Type"))
        print("REFRESH TOKEN :", refresh_token)
        return response


    @action(detail=False, methods=["post"], permission_classes=[AllowAny], authentication_classes=[],throttle_classes=[ScopedRateThrottle],)
    def refresh(self, request):
        is_mobile = request.headers.get("X-Client-Type") == "mobile"
        print("COOKIES :", request.COOKIES)
        print("HEADERS :", request.headers)
        refresh_token = (
            request.data.get("refresh")
            if is_mobile
            else request.COOKIES.get("refresh_token")
        )

        if not refresh_token:
            return Response(
                {"detail": "Refresh token manquant."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TokenRefreshSerializer(
            data={"refresh": refresh_token}
        )

        serializer.is_valid(raise_exception=True)

        tokens = serializer.validated_data

        if is_mobile:
            return Response(tokens, status=status.HTTP_200_OK)

        response = Response(
            {"access": tokens["access"]},
            status=status.HTTP_200_OK,
        )

        if "refresh" in tokens:
            response.set_cookie(
                key="refresh_token",
                value=tokens["refresh"],
                httponly=True,
                secure=True,
                samesite="Lax",
                path="/api/v1/auth/",
            )

        return response

# Creation de l'endpoint utilisable par le front-end pour avoir le cookie CSRF
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        authentication_classes=[],
    )
    @method_decorator(ensure_csrf_cookie)
    def csrf_token(self, request):
        return Response({
            "csrfToken": get_token(request)
        })