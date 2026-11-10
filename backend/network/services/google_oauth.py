from google.auth.transport import requests
from google.oauth2 import id_token
from django.conf import settings


def verify_google_id_token(token):
    try:
        id_info = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )

    except ValueError:
        raise ValueError("Le jeton Google est invalide ou expiré.")

    return id_info