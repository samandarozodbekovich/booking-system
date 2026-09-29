import pytest

from apps.accounts.models import User

from .factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


def test_register_always_creates_customer(api_client):
    response = api_client.post(
        "/api/auth/register/",
        {"username": "ali", "email": "Ali@Mail.com", "password": DEFAULT_PASSWORD, "role": "admin"},
        format="json",
    )

    assert response.status_code == 201
    user = User.objects.get(username="ali")
    assert user.role == User.Role.CUSTOMER  # "role" from the request is ignored
    assert user.email == "ali@mail.com"  # normalized


def test_register_rejects_duplicate_email_in_any_case(api_client):
    UserFactory(email="ali@mail.com")

    response = api_client.post(
        "/api/auth/register/",
        {"username": "ali2", "email": "ALI@mail.COM", "password": DEFAULT_PASSWORD},
        format="json",
    )

    assert response.status_code == 400
    assert "email" in response.json()


def test_register_rejects_weak_password(api_client):
    response = api_client.post(
        "/api/auth/register/",
        {"username": "ali", "email": "ali@mail.com", "password": "123"},
        format="json",
    )

    assert response.status_code == 400
    assert "password" in response.json()


def test_login_and_me(api_client):
    user = UserFactory(username="vali")

    login = api_client.post(
        "/api/auth/login/", {"username": "vali", "password": DEFAULT_PASSWORD}, format="json"
    )
    assert login.status_code == 200

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
    me = api_client.get("/api/auth/profile/")

    assert me.status_code == 200
    assert me.json()["id"] == user.id
    assert me.json()["role"] == "customer"


def test_me_requires_authentication(api_client):
    assert api_client.get("/api/auth/profile/").status_code == 401


def test_logout_blacklists_refresh_token(api_client):
    UserFactory(username="vali")
    tokens = api_client.post(
        "/api/auth/login/", {"username": "vali", "password": DEFAULT_PASSWORD}, format="json"
    ).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    logout = api_client.post("/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json")
    refresh = api_client.post("/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json")

    assert logout.status_code == 204
    assert refresh.status_code == 401