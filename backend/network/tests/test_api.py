"""Tests de l'API Network.

Lancer depuis backend/ (venv activé) :
    python manage.py test network

Chaque test est isolé dans une transaction (rollback automatique) :
aucune donnée n'est laissée en base après l'exécution.
"""
import json
from datetime import timedelta

from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from network.models import (
    Answer,
    Category,
    Difficulty,
    Notion,
    Question,
    TentativeQuestion,
    Utilisateur,
)

BASE = "/api/v1"
PASSWORD = "Passw0rd!2026"


class APITestCase(TestCase):
    """Base commune : helpers d'authentification et fixtures de quiz."""

    def setUp(self):
        # Les compteurs de throttling vivent dans le cache : on les remet à
        # zéro pour qu'un test ne throttle pas le test suivant.
        cache.clear()
        # Le test client désactive le CSRF par défaut (flag interne
        # _dont_enforce_csrf_checks) : sans cela, les tests de sécurité CSRF
        # passeraient toujours, quel que soit le code.
        self.client = Client(enforce_csrf_checks=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def make_user(self, email, is_staff=False, username=None):
        return Utilisateur.objects.create_user(
            username=username or email.split("@")[0],
            email=email,
            password=PASSWORD,
            is_staff=is_staff,
        )

    def auth(self, user):
        """En-tête Authorization simulant l'utilisateur connecté."""
        token = str(RefreshToken.for_user(user).access_token)
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def mobile(self):
        """Header qui désactive la vérification CSRF côté API."""
        return {"HTTP_X_CLIENT_TYPE": "mobile"}

    def get_csrf(self):
        """Récupère le token CSRF (requis pour toute requête web)."""
        r = self.client.get(f"{BASE}/auth/csrf_token/")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["csrfToken"]

    def post(self, url, data, **headers):
        """POST JSON (le content_type est géré automatiquement)."""
        return self.client.post(
            url, data=json.dumps(data), content_type="application/json", **headers
        )

    def make_quiz(self):
        """Crée un mini-quiz : difficulté > catégorie > notion > question > 2 réponses."""
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

    def make_tentative(self, user, answer, question=None, days_ago=0):
        tentative = TentativeQuestion.objects.create(
            user=user,
            question=question or self.question,
            selected_answer=answer,
        )
        if days_ago:
            TentativeQuestion.objects.filter(pk=tentative.pk).update(
                answered_at=timezone.now() - timedelta(days=days_ago)
            )
        return tentative


# ======================================================================
# Authentification
# ======================================================================
class AuthTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user("alice@example.com")

    # --- CSRF -------------------------------------------------------
    def test_endpoint_csrf_renvoie_un_token_et_pose_le_cookie(self):
        r = self.client.get(f"{BASE}/auth/csrf_token/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("csrfToken", r.json())
        self.assertIn("csrftoken", r.cookies)

    # --- Inscription ------------------------------------------------
    def test_inscription_web_sans_csrf_refusee(self):
        r = self.post(
            f"{BASE}/auth/register/",
            {"username": "bob", "email": "bob@example.com", "password": PASSWORD},
        )
        self.assertEqual(r.status_code, 403)

    def test_inscription_web_avec_csrf_reussie(self):
        r = self.post(
            f"{BASE}/auth/register/",
            {"username": "bob", "email": "bob@example.com", "password": PASSWORD},
            HTTP_X_CSRFTOKEN=self.get_csrf(),
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIn("access", r.json())
        self.assertIn("refresh_token", r.cookies)
        self.assertTrue(Utilisateur.objects.filter(email="bob@example.com").exists())

    def test_inscription_mobile_renvoie_les_tokens_dans_le_corps(self):
        r = self.post(
            f"{BASE}/auth/register/",
            {"username": "carol", "email": "carol@example.com", "password": PASSWORD},
            **self.mobile(),
        )
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertIn("access", body)
        self.assertIn("refresh", body)
        # Mobile : pas de cookie, tout est dans le corps
        self.assertNotIn("refresh_token", r.cookies)

    def test_inscription_email_deja_utilise_refusee(self):
        r = self.post(
            f"{BASE}/auth/register/",
            {"username": "intrus", "email": "alice@example.com", "password": PASSWORD},
            **self.mobile(),
        )
        self.assertEqual(r.status_code, 400)

    # --- Connexion --------------------------------------------------
    def test_connexion_reussie(self):
        r = self.post(
            f"{BASE}/auth/login/",
            {"email": "alice@example.com", "password": PASSWORD},
            **self.mobile(),
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("access", r.json())

    def test_connexion_mdp_incorrect_refusee(self):
        r = self.post(
            f"{BASE}/auth/login/",
            {"email": "alice@example.com", "password": "mauvais"},
            **self.mobile(),
        )
        self.assertEqual(r.status_code, 401)

    def test_login_web_sans_csrf_refuse(self):
        r = self.post(
            f"{BASE}/auth/login/",
            {"email": "alice@example.com", "password": PASSWORD},
        )
        self.assertEqual(r.status_code, 403)

    def test_login_web_avec_csrf_reussi(self):
        r = self.post(
            f"{BASE}/auth/login/",
            {"email": "alice@example.com", "password": PASSWORD},
            HTTP_X_CSRFTOKEN=self.get_csrf(),
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("refresh_token", r.cookies)

    # --- Refresh ----------------------------------------------------
    def test_refresh_web_renouvelle_les_tokens(self):
        r = self.post(
            f"{BASE}/auth/login/",
            {"email": "alice@example.com", "password": PASSWORD},
            HTTP_X_CSRFTOKEN=self.get_csrf(),
        )
        self.assertEqual(r.status_code, 200)

        # Le cookie refresh_token (posé par le login) est renvoyé automatiquement
        r = self.post(f"{BASE}/auth/refresh/", {}, HTTP_X_CSRFTOKEN=self.get_csrf())
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("access", r.json())
        self.assertIn("refresh_token", r.cookies)

    def test_refresh_sans_token_refuse(self):
        r = self.post(f"{BASE}/auth/refresh/", {}, **self.mobile())
        self.assertEqual(r.status_code, 400)

    def test_refresh_mobile_renvoie_les_tokens_dans_le_corps(self):
        r = self.post(
            f"{BASE}/auth/login/",
            {"email": "alice@example.com", "password": PASSWORD},
            **self.mobile(),
        )
        refresh = r.json()["refresh"]

        r = self.post(f"{BASE}/auth/refresh/", {"refresh": refresh}, **self.mobile())
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("access", r.json())
        self.assertIn("refresh", r.json())

    # --- Déconnexion ------------------------------------------------
    def test_logout_web_supprime_le_cookie(self):
        r = self.post(
            f"{BASE}/auth/login/",
            {"email": "alice@example.com", "password": PASSWORD},
            HTTP_X_CSRFTOKEN=self.get_csrf(),
        )
        self.assertEqual(r.status_code, 200)

        r = self.post(f"{BASE}/auth/logout/", {}, HTTP_X_CSRFTOKEN=self.get_csrf())
        self.assertEqual(r.status_code, 200, r.content)
        # delete_cookie : morsel présent mais valeur vidée
        self.assertIn("refresh_token", r.cookies)
        self.assertEqual(r.cookies["refresh_token"].value, "")

    def test_logout_mobile_revoque_le_refresh(self):
        r = self.post(
            f"{BASE}/auth/login/",
            {"email": "alice@example.com", "password": PASSWORD},
            **self.mobile(),
        )
        refresh = r.json()["refresh"]

        r = self.post(f"{BASE}/auth/logout/", {"refresh": refresh}, **self.mobile())
        self.assertEqual(r.status_code, 200, r.content)

        # Le refresh blacklisté ne doit plus fonctionner
        r = self.post(f"{BASE}/auth/refresh/", {"refresh": refresh}, **self.mobile())
        self.assertEqual(r.status_code, 401)


# ======================================================================
# Permissions : IsAdminOrReadOnly sur Difficulty/Notion/Question/Answer
# ======================================================================
class PermissionTests(APITestCase):
    # Les 4 viewsets soumis à IsAdminOrReadOnly
    ADMIN_ONLY = ["difficulties", "notions", "questions", "answers"]

    def setUp(self):
        super().setUp()
        self.make_quiz()
        self.user = self.make_user("lecteur@example.com")
        self.admin = self.make_user("admin@example.com", is_staff=True)

    def payload_for(self, endpoint):
        """Payload de création valide pour chaque endpoint."""
        return {
            "difficulties": {"name": "Difficile"},
            "notions": {"title": "UDP", "slug": "udp", "category": str(self.category.id)},
            "questions": {
                "question_text": "UDP est-il fiable ?",
                "explication": "UDP ne garantit pas la livraison.",
                "notion": str(self.notion.id),
                "difficulty": str(self.difficulty.id),
            },
            "answers": {
                "answer_text": "Peut-être",
                "question": str(self.question.id),
                "is_correct": True,
            },
        }[endpoint]

    def test_lecture_anonyme_refusee(self):
        for endpoint in self.ADMIN_ONLY:
            r = self.client.get(f"{BASE}/{endpoint}/")
            self.assertEqual(r.status_code, 401, endpoint)

    def test_lecture_connectee_autorisee(self):
        for endpoint in self.ADMIN_ONLY:
            r = self.client.get(f"{BASE}/{endpoint}/", **self.auth(self.user))
            self.assertEqual(r.status_code, 200, endpoint)

    def test_ecriture_non_admin_refusee(self):
        for endpoint in self.ADMIN_ONLY:
            r = self.post(f"{BASE}/{endpoint}/", {}, **self.auth(self.user))
            self.assertEqual(r.status_code, 403, endpoint)

    def test_modification_non_admin_refusee(self):
        for endpoint, obj in [
            ("difficulties", self.difficulty),
            ("notions", self.notion),
            ("questions", self.question),
            ("answers", self.answer_ok),
        ]:
            r = self.client.patch(
                f"{BASE}/{endpoint}/{obj.id}/",
                data=json.dumps({"id": str(obj.id)}),
                content_type="application/json",
                **self.auth(self.user),
            )
            self.assertEqual(r.status_code, 403, endpoint)

    def test_suppression_non_admin_refusee(self):
        r = self.client.delete(
            f"{BASE}/difficulties/{self.difficulty.id}/", **self.auth(self.user)
        )
        self.assertEqual(r.status_code, 403)

    def test_creation_admin_autorisee(self):
        for endpoint in self.ADMIN_ONLY:
            r = self.post(f"{BASE}/{endpoint}/", self.payload_for(endpoint), **self.auth(self.admin))
            self.assertEqual(r.status_code, 201, f"{endpoint}: {r.content}")

    def test_suppression_admin_autorisee(self):
        r = self.client.delete(
            f"{BASE}/difficulties/{self.difficulty.id}/", **self.auth(self.admin)
        )
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Difficulty.objects.filter(pk=self.difficulty.id).exists())

    def test_anonyme_ne_peut_pas_ecrire(self):
        r = self.post(f"{BASE}/difficulties/", {"name": "X"})
        self.assertEqual(r.status_code, 401)

    # --- Catégorie : réservée à l'admin (IsAdminUser) ---------------
    def test_categories_lues_uniquement_par_ladmin(self):
        r = self.client.get(f"{BASE}/categories/", **self.auth(self.user))
        self.assertEqual(r.status_code, 403)

        r = self.client.get(f"{BASE}/categories/", **self.auth(self.admin))
        self.assertEqual(r.status_code, 200)

    def test_user_non_admin_ne_peut_pas_creer_de_user(self):
        r = self.post(
            f"{BASE}/users/",
            {"username": "x", "email": "x@example.com"},
            **self.auth(self.user),
        )
        self.assertEqual(r.status_code, 403)


# ======================================================================
# Tentatives : réponse à une question
# ======================================================================
class TentativeTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.make_quiz()
        self.user = self.make_user("joueur@example.com")

    def answer(self, selected, **extra):
        return self.post(
            f"{BASE}/tentatives/",
            {"question": str(self.question.id), "selected_answer": str(selected.id)},
            **{**self.auth(self.user), **self.mobile(), **extra},
        )

    def test_reponse_correcte_reussie(self):
        r = self.answer(self.answer_ok)
        self.assertEqual(r.status_code, 201, r.content)
        data = r.json()
        self.assertTrue(data["is_correct"])
        self.assertIn("answered_at", data)
        self.assertNotIn("user", data)  # l'utilisateur n'est pas exposé

    def test_reponse_incorrecte_reussie(self):
        r = self.answer(self.answer_ko)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertFalse(r.json()["is_correct"])

    def test_reponse_enrichie_avec_explication_et_bonne_reponse(self):
        r = self.answer(self.answer_ko)
        data = r.json()
        self.assertEqual(data["explication"], self.question.explication)
        self.assertEqual(data["bonne_reponse"], str(self.answer_ok.id))

    def test_score_incremente_si_reponse_correcte(self):
        self.answer(self.answer_ok)
        self.user.refresh_from_db()
        self.assertEqual(self.user.score, 1)

    def test_score_inchange_si_reponse_incorrecte(self):
        self.answer(self.answer_ko)
        self.user.refresh_from_db()
        self.assertEqual(self.user.score, 0)

    def test_reponse_dune_autre_question_refusee(self):
        """La réponse choisie doit appartenir à la question posée."""
        autre_question = Question.objects.create(
            question_text="Autre question ?",
            explication="Explication.",
            notion=self.notion,
            difficulty=self.difficulty,
        )
        r = self.post(
            f"{BASE}/tentatives/",
            {
                "question": str(autre_question.id),
                "selected_answer": str(self.answer_ok.id),  # appartient à self.question
            },
            **{**self.auth(self.user), **self.mobile()},
        )
        self.assertEqual(r.status_code, 400)

    def test_plusieurs_tentatives_sur_la_meme_question_autorisees(self):
        self.assertEqual(self.answer(self.answer_ok).status_code, 201)
        self.assertEqual(self.answer(self.answer_ko).status_code, 201)

    def test_anonyme_refuse(self):
        r = self.post(
            f"{BASE}/tentatives/",
            {"question": str(self.question.id), "selected_answer": str(self.answer_ok.id)},
            **self.mobile(),
        )
        self.assertEqual(r.status_code, 401)

    # --- Historique -------------------------------------------------
    def test_historique_ne_contient_que_ses_tentatives(self):
        autre_user = self.make_user("autre@example.com")
        self.make_tentative(self.user, self.answer_ok)
        self.make_tentative(autre_user, self.answer_ko)

        r = self.client.get(f"{BASE}/tentatives/", **self.auth(self.user))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["count"], 1)

    def test_historique_trie_par_date_decroissante(self):
        ancienne = self.make_tentative(self.user, self.answer_ko, days_ago=2)
        recente = self.make_tentative(self.user, self.answer_ok)

        r = self.client.get(f"{BASE}/tentatives/", **self.auth(self.user))
        ids = [t["id"] for t in r.json()["results"]]
        self.assertEqual(ids, [str(recente.id), str(ancienne.id)])

    def test_historique_pagine(self):
        for _ in range(25):
            self.make_tentative(self.user, self.answer_ko)

        r = self.client.get(f"{BASE}/tentatives/", **self.auth(self.user))
        data = r.json()
        self.assertEqual(data["count"], 25)
        self.assertEqual(len(data["results"]), 20)  # PAGE_SIZE
        self.assertIsNotNone(data["next"])

        r = self.client.get(f"{BASE}/tentatives/?page=2", **self.auth(self.user))
        self.assertEqual(len(r.json()["results"]), 5)

    def test_historique_taille_de_page_parametrable(self):
        for _ in range(7):
            self.make_tentative(self.user, self.answer_ko)

        r = self.client.get(
            f"{BASE}/tentatives/?page_size=3", **self.auth(self.user)
        )
        data = r.json()
        self.assertEqual(len(data["results"]), 3)
        self.assertEqual(data["count"], 7)

    def test_admin_voit_toutes_les_tentatives(self):
        autre_user = self.make_user("autre@example.com")
        self.make_tentative(self.user, self.answer_ok)
        self.make_tentative(autre_user, self.answer_ko)
        admin = self.make_user("admin@example.com", is_staff=True)

        r = self.client.get(f"{BASE}/tentatives/", **self.auth(admin))
        self.assertEqual(r.json()["count"], 2)


# ======================================================================
# Statistiques personnelles
# ======================================================================
class StatsTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.make_quiz()
        self.user = self.make_user("joueur@example.com")

    def get_stats(self, user=None):
        return self.client.get(
            f"{BASE}/users/mes-statistiques/", **self.auth(user or self.user)
        )

    def test_stats_sans_tentative(self):
        r = self.get_stats()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.json(),
            {
                "score": 0,
                "total_tentatives": 0,
                "reponses_correctes": 0,
                "reponses_incorrectes": 0,
                "taux_reussite": 0,
            },
        )

    def test_stats_avec_tentatives(self):
        self.make_tentative(self.user, self.answer_ok)
        self.make_tentative(self.user, self.answer_ok)
        self.make_tentative(self.user, self.answer_ko)
        # Le score n'est incrémenté que par l'API : on le aligne ici
        Utilisateur.objects.filter(pk=self.user.pk).update(score=2)

        data = self.get_stats().json()
        self.assertEqual(data["score"], 2)
        self.assertEqual(data["total_tentatives"], 3)
        self.assertEqual(data["reponses_correctes"], 2)
        self.assertEqual(data["reponses_incorrectes"], 1)
        self.assertEqual(data["taux_reussite"], 66.67)

    def test_stats_isolees_par_utilisateur(self):
        autre_user = self.make_user("autre@example.com")
        self.make_tentative(autre_user, self.answer_ok)

        data = self.get_stats().json()
        self.assertEqual(data["total_tentatives"], 0)

    def test_stats_anonyme_refusee(self):
        r = self.client.get(f"{BASE}/users/mes-statistiques/")
        self.assertEqual(r.status_code, 401)


# ======================================================================
# Progression par notion
# ======================================================================
class ProgressionTests(APITestCase):
    def setUp(self):
        super().setUp()
        # make_quiz crée une notion publiée "le-tcp" avec UNE question
        self.make_quiz()
        self.user = self.make_user("joueur@example.com")

    def get_progression(self, user=None, query=""):
        return self.client.get(
            f"{BASE}/users/ma-progression/{query}", **self.auth(user or self.user)
        )

    def add_questions(self, n):
        """Ajoute n questions (chacune avec 1 bonne + 1 mauvaise réponse) à la notion."""
        questions = []
        for i in range(n):
            q = Question.objects.create(
                question_text=f"Question {i} ?",
                explication=f"Explication {i}.",
                notion=self.notion,
                difficulty=self.difficulty,
            )
            Answer.objects.create(answer_text="Bonne", question=q, is_correct=True)
            Answer.objects.create(answer_text="Mauvaise", question=q, is_correct=False)
            questions.append(q)
        return questions

    def repondre(self, user, question, juste=True):
        reponse = question.answers.get(is_correct=juste)
        return self.make_tentative(user, reponse, question=question)

    def by_slug(self, data, slug):
        return next(d for d in data if d["notion"]["slug"] == slug)

    def test_structure_de_la_reponse(self):
        data = self.get_progression().json()
        self.assertEqual(len(data), 1)  # une seule notion publiée
        d = data[0]
        self.assertEqual(
            set(d.keys()),
            {
                "notion", "questions_total", "questions_tentees",
                "questions_reussies", "progression", "est_maitrisee",
            },
        )
        self.assertEqual(set(d["notion"].keys()), {"id", "title", "slug"})
        self.assertEqual(d["notion"]["slug"], "le-tcp")

    def test_progression_sans_tentative(self):
        d = self.by_slug(self.get_progression().json(), "le-tcp")
        self.assertEqual(d["questions_total"], 1)
        self.assertEqual(d["questions_tentees"], 0)
        self.assertEqual(d["questions_reussies"], 0)
        self.assertEqual(d["progression"], 0.0)
        self.assertFalse(d["est_maitrisee"])

    def test_progression_totale_maitrisee(self):
        self.repondre(self.user, self.question, juste=True)
        d = self.by_slug(self.get_progression().json(), "le-tcp")
        self.assertEqual(d["questions_reussies"], 1)
        self.assertEqual(d["progression"], 100.0)
        self.assertTrue(d["est_maitrisee"])

    def test_progression_partielle(self):
        self.add_questions(3)  # total = 4 questions dans la notion
        self.repondre(self.user, self.question, juste=True)  # 1/4
        d = self.by_slug(self.get_progression().json(), "le-tcp")
        self.assertEqual(d["questions_total"], 4)
        self.assertEqual(d["questions_tentees"], 1)
        self.assertEqual(d["questions_reussies"], 1)
        self.assertEqual(d["progression"], 25.0)
        self.assertFalse(d["est_maitrisee"])

    def test_question_reussie_meme_si_derniere_fausse(self):
        """Règle « >= 1 bonne réponse » : une rataj du jour ne dégrade pas."""
        self.repondre(self.user, self.question, juste=True)
        self.repondre(self.user, self.question, juste=False)  # 2e tentative, fausse
        d = self.by_slug(self.get_progression().json(), "le-tcp")
        self.assertEqual(d["questions_tentees"], 1)
        self.assertEqual(d["questions_reussies"], 1)
        self.assertEqual(d["progression"], 100.0)
        self.assertTrue(d["est_maitrisee"])

    def test_seuil_par_defaut_est_70(self):
        nouvelles = self.add_questions(9)  # total = 10

        # 6 réussies sur 10 = 60 % -> sous le seuil
        self.repondre(self.user, self.question, juste=True)
        for q in nouvelles[:5]:
            self.repondre(self.user, q, juste=True)
        d = self.by_slug(self.get_progression().json(), "le-tcp")
        self.assertEqual(d["progression"], 60.0)
        self.assertFalse(d["est_maitrisee"])

        # 7e réussite -> 70 % exact -> maîtrisée (frontière incluse)
        self.repondre(self.user, nouvelles[5], juste=True)
        d = self.by_slug(self.get_progression().json(), "le-tcp")
        self.assertEqual(d["progression"], 70.0)
        self.assertTrue(d["est_maitrisee"])

    def test_seuil_parametre_frontiere(self):
        self.add_questions(3)  # total = 4
        self.repondre(self.user, self.question, juste=True)  # 25 %

        d = self.by_slug(self.get_progression(query="?seuil=25").json(), "le-tcp")
        self.assertTrue(d["est_maitrisee"])  # 25 >= 25
        d = self.by_slug(self.get_progression(query="?seuil=26").json(), "le-tcp")
        self.assertFalse(d["est_maitrisee"])  # 25 < 26

    def test_seuil_non_numerique_refuse(self):
        self.assertEqual(self.get_progression(query="?seuil=abc").status_code, 400)

    def test_seuil_hors_limites_refuse(self):
        self.assertEqual(self.get_progression(query="?seuil=150").status_code, 400)
        self.assertEqual(self.get_progression(query="?seuil=-10").status_code, 400)

    def test_isolation_entre_utilisateurs(self):
        autre = self.make_user("autre@example.com")
        self.repondre(autre, self.question, juste=True)

        d = self.by_slug(self.get_progression().json(), "le-tcp")
        self.assertEqual(d["questions_reussies"], 0)  # les tentatives d'autre ne comptent pas
        self.assertFalse(d["est_maitrisee"])

    def test_notion_non_publiee_exclue(self):
        cat = Category.objects.create(name="Secret", slug="secret-cat")
        masquee = Notion.objects.create(
            title="Masquee", slug="masquee", category=cat, is_published=False
        )
        Question.objects.create(
            question_text="Q cachée ?", explication="E", notion=masquee,
            difficulty=self.difficulty,
        )
        slugs = [x["notion"]["slug"] for x in self.get_progression().json()]
        self.assertIn("le-tcp", slugs)
        self.assertNotIn("masquee", slugs)

    def test_notion_sans_question_sans_crash(self):
        cat = Category.objects.create(name="Vide", slug="vide-cat")
        Notion.objects.create(
            title="Vide", slug="vide", category=cat, is_published=True
        )
        d = self.by_slug(self.get_progression().json(), "vide")
        self.assertEqual(d["questions_total"], 0)
        self.assertEqual(d["progression"], 0.0)  # division par zéro évitée
        self.assertFalse(d["est_maitrisee"])

    def test_anonyme_refuse(self):
        r = self.client.get(f"{BASE}/users/ma-progression/")
        self.assertEqual(r.status_code, 401)
