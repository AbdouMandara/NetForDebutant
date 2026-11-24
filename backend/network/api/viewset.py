from django.db import IntegrityError, transaction
from django.db.models import F, Count, Q, Exists, OuterRef
from rest_framework import viewsets
from network.models import Difficulty, Category, Notion, Question, Utilisateur, Answer, TentativeQuestion
from rest_framework_simplejwt.tokens import RefreshToken
from network.api.serializer import CategorySerializer, RegisterSerializer, DifficultySerializer, NotionSerializer, UtilisateurSerializer, QuestionSerializer, AnswerSerializer, AdminAnswerSerializer, TentativeQuestionSerializer, NotionProgressionSerializer, GoogleAuthSerializer, LogoutSerializer, AuthResponseSerializer, RefreshSerializer, RefreshResponseSerializer, CsrfTokenSerializer, MesStatistiquesSerializer
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from network.api.permissions import IsAdminOrReadOnly
from network.services.google_oauth import verify_google_id_token
from rest_framework.throttling import ScopedRateThrottle
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from network.api.pagination import StandardResultsSetPagination
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema

# % de questions réussies (au moins une fois) pour considérer une notion maîtrisée.
# Surchargeable par requête : GET .../ma-progression/?seuil=50
SEUIL_MAITRISE = 70

# En-tête commun aux endpoints auth : documenté une seule fois.
HEADER_CLIENT_TYPE = OpenApiParameter(
    'X-Client-Type',
    type=OpenApiTypes.STR,
    location=OpenApiParameter.HEADER,
    required=False,
    enum=['mobile'],
    description=(
        "Envoyer `mobile` désactive la vérification CSRF et fait renvoyer "
        "les tokens access/refresh dans le corps de la réponse "
        "(sinon le refresh part dans le cookie httpOnly `refresh_token`)."
    ),
)

# Flux web : token CSRF obtenu via GET /api/v1/auth/csrf_token/
HEADER_CSRF = OpenApiParameter(
    'X-CSRFToken',
    type=OpenApiTypes.STR,
    location=OpenApiParameter.HEADER,
    required=False,
    description=(
        "Token CSRF (flux web uniquement), obtenu via "
        "GET /api/v1/auth/csrf_token/. Requis sauf si X-Client-Type: mobile."
    ),
)

# Les deux en-têtes combinés pour les endpoints qui gèrent les deux flux.
AUTH_HEADERS = [HEADER_CLIENT_TYPE, HEADER_CSRF]


