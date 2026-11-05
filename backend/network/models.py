from django.db import models
import uuid
from django.utils import timezone

# Create your models here.
class Difficulty(models.Model):
    EASY = 'Easy', 'Easy'
    MEDIUM = 'Medium', 'Medium'
    HARD = 'Hard', 'Hard'

class Notion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, null=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question_text = models.CharField(max_length=200)
    explication = models.TextField(blank=False, null=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # Relationships
    notion = models.ForeignKey(Notion, on_delete=models.CASCADE)
    difficulty = models.ForeignKey(Difficulty, on_delete=models.CASCADE)

    def __str__(self):
        return self.question_text


class Answer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    answer_text = models.CharField(max_length=200)
    is_correct = models.BooleanField(default=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.answer_text