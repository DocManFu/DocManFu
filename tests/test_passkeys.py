"""Passkey registration and sign-in, end to end with a software authenticator."""

import hashlib
import json
import os
import struct

import cbor2
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from webauthn.helpers import bytes_to_base64url

from app.api import passkeys as passkeys_module
from app.core.auth import get_current_user
from app.core.security import decode_token, hash_password
from app.db.base import Base
from app.db.deps import get_db
from app.models.passkey import Passkey
from app.models.user import User

ORIGIN = "https://docs.example.com"
RP_ID = "docs.example.com"


class FakeRedis:
    store: dict = {}

    def set(self, key, value, ex=None):
        self.store[key] = value

    def getdel(self, key):
        return self.store.pop(key, None)

    def close(self):
        pass


class SoftAuthenticator:
    """Minimal WebAuthn authenticator: 'none' attestation, ES256, UP+UV."""

    def __init__(self, origin=ORIGIN, rp_id=RP_ID):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(16)
        self.origin = origin
        self.rp_id_hash = hashlib.sha256(rp_id.encode()).digest()
        self.counter = 0

    def _client_data(self, type_, challenge):
        return json.dumps(
            {"type": type_, "challenge": challenge, "origin": self.origin}
        ).encode()

    def register(self, options):
        numbers = self.key.public_key().public_numbers()
        cose_key = cbor2.dumps(
            {
                1: 2,
                3: -7,
                -1: 1,
                -2: numbers.x.to_bytes(32, "big"),
                -3: numbers.y.to_bytes(32, "big"),
            }
        )
        auth_data = (
            self.rp_id_hash
            + bytes([0x45])  # UP | UV | AT
            + struct.pack(">I", self.counter)
            + bytes(16)  # AAGUID
            + struct.pack(">H", len(self.credential_id))
            + self.credential_id
            + cose_key
        )
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        cid = bytes_to_base64url(self.credential_id)
        return {
            "id": cid,
            "rawId": cid,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(
                    self._client_data("webauthn.create", options["challenge"])
                ),
                "attestationObject": bytes_to_base64url(attestation),
                "transports": ["internal"],
            },
            "clientExtensionResults": {},
        }

    def sign_in(self, options):
        self.counter += 1
        client_data = self._client_data("webauthn.get", options["challenge"])
        auth_data = self.rp_id_hash + bytes([0x05]) + struct.pack(">I", self.counter)
        signature = self.key.sign(
            auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
        )
        cid = bytes_to_base64url(self.credential_id)
        return {
            "id": cid,
            "rawId": cid,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(signature),
            },
            "clientExtensionResults": {},
        }


@pytest.fixture
def env(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[User.__table__, Passkey.__table__])
    Session = sessionmaker(bind=engine)

    monkeypatch.setattr(passkeys_module.settings, "WEBAUTHN_ORIGIN", ORIGIN)
    monkeypatch.setattr(passkeys_module.settings, "JWT_SECRET_KEY", "test-secret")
    FakeRedis.store = {}
    monkeypatch.setattr(passkeys_module, "get_redis_client", FakeRedis)

    with Session() as db:
        for name in ("alice", "bob"):
            db.add(
                User(
                    username=name,
                    email=f"{name}@example.com",
                    hashed_password=hash_password("password1"),
                    role="user",
                    is_active=True,
                    token_version=0,
                )
            )
        db.commit()

    def override_db():
        with Session() as db:
            yield db

    current = {"username": "alice"}

    def override_user(db=Depends(get_db)):
        return db.query(User).filter(User.username == current["username"]).one()

    app = FastAPI()
    app.include_router(passkeys_module.router)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app), Session, current


def register(client, authenticator, password="password1", name="Bitwarden"):
    res = client.post(
        "/api/auth/passkeys/register/options", json={"password": password}
    )
    if res.status_code != 200:
        return res
    body = res.json()
    return client.post(
        "/api/auth/passkeys/register/verify",
        json={
            "challenge_id": body["challenge_id"],
            "credential": authenticator.register(body["options"]),
            "name": name,
        },
    )


