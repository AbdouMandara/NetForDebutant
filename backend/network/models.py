from django.db import models
import uuid
from django.contrib.auth.models import AbstractUser

# Create your models here.
    


class Difficulty(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.name

    
class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Notion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, null=True)
    is_published = models.BooleanField(default=False)
    photo = models.ImageField(
        upload_to="notions/photos/",
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    #Relationships
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    def __str__(self):
        return self.title


class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question_text = models.CharField(max_length=200)
    explication = models.TextField(blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Relationships
    notion = models.ForeignKey(Notion, on_delete=models.CASCADE)
    difficulty = models.ForeignKey(Difficulty, on_delete=models.CASCADE)

    def __str__(self):
        return self.question_text


class Utilisateur(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    photo = models.ImageField(
        upload_to="users/avatars/",
        blank=True,
        null=True
    )
    google_sub = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True
    )

    # Definition de "email" comme champ d'identification principal pour l'authentification
    USERNAME_FIELD = "email"
    # Indique que le champ "username" est requis lors de la création d'un utilisateur
    REQUIRED_FIELDS = ["username"]
    
    def __str__(self):
        return self.username
        

class Answer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    answer_text = models.CharField(max_length=200)
    is_correct = models.BooleanField(default=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.answer_text



class TentativeQuestion(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    user = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name="tentatives"
    )

    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name="tentatives"
    )

    selected_answer = models.ForeignKey(
        Answer,
        on_delete=models.PROTECT,
        related_name="tentatives"
    )

    answered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.question.question_text}"