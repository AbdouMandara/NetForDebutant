from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from network.models import (
    Difficulty,
    Category,
    Notion,
    Question,
    Utilisateur,
    Answer,
    TentativeQuestion,
)


@admin.register(Difficulty)
class DifficultyAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Notion)
class NotionAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'category', 'is_published', 'created_at')
    list_filter = ('is_published', 'category')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'notion', 'difficulty', 'created_at')
    list_filter = ('difficulty', 'notion')
    search_fields = ('question_text',)


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('answer_text', 'question', 'is_correct')
    list_filter = ('is_correct',)
    search_fields = ('answer_text',)


@admin.register(TentativeQuestion)
class TentativeQuestionAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'selected_answer', 'answered_at')
    list_filter = ('answered_at',)
    readonly_fields = ('user', 'question', 'selected_answer', 'answered_at')


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ('email', 'username', 'score', 'is_staff', 'is_active', 'last_login')
    search_fields = ('email', 'username')
    ordering = ('email',)
    fieldsets = UserAdmin.fieldsets + (
        ('Réseau', {'fields': ('photo', 'google_sub', 'score')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
    )
