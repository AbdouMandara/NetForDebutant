# NetForDebutant

API Django REST Framework d'un quiz réseau pédagogique.

## Documentation de l'API

La documentation est générée automatiquement par [drf-spectacular](https://drf-spectacular.readthedocs.io/) (OpenAPI 3.1) et servie localement (assets inclus via `drf-spectacular-sidecar`, pas de CDN) :

| Page | URL |
|------|-----|
| Schéma (YAML) | `/api/v1/schema/` |
| Schéma (JSON) | `/api/v1/schema/?format=json` |
| Swagger UI | `/api/v1/schema/swagger-ui/` |
| ReDoc | `/api/v1/schema/redoc/` |

**Health check** : `GET /health/` (public, sans auth) renvoie `{"status": "ok", "database": "ok"}` en 200, ou 503 si la base est injoignable.

En local avec `DEBUG=True` : http://localhost:8000/api/v1/schema/swagger-ui/

Le fichier `backend/schema.yml` est commité (utile pour la revue de diff et la génération de clients). **À régénérer après chaque changement d'endpoint ou de serializer :**

```bash
cd backend
source .venv/bin/activate
python manage.py spectacular --file schema.yml --validate
```

Un test (`DocumentationTests.test_schema_yml_commité_est_a_jour`) échoue si le fichier est périmé.

### Annotations

Le schéma se déduit des viewsets/serializers ; les cas particuliers sont annotés dans `network/api/viewset.py` :

- `@extend_schema` : description, paramètres (`?seuil=` de `ma-progression`), en-tête `X-Client-Type`, réponses des endpoints auth/stats
- `@extend_schema_field` : type des `SerializerMethodField` (dans `network/api/serializer.py`)

En cas de warning à la génération, ces deux décorateurs sont les remèdes.

## Développement

```bash
cd backend
source .venv/bin/activate
python manage.py runserver        # serveur de dev
python manage.py test network     # suite de tests
```

Voir `AGENTS.md` pour l'architecture et les pièges connus.
