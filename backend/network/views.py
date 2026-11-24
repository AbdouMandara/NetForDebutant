from django.db import connection
from django.db.utils import OperationalError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from network.api.serializer import HealthSerializer


class HealthView(APIView):
    """Health check public (monitoring, uptime robot, LoadBalancer).

    Aucune authentification ni throttle : le but est de pouvoir sonder
    l'application même quand tout le reste est hors service.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        responses={200: HealthSerializer, 503: HealthSerializer},
        description=(
            "État de l'application. Renvoie 200 si l'API et la base de "
            "données répondent, 503 sinon (base injoignable)."
        ),
        tags=['health'],
    )
    def get(self, request):
        try:
            connection.ensure_connection()  # lève OperationalError si la BDD est KO
        except OperationalError:
            return Response(
                {'status': 'unavailable', 'database': 'error'},
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {'status': 'ok', 'database': 'ok'},
            status=HTTP_200_OK,
        )