class UserViewSet(ModelViewSet):
    serializer_class = UtilisateurSerializer
    permission_classes = [IsAuthenticated]

    @property
    def pagination_class(self):
        # ma-progression renvoie une liste PLATE (jamais paginée au runtime :
        # DRF ne pagine que l'action list). Sans cela, drf-spectacular
        # envelopperait la réponse dans un PaginatedXxxList fictif.
        if getattr(self, 'action', None) == 'ma_progression':
            return None
        return StandardResultsSetPagination

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

    @extend_schema(
        responses={200: MesStatistiquesSerializer},
        description=(
            "Statistiques globales de l'utilisateur connecté : score, nombre "
            "de tentatives, réponses correctes/incorrectes et taux de réussite."
        ),
    )
    @action(detail=False, methods=['get'], url_path='mes-statistiques')
    def mes_statistiques(self, request):
        user = request.user
        stats = TentativeQuestion.objects.filter(user=user).aggregate(
            total=Count('id'),
            correctes=Count('id', filter=Q(selected_answer__is_correct=True)),
            incorrectes=Count('id', filter=Q(selected_answer__is_correct=False)),
        )
        total = stats['total']
        return Response({
            'score': user.score,
            'total_tentatives': total,
            'reponses_correctes': stats['correctes'],
            'reponses_incorrectes': stats['incorrectes'],
            'taux_reussite': round(stats['correctes'] / total * 100, 2) if total else 0,
        })

    @extend_schema(
        responses={200: NotionProgressionSerializer(many=True)},
        parameters=[
            OpenApiParameter(
                name='seuil',
                type=OpenApiTypes.FLOAT,
                location=OpenApiParameter.QUERY,
                required=False,
                default=SEUIL_MAITRISE,
                description=(
                    "Pourcentage (0-100) de questions réussies requis pour "
                    "considérer une notion comme maîtrisée. 400 si invalide."
                ),
            )
        ],
        description=(
            "Progression de l'utilisateur connecté, notion par notion. Seules "
            "les notions publiées sont listées. Une notion est « maîtrisée » "
            "quand au moins `seuil` % de ses questions ont été réussies une "
            "fois au moins (une nouvelle tentative ratée ne dégrade pas le "
            "score d'une question)."
        ),
    )
    @action(detail=False, methods=['get'], url_path='ma-progression')
    def ma_progression(self, request):
        """Progression de l'utilisateur connecté, notion par notion.

        Seules les notions publiées sont listées (même sans tentative) pour
        montrer ce qu'il reste à étudier. Une notion est « maîtrisée » quand au
        moins `seuil` % de ses questions ont été réussies UNE FOIS au moins.
        """
        user = request.user
        seuil = self._seuil_maitrise(request)

        # 1 seule requête SQL : une ligne par question publiée, avec 2 booléens
        # (tentée / réussie) calculés POUR cet utilisateur via des sous-requêtes.
        # Aucun N+1 : les Exists sont évalués par la base, pas en Python.
        lignes = (
            Question.objects.filter(notion__is_published=True)
            .annotate(
                tentee=Exists(
                    TentativeQuestion.objects.filter(
                        user=user, question=OuterRef('pk')
                    )
                ),
                reussie=Exists(
                    TentativeQuestion.objects.filter(
                        user=user,
                        question=OuterRef('pk'),
                        selected_answer__is_correct=True,
                    )
                ),
            )
            .values_list('notion_id', 'tentee', 'reussie')
        )

        # Regroupement en mémoire (une seule passe, une ligne par question)
        stats = {}
        for notion_id, tentee, reussie in lignes:
            s = stats.setdefault(
                str(notion_id),
                {'questions_total': 0, 'questions_tentees': 0, 'questions_reussies': 0},
            )
            s['questions_total'] += 1
            if tentee:
                s['questions_tentees'] += 1
            if reussie:
                s['questions_reussies'] += 1

        # 1 requête : toutes les notions publiées, même sans question
        resultats = []
        vide = {'questions_total': 0, 'questions_tentees': 0, 'questions_reussies': 0}
        for notion in Notion.objects.filter(is_published=True).values('id', 'title', 'slug'):
            s = stats.get(str(notion['id']), vide)
            total = s['questions_total']
            progression = round(s['questions_reussies'] / total * 100, 2) if total else 0.0
            resultats.append({
                'notion': {
                    'id': str(notion['id']),
                    'title': notion['title'],
                    'slug': notion['slug'],
                },
                'questions_total': total,
                'questions_tentees': s['questions_tentees'],
                'questions_reussies': s['questions_reussies'],
                'progression': progression,
                'est_maitrisee': total > 0 and progression >= seuil,
            })

        return Response(NotionProgressionSerializer(resultats, many=True).data)

    @staticmethod
    def _seuil_maitrise(request):
        """Seuil de maîtrise en %, surchargeable par le paramètre ?seuil=NN."""
        brut = request.query_params.get('seuil')
        if brut is None:
            return SEUIL_MAITRISE
        try:
            seuil = float(brut)
        except (TypeError, ValueError):
            raise ValidationError({'seuil': 'Doit être un nombre entre 0 et 100.'})
        if not 0 <= seuil <= 100:
            raise ValidationError({'seuil': 'Doit être un nombre entre 0 et 100.'})
        return seuil

        
# Elle servira au niveau de la verif du csrf
class CSRFCheck(CsrfViewMiddleware):
    def _reject(self, request, reason):
        return reason


