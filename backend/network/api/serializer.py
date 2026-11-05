from network.models import Category, Notion, Question, Utilisateur, Answer, Difficulty, TentativeQuestion
from rest_framework import serializers

class UtilisateurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Utilisateur
        fields = ['id', 'username', 'email', 'photo']
        read_only_fields = ['id']

class NotionSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    class Meta:
        model = Notion
        fields = ['id', 'title', 'slug', 'description', 'is_published', 'photo', 'created_at', 'updated_at', 'questions']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_questions_of_notion(self, obj):
        questions = obj.question_set.all()
        serializer = QuestionSerializer(questions, many=True)
        return serializer.data


class CategorySerializer(serializers.ModelSerializer):
    notions = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['name', 'description', 'slug', 'created_at', 'updated_at', 'notions']
        read_only_fields = ['id', 'created_at', 'updated_at']
    def get_notions_of_category(self, obj):
        notions = obj.notion_set.all()
        serializer = NotionSerializer(notions, many=True)
        return serializer.data

class DifficultySerializer(serializers.ModelSerializer):
    class Meta:
        model = Difficulty
        fields = ['id', 'name', 'description']
        read_only_fields = ['id']

class QuestionSerializer(serializers.ModelSerializer):
    answers = serializers.SerializerMethodField()
    class Meta:
        model = Question
        fields = ['id', 'question_text', 'explication', 'created_at', 'updated_at', 'answers', 'difficulty']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_answers_of_question(self, obj):
        answers = obj.answers.all() # je mets answer car j'ai mis related_name='answers' dans le modèle Answer pour la relation ForeignKey avec Question
        serializer = AnswerSerializer(answers, many=True)
        return serializer.data

    def get_difficulty_of_question(self, obj):
        difficulty = obj.difficulty
        serializer = DifficultySerializer(difficulty)
        return serializer.data
    
class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ['id', 'answer_text', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class TentativeQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TentativeQuestion
        fields = ['id', 'user', 'question', 'selected_answer', 'created_at']
        read_only_fields = ['id', 'created_at']