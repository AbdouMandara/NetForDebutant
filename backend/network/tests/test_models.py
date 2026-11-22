# tests/test_models.py
#
# Tests unitaires des modèles du réseau.
# Lancer depuis backend/ :  python manage.py test network.tests.test_models

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from network.models import (
    Answer,
    Category,
    Difficulty,
    Notion,
    Question,
    TentativeQuestion,
    Utilisateur,
)


class CategoryModelTest(TestCase):
    
    # C'est ici qu'il y'aura notre test, pour voir la creation des categories
    def test_create_category(self):
        category = Category.objects.create(
            name="Réseaux informatiques"
        )
        
        # On verifie que ce qu'on a envoye est bien ca
        self.assertEqual(
            category.name,
            "Réseaux informatiques"
        )
        # On verifie qu'une condition est vraie ici que cette categorie qu'on vient de creer n'existait pas au prealable
        self.assertTrue(
            Category.objects.filter(id=category.id).exists()
        )

    def test_str_renvoie_le_nom(self):
        category = Category.objects.create(name="TCP/IP")
        self.assertEqual(str(category), "TCP/IP")

    def test_slug_unique(self):
        Category.objects.create(name="A", slug="commun")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(name="B", slug="commun")

    def test_dates_remplies_automatiquement(self):
        category = Category.objects.create(name="Datée", slug="datee")
        self.assertIsNotNone(category.created_at)
        self.assertIsNotNone(category.updated_at)

    def test_suppression_supprime_ses_notions(self):
        category = Category.objects.create(name="À supprimer", slug="a-supprimer")
        notion = Notion.objects.create(
            title="Orpheline", slug="orpheline", category=category
        )
        category.delete()
        self.assertFalse(Notion.objects.filter(pk=notion.pk).exists())


class QuizFixtureMixin:
    """Mini-quiz partagé : difficulté > catégorie > notion > question > 2 réponses."""

    def make_quiz(self):
        self.difficulty = Difficulty.objects.create(name="Facile")
        self.category = Category.objects.create(name="Réseau", slug="reseau")
        self.notion = Notion.objects.create(
            title="Le TCP", slug="le-tcp", category=self.category, is_published=True
        )
        self.question = Question.objects.create(
            question_text="TCP est-il fiable ?",
            explication="TCP garantit la livraison des paquets dans l'ordre.",
            notion=self.notion,
            difficulty=self.difficulty,
        )
        self.answer_ok = Answer.objects.create(
            answer_text="Oui", question=self.question, is_correct=True
        )
        self.answer_ko = Answer.objects.create(
            answer_text="Non", question=self.question, is_correct=False
        )


class DifficultyModelTest(TestCase):
    def test_create_difficulty_avec_uuid(self):
        difficulty = Difficulty.objects.create(name="Difficile")
        # Clé primaire UUID auto-générée
        self.assertIsNotNone(difficulty.id)
        self.assertEqual(str(difficulty.id).count("-"), 4)

    def test_str_renvoie_le_nom(self):
        self.assertEqual(str(Difficulty.objects.create(name="Moyen")), "Moyen")

    def test_nom_unique(self):
        Difficulty.objects.create(name="Facile")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Difficulty.objects.create(name="Facile")

    def test_description_optionnelle(self):
        difficulty = Difficulty.objects.create(name="Sans desc")
        self.assertIsNone(difficulty.description)