def sign_in(client, authenticator):
    body = client.post("/api/auth/passkeys/login/options").json()
    credential = authenticator.sign_in(body["options"])
    return client.post(
        "/api/auth/passkeys/login/verify",
        json={"challenge_id": body["challenge_id"], "credential": credential},
    ), (body["challenge_id"], credential)


def test_register_and_sign_in(env):
    client, Session, _ = env
    authenticator = SoftAuthenticator()

    res = register(client, authenticator)
    assert res.status_code == 201, res.text
    assert res.json()["name"] == "Bitwarden"

    options = client.post("/api/auth/passkeys/login/options").json()["options"]
    assert options["rpId"] == RP_ID
    assert options["userVerification"] == "required"
    assert not options.get("allowCredentials")  # discoverable, no username needed

    res, _ = sign_in(client, authenticator)
    assert res.status_code == 200, res.text
    assert res.json()["user"]["username"] == "alice"
    assert decode_token(res.json()["access_token"])["type"] == "access"

    with Session() as db:
        passkey = db.query(Passkey).one()
        assert passkey.sign_count == 1
        assert passkey.last_used_at is not None
        assert passkey.transports == ["internal"]


def test_registration_requires_password(env):
    client, _, _ = env
    res = register(client, SoftAuthenticator(), password="wrong")
    assert res.status_code == 400
    assert not FakeRedis.store  # no challenge issued


def test_registration_options_require_resident_key_and_uv(env):
    client, _, _ = env
    options = client.post(
        "/api/auth/passkeys/register/options", json={"password": "password1"}
    ).json()["options"]
    selection = options["authenticatorSelection"]
    assert selection["residentKey"] == "required"
    assert selection["userVerification"] == "required"


def test_challenge_cannot_be_replayed(env):
    client, _, _ = env
    authenticator = SoftAuthenticator()
    register(client, authenticator)

    res, (challenge_id, credential) = sign_in(client, authenticator)
    assert res.status_code == 200
    replay = client.post(
        "/api/auth/passkeys/login/verify",
        json={"challenge_id": challenge_id, "credential": credential},
    )
    assert replay.status_code == 400


def test_wrong_origin_rejected(env):
    client, _, _ = env
    authenticator = SoftAuthenticator()
    register(client, authenticator)

    authenticator.origin = "https://phish.example.net"
    res, _ = sign_in(client, authenticator)
    assert res.status_code == 401


def test_unknown_credential_rejected(env):
    client, _, _ = env
    res, _ = sign_in(client, SoftAuthenticator())
    assert res.status_code == 401


def test_inactive_user_cannot_sign_in(env):
    client, Session, _ = env
    authenticator = SoftAuthenticator()
    register(client, authenticator)
    with Session() as db:
        db.query(User).filter(User.username == "alice").one().is_active = False
        db.commit()

    res, _ = sign_in(client, authenticator)
    assert res.status_code == 401


def test_cannot_reuse_another_users_registration_challenge(env):
    client, _, current = env
    body = client.post(
        "/api/auth/passkeys/register/options", json={"password": "password1"}
    ).json()

    current["username"] = "bob"
    res = client.post(
        "/api/auth/passkeys/register/verify",
        json={
            "challenge_id": body["challenge_id"],
            "credential": SoftAuthenticator().register(body["options"]),
        },
    )
    assert res.status_code == 400


def test_list_and_delete_only_own_passkeys(env):
    client, _, current = env
    register(client, SoftAuthenticator(), name="Alice key")
    alice_key = client.get("/api/auth/passkeys").json()[0]

    current["username"] = "bob"
    assert client.get("/api/auth/passkeys").json() == []
    assert client.delete(f"/api/auth/passkeys/{alice_key['id']}").status_code == 404

    current["username"] = "alice"
    assert client.delete(f"/api/auth/passkeys/{alice_key['id']}").status_code == 200
    assert client.get("/api/auth/passkeys").json() == []


def test_disabled_without_origin(env, monkeypatch):
    client, _, _ = env
    monkeypatch.setattr(passkeys_module.settings, "WEBAUTHN_ORIGIN", "")
    assert client.post("/api/auth/passkeys/login/options").status_code == 400