def enforce_csrf(request):
    django_request = request._request

    check = CSRFCheck(lambda request: None)
    check.process_request(django_request) #prépare la vérification du token transmis dans l'en-tete

    reason = check.process_view(
        django_request,
        None,
        (),
        {},
    ) #vérifie le cookie et le token transmis dans l'en-tête du front-end

    if reason:
        raise PermissionDenied(
            f"Verification CSRF a echoue car : {reason}"
        )
    
class AuthViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    # Necessaire pour afficher dans la documentation de l'API
    def get_serializer_class(self):
        # Attention : doit TOUJOURS renvoyer un serializer (sinon drf-spectacular
        # échoue à générer le schéma pour l'action csrf_token/refresh).
        serializers = {
            "register": RegisterSerializer,
            "login": TokenObtainPairSerializer,
            "google_oauth": GoogleAuthSerializer,
            "logout": LogoutSerializer,
            "refresh": RefreshSerializer,
            "csrf_token": CsrfTokenSerializer,
        }

        return serializers.get(self.action, CsrfTokenSerializer)
    
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
    @extend_schema(
        request=RegisterSerializer,
        responses={201: AuthResponseSerializer},
        parameters=AUTH_HEADERS,
        description=(
            "Inscription classique (username, email, password). Sans "
            "`X-Client-Type: mobile`, l'en-tête `X-CSRFToken` est exigé "
            "(token obtenu via GET /api/v1/auth/csrf_token/). Throttle : "
            "3 inscriptions/heure."
        ),
    )
    @action(detail=False, methods=['post'], throttle_classes=[ScopedRateThrottle])
    def register(self, request):
        is_mobile = request.headers.get("X-Client-Type") == "mobile"
        if not is_mobile:
            enforce_csrf(request)

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
    @extend_schema(
        request=TokenObtainPairSerializer,
        responses={200: AuthResponseSerializer},
        parameters=AUTH_HEADERS,
        description=(
            "Connexion par email + password. Sans `X-Client-Type: mobile`, "
            "l'en-tête `X-CSRFToken` est exigé. Throttle : 5 connexions/minute."
        ),
    )
    @action(detail=False, methods=["post"], throttle_classes=[ScopedRateThrottle])
    def login(self, request):
        is_mobile = request.headers.get("X-Client-Type") == "mobile"
        if not is_mobile:
            enforce_csrf(request)

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

    @extend_schema(
        request=GoogleAuthSerializer,
        responses={
            200: AuthResponseSerializer,
            201: AuthResponseSerializer,
            400: None,  # jeton invalide ou email non vérifié
            409: None,  # compte existant lié à un autre mode de connexion
        },
        parameters=AUTH_HEADERS,
        description=(
            "Connexion/inscription via Google : envoyer le `id_token` obtenu "
            "côté client (Google Identity Services). Throttle : 10/minute."
        ),
    )
    @action(detail=False, methods=["post"], throttle_classes=[ScopedRateThrottle])
    def google_oauth(self, request):
        is_mobile = request.headers.get("X-Client-Type") == "mobile"
        if not is_mobile:
            enforce_csrf(request)

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


    @extend_schema(
        request=LogoutSerializer,
        responses={200: None},
        parameters=AUTH_HEADERS,
        description=(
            "Révoque le refresh token (blacklist JWT). Mobile : token dans le "
            "corps `refresh` ; web : lu dans le cookie `refresh_token` (le "
            "cookie est supprimé de la réponse)."
        ),
    )
    @action( detail=False, methods=["post"], permission_classes=[AllowAny], authentication_classes=[])
    def logout(self, request):
        is_mobile = request.headers.get("X-Client-Type") == "mobile"
        if not is_mobile:
            enforce_csrf(request)
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
        return response

    # Pour refresh le token
    @extend_schema(
        request=RefreshSerializer,
        responses={200: RefreshResponseSerializer},
        parameters=AUTH_HEADERS,
        description=(
            "Échange un refresh token contre un nouvel access token. Mobile : "
            "refresh dans le corps ; web : lu dans le cookie `refresh_token` "
            "(`X-CSRFToken` exigé). Rotation : un nouveau refresh token est "
            "renvoyé si `ROTATE_REFRESH_TOKENS` est actif."
        ),
    )
    @action(detail=False, methods=["post"], permission_classes=[AllowAny], authentication_classes=[],throttle_classes=[ScopedRateThrottle],)
    def refresh(self, request):
        is_mobile = request.headers.get("X-Client-Type") == "mobile"

        # Pour verifier le token envoyer par le front-end des appareils depuis web, on va utiliser la fonction de django qui est dans le middleware de django pour verifier le csrf. On va l'utiliser seulement si c'est pas un mobile car pour le mobile, on ne va pas utiliser le cookie csrf mais plutot le token csrf qu'on va envoyer dans l'en-tete du front-end. Donc pour le mobile, on ne va pas verifier le csrf.
        if not is_mobile:
            enforce_csrf(request)
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

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError:
            return Response(
                {"detail": "Refresh token invalide ou révoqué."},
                status=status.HTTP_401_UNAUTHORIZED
            )

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
    @extend_schema(
        responses={200: CsrfTokenSerializer},
        description=(
            "Pose le cookie CSRF et renvoie le token à envoyer dans l'en-tête "
            "`X-CSRFToken` pour tout endpoint auth en mode web."
        ),
    )
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

