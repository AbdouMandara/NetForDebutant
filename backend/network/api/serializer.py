from network.models import Category, Notion, Question, Utilisateur, Answer, Difficulty, TentativeQuestion
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_spectacular.utils import extend_schema_field


class UtilisateurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Utilisateur
        fields = ['username', 'email', 'photo', 'score', 'date_joined', 'last_login', 'is_active']
        read_only_fields = ['id']

class DifficultySerializer(serializers.ModelSerializer):
    class Meta:
        model = Difficulty
        fields = ['id', 'name', 'description']
        read_only_fields = ['id']


class AnswerSerializer(serializers.ModelSerializer):
    """Serializer public : n'expose PAS is_correct (le front ne doit pas
    pouvoir tricher en amont ; la correction passe par POST /tentatives/)."""
    class Meta:
        model = Answer
        fields = ['id', 'answer_text', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class QuestionSerializer(serializers.ModelSerializer):
    answers = serializers.SerializerMethodField()
    class Meta:
        model = Question
        fields = ['id', 'question_text', 'explication', 'notion', 'created_at', 'updated_at', 'answers', 'difficulty']
        read_only_fields = ['id', 'created_at', 'updated_at']

    @extend_schema_field(AnswerSerializer(many=True))
    def get_answers(self, obj):
        answers = obj.answers.all() # je mets answer car j'ai mis related_name='answers' dans le modèle Answer pour la relation ForeignKey avec Question
        serializer = AnswerSerializer(answers, many=True)
        return serializer.data

    def get_difficulty_of_question(self, obj):
        difficulty = obj.difficulty
        serializer = DifficultySerializer(difficulty)
        return serializer.data


class NotionSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    class Meta:
        model = Notion
        fields = ['id', 'title', 'slug', 'description', 'category', 'is_published', 'photo', 'created_at', 'updated_at', 'questions']
        read_only_fields = ['id', 'created_at', 'updated_at']

    @extend_schema_field(QuestionSerializer(many=True))
    def get_questions(self, obj):
        questions = obj.question_set.all()
        serializer = QuestionSerializer(questions, many=True)
        return serializer.data


class CategorySerializer(serializers.ModelSerializer):
    notions = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['name', 'description', 'slug', 'created_at', 'updated_at', 'notions']
        read_only_fields = ['id', 'created_at', 'updated_at']

    @extend_schema_field(NotionSerializer(many=True))
    def get_notions(self, obj):
        notions = obj.notion_set.all()
        serializer = NotionSerializer(notions, many=True)
        return serializer.data


class AdminAnswerSerializer(serializers.ModelSerializer):
    """AnswerViewSet : permet à l'admin de créer/éditer avec question et is_correct.

    is_correct est retiré de la réponse pour les non-admins : seul l'admin
    doit voir quelle réponse est la bonne.
    """
    class Meta:
        model = Answer
        fields = ['id', 'answer_text', 'question', 'is_correct', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request is not None and not request.user.is_staff:
            data.pop('is_correct', None)
        return data

class TentativeQuestionSerializer(serializers.ModelSerializer):
    is_correct = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TentativeQuestion
        fields = ['id', 'question', 'selected_answer', 'answered_at', 'is_correct']
        read_only_fields = ['id', 'answered_at', 'is_correct']

    @extend_schema_field(serializers.BooleanField())
    def get_is_correct(self, obj):
        return obj.selected_answer.is_correct if obj.selected_answer else False

    def validate(self, data):
        selected_answer = data.get('selected_answer') or getattr(self.instance, 'selected_answer', None)
        question = data.get('question') or getattr(self.instance, 'question', None)

        if question and selected_answer and selected_answer.question_id != question.id:
            raise serializers.ValidationError(
                {"selected_answer": "Cette réponse n'appartient pas à la question sélectionnée."}
            )

        return data


class NotionRefSerializer(serializers.Serializer):
    """Référence courte d'une notion (id, titre, slug) dans les réponses calculées."""
    id = serializers.CharField()
    title = serializers.CharField()
    slug = serializers.CharField()


class NotionProgressionSerializer(serializers.Serializer):
    """Progression d'un apprenant sur UNE notion.

    Ce n'est pas un modèle : les valeurs sont calculées à la volée à partir de
    TentativeQuestion (voir UserViewSet.ma_progression).
    """
    notion = serializers.SerializerMethodField()
    questions_total = serializers.IntegerField()
    questions_tentees = serializers.IntegerField()
    questions_reussies = serializers.IntegerField()
    progression = serializers.FloatField()
    est_maitrisee = serializers.BooleanField()

    @extend_schema_field(NotionRefSerializer())
    def get_notion(self, obj):
        return obj.get('notion')


# Serializer pour l'auth (celui de base pour l'inscription et la connexion a travers oAUth de Google, pour le login, refresh token, logout etc, on va utiliser les serializer du package django-rest-framework-simplejwt)

class RegisterSerializer(serializers.ModelSerializer):

    # Je declare Mes regles de validation personnalisees ici
    password = serializers.CharField(
        write_only=True, #Ce n'est pas pour la lecture donc l'api ne l'expose pas, seulement pour l'ecriture
        validators=[validate_password], #Je mets la fonction de validation de mot de passe de Django pour que le mot de passe respecte les regles de securite
    )

    class Meta:
        model = Utilisateur
        fields = ['id', 'username', 'email','password']
        read_only_fields = ['id']

    def create(self, validated_data):
        return Utilisateur.objects.create_user(**validated_data)


class GoogleAuthSerializer(serializers.Serializer):
    # On prend ca car c'est ce que Google nous renvoie apres l'authentification de l'utilisateur
    id_token = serializers.CharField(
        write_only=True,
        trim_whitespace=True #supprimer automatiquement les espaces au début et à la fin de la valeur reçue
    )


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        write_only=True,
        trim_whitespace=True,
    )

    def validate_refresh(self, value):
        try:
            self.token = RefreshToken(value)
        except TokenError:
            raise serializers.ValidationError(
                "Le refresh token est invalide ou expiré."
            )
        return value

    def save(self, **kwargs):
        self.token.blacklist()


# ---------------------------------------------------------------------------
# Serializers de documentation (drf-spectacular) : décrivent les réponses
# calculées à la volée par les endpoints auth / stats.
# ---------------------------------------------------------------------------

class AuthUserSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()


class AuthResponseSerializer(serializers.Serializer):
    """Réponse commune de register / login / google_oauth.

    `refresh` n'est présent que pour les clients mobiles (en-tête
    `X-Client-Type: mobile`) : le web reçoit le refresh token dans le cookie
    `refresh_token` (httpOnly, chemin /api/v1/auth/).
    """
    message = serializers.CharField()
    user = AuthUserSerializer()
    access = serializers.CharField()
    refresh = serializers.CharField(required=False)


class RefreshSerializer(serializers.Serializer):
    """Corps de POST /auth/refresh/ côté mobile.

    Côté web, le refresh token est lu dans le cookie `refresh_token` et le
    corps de requête peut être vide.
    """
    refresh = serializers.CharField(write_only=True, required=False)


class RefreshResponseSerializer(serializers.Serializer):
    """Réponse de /auth/refresh/ : access (+ refresh si rotation activée)."""
    access = serializers.CharField()
    refresh = serializers.CharField(required=False)


class CsrfTokenSerializer(serializers.Serializer):
    """Réponse de GET /auth/csrf_token/ : à renvoyer dans l'en-tête X-CSRFToken."""
    csrfToken = serializers.CharField()


class MesStatistiquesSerializer(serializers.Serializer):
    """Réponse de GET /users/mes-statistiques/."""
    score = serializers.IntegerField()
    total_tentatives = serializers.IntegerField()
    reponses_correctes = serializers.IntegerField()
    reponses_incorrectes = serializers.IntegerField()
    taux_reussite = serializers.FloatField()