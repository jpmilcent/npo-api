from fastapi import status
from fastapi.testclient import TestClient

from npo.core.config import backend_settings
from npo.main import app


def test_cors_simple_request():
    """
    Test qu'une requête standard (GET) avec un header 'Origin' reçoit bien
    les en-têtes CORS de réponse, y compris les en-têtes exposés.
    """
    origin = "http://localhost:4200"
    headers = {"Origin": origin}

    with TestClient(app) as client:
        response = client.get("/", headers=headers)

    assert response.status_code == status.HTTP_200_OK

    # Vérification des headers CORS standards
    # On utilise la configuration réelle pour l'assertion afin d'éviter les "magic strings"
    # et de rendre le test résilient aux changements de configuration par défaut.
    assert response.headers["access-control-allow-origin"] == backend_settings.cors_origins[0]
    assert (
        response.headers["access-control-allow-credentials"]
        == str(backend_settings.cors_allow_credentials).lower()
    )

    # Vérification que nos headers custom sont bien exposés au JS
    expose_headers = response.headers["access-control-expose-headers"]
    assert "X-Request-ID" in expose_headers
    assert "X-Response-Time" in expose_headers


def test_cors_preflight_request():
    """
    Test d'une requête 'Preflight' (OPTIONS) envoyée par le navigateur
    avant une requête complexe (ex: POST avec JSON et Authorization).
    """
    origin = "http://localhost:4200"
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,authorization",
    }

    with TestClient(app) as client:
        response = client.options("/", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["access-control-allow-origin"] == origin

    # Vérifie que les méthodes et headers demandés sont acceptés
    allow_methods = response.headers["access-control-allow-methods"]
    assert "POST" in allow_methods

    allow_headers = response.headers["access-control-allow-headers"].lower()
    assert "content-type" in allow_headers
    assert "authorization" in allow_headers