class NotionModelTest(QuizFixtureMixin, TestCase):
    def test_str_renvoie_le_titre(self):
        self.make_quiz()
        self.assertEqual(str(self.notion), "Le TCP")

    def test_is_published_par_defaut_false(self):
        notion = Notion.objects.create(
            title="Brouillon", slug="brouillon", category=Category.objects.create(name="C", slug="c")
        )
        self.assertFalse(notion.is_published)

    def test_categorie_requise(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Notion.objects.create(title="Sans catégorie", slug="sans-cat")

    def test_suppression_supprime_ses_questions(self):
        self.make_quiz()
        self.notion.delete()
        self.assertFalse(Question.objects.filter(pk=self.question.pk).exists())

    def test_tri_par_defaut_plus_recente_en_premier(self):
        self.make_quiz()
        ancienne = Notion.objects.create(
            title="Ancienne", slug="ancienne", category=self.category
        )
        Notion.objects.filter(pk=ancienne.pk).update(
            created_at=timezone.now() - timedelta(days=5)
        )
        titres = list(Notion.objects.values_list("title", flat=True))
        # La plus récente (Le TCP) doit passer avant l'ancienne
        self.assertEqual(titres[0], "Le TCP")
        self.assertEqual(titres[-1], "Ancienne")


class QuestionModelTest(QuizFixtureMixin, TestCase):
    def test_str_renvoie_le_texte(self):
        self.make_quiz()
        self.assertEqual(str(self.question), "TCP est-il fiable ?")

    def test_explication_requise(self):
        self.make_quiz()
        # blank=False : full_clean refuse une explication vide
        sans_explication = Question(
            question_text="Q sans explication",
            notion=self.notion,
            difficulty=self.difficulty,
        )
        with self.assertRaises(ValidationError):
            sans_explication.full_clean()

    def test_notion_et_difficulty_requises(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Question.objects.create(question_text="Orpheline", explication="E")

    def test_suppression_supprime_ses_reponses(self):
        self.make_quiz()
        self.question.delete()
        self.assertFalse(Answer.objects.filter(pk=self.answer_ok.pk).exists())

    def test_related_name_answers(self):
        self.make_quiz()
        self.assertEqual(self.question.answers.count(), 2)


class UtilisateurModelTest(TestCase):
    def test_str_renvoie_le_username(self):
        user = Utilisateur.objects.create_user(
            username="joueur", email="joueur@example.com", password="Passw0rd!2026"
        )
        self.assertEqual(str(user), "joueur")

    def test_score_par_defaut_zero(self):
        user = Utilisateur.objects.create_user(
            username="neuf", email="neuf@example.com", password="Passw0rd!2026"
        )
        self.assertEqual(user.score, 0)

    def test_email_comme_identifiant_principal(self):
        # Le cœur de l'auth : connexion par email, pas par username
        self.assertEqual(Utilisateur.USERNAME_FIELD, "email")
        self.assertEqual(Utilisateur.REQUIRED_FIELDS, ["username"])

    def test_email_unique(self):
        Utilisateur.objects.create_user(
            username="premier", email="dup@example.com", password="Passw0rd!2026"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Utilisateur.objects.create_user(
                    username="second", email="dup@example.com", password="Passw0rd!2026"
                )

    def test_password_hashé_et_non_en_clair(self):
        user = Utilisateur.objects.create_user(
            username="securise", email="securise@example.com", password="Passw0rd!2026"
        )
        self.assertNotEqual(user.password, "Passw0rd!2026")
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(user.check_password("Passw0rd!2026"))

    def test_google_sub_nullable(self):
        # Deux comptes sans Google peuvent coexister (NULL non unique en SQL)
        Utilisateur.objects.create_user(
            username="sans1", email="sans1@example.com", password="Passw0rd!2026"
        )
        Utilisateur.objects.create_user(
            username="sans2", email="sans2@example.com", password="Passw0rd!2026"
        )
        self.assertEqual(Utilisateur.objects.filter(google_sub__isnull=True).count(), 2)

    def test_google_sub_unique(self):
        Utilisateur.objects.create_user(
            username="g1", email="g1@example.com", password="Passw0rd!2026",
            google_sub="sub-123",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Utilisateur.objects.create_user(
                    username="g2", email="g2@example.com", password="Passw0rd!2026",
                    google_sub="sub-123",
                )


class AnswerModelTest(QuizFixtureMixin, TestCase):
    def test_str_renvoie_le_texte_de_la_reponse(self):
        self.make_quiz()
        self.assertEqual(str(self.answer_ok), "Oui")

    def test_is_correct_par_defaut_false(self):
        self.make_quiz()
        reponse = Answer.objects.create(answer_text="Peut-être", question=self.question)
        self.assertFalse(reponse.is_correct)

    def test_suppression_de_la_question_supprime_les_reponses(self):
        self.make_quiz()
        self.question.delete()
        self.assertEqual(Answer.objects.filter(question__isnull=True).count(), 0)

    def test_reponse_ne_peut_exister_sans_question(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Answer.objects.create(answer_text="Orpheline")


class TentativeQuestionModelTest(QuizFixtureMixin, TestCase):
    def setUp(self):
        self.make_quiz()
        self.user = Utilisateur.objects.create_user(
            username="joueur", email="joueur@example.com", password="Passw0rd!2026"
        )

    def test_str_combine_user_et_question(self):
        tentative = TentativeQuestion.objects.create(
            user=self.user, question=self.question, selected_answer=self.answer_ok
        )
        self.assertEqual(str(tentative), "joueur - TCP est-il fiable ?")

    def test_answered_at_rempli_automatiquement(self):
        tentative = TentativeQuestion.objects.create(
            user=self.user, question=self.question, selected_answer=self.answer_ok
        )
        self.assertIsNotNone(tentative.answered_at)

    def test_question_protegee_par_les_tentatives(self):
        """Une question déjà tentée ne doit pas pouvoir être supprimée."""
        TentativeQuestion.objects.create(
            user=self.user, question=self.question, selected_answer=self.answer_ok
        )
        with self.assertRaises(ProtectedError):
            with transaction.atomic():
                self.question.delete()

    def test_reponse_protegee_par_les_tentatives(self):
        """Une réponse utilisée ne doit pas pouvoir être supprimée."""
        TentativeQuestion.objects.create(
            user=self.user, question=self.question, selected_answer=self.answer_ok
        )
        with self.assertRaises(ProtectedError):
            with transaction.atomic():
                self.answer_ok.delete()

    def test_suppression_du_user_supprime_ses_tentatives(self):
        TentativeQuestion.objects.create(
            user=self.user, question=self.question, selected_answer=self.answer_ok
        )
        self.user.delete()
        self.assertEqual(TentativeQuestion.objects.count(), 0)

    def test_related_names_des_tentatives(self):
        TentativeQuestion.objects.create(
            user=self.user, question=self.question, selected_answer=self.answer_ok
        )
        self.assertEqual(self.user.tentatives.count(), 1)
        self.assertEqual(self.question.tentatives.count(), 1)
        self.assertEqual(self.answer_ok.tentatives.count(), 1)


class ModelOrderingTest(TestCase):
    """Verrouille les Meta.ordering ajoutés pour la pagination (option A)."""

    def test_ordering_de_tous_les_modeles(self):
        self.assertEqual(Difficulty._meta.ordering, ["name"])
        self.assertEqual(Category._meta.ordering, ["name"])
        self.assertEqual(Notion._meta.ordering, ["-created_at"])
        self.assertEqual(Question._meta.ordering, ["-created_at"])
        self.assertEqual(Answer._meta.ordering, ["created_at"])
        self.assertEqual(TentativeQuestion._meta.ordering, ["-answered_at"])