class CategoryViewSet(ModelViewSet):
    serializer_class = CategorySerializer
    # prefetch chaîné : Category -> Notions -> Questions -> Answers (évite le N+1)
    queryset = Category.objects.prefetch_related('notion_set__question_set__answers')
    permission_classes = [IsAdminUser]


class DifficultyViewSet(ModelViewSet):
    serializer_class = DifficultySerializer
    queryset = Difficulty.objects.all()
    permission_classes = [IsAdminOrReadOnly]


class NotionViewSet(ModelViewSet):
    serializer_class = NotionSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        return Notion.objects.prefetch_related('question_set__answers')


class QuestionViewSet(ModelViewSet):
    serializer_class = QuestionSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = Question.objects.prefetch_related('answers')
        notion_id = self.request.query_params.get("notion")
        if notion_id:
            queryset = queryset.filter(notion_id=notion_id)
        return queryset


class AnswerViewSet(ModelViewSet):
    serializer_class = AdminAnswerSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = Answer.objects.all()
        question_id = self.request.query_params.get("question")
        if question_id:
            queryset = queryset.filter(question_id=question_id)
        return queryset


class TentativeQuestionViewSet(ModelViewSet):
    serializer_class = TentativeQuestionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # select_related : le serializer lit selected_answer.is_correct et question.explication
        base = TentativeQuestion.objects.select_related('question', 'selected_answer')
        # is_authenticated : pendant la génération du schéma OpenAPI, la
        # requête est anonyme — filter(user=AnonymousUser) lèverait une erreur.
        if not user.is_authenticated:
            return base.none()
        if user.is_staff:
            return base.order_by('-answered_at')
        # Un utilisateur ne voit que ses propres tentatives, les plus récentes d'abord
        return base.filter(user=user).order_by('-answered_at')

    def perform_create(self, serializer):
        tentative = serializer.save(user=self.request.user)
        if tentative.selected_answer and tentative.selected_answer.is_correct:
            Utilisateur.objects.filter(pk=self.request.user.pk).update(
                score=F('score') + 1
            )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        # Réponse enrichie pour le front : explication + bonne réponse
        tentative = serializer.instance
        bonne_reponse = tentative.question.answers.filter(is_correct=True).first()
        data = serializer.data
        data['explication'] = tentative.question.explication
        data['bonne_reponse'] = bonne_reponse.id if bonne_reponse else None

        return Response(data, status=status.HTTP_201_CREATED, headers=headers)