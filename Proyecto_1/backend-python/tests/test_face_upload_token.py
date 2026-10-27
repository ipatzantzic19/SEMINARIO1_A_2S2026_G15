"""Firma real, aislamiento de propósito y compatibilidad criptográfica con Node."""

import base64
import json
import shutil
import subprocess
from datetime import datetime, timezone

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.common.errors import ApiError
from app.modules.auth.face import FaceLoginService
from app.modules.auth.face_store import FaceChallengeStore
from app.modules.auth.face_upload_token import FaceUploadTokenSigner
from app.modules.integrations.cognito.gateway import AuthChallenge
from tests.fakes import FakeCognito

CID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
NOW = 1_800_000_000


@pytest.fixture
def signer(tmp_path, rsa_key):
    path = tmp_path / "private.pem"
    path.write_bytes(rsa_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    return FaceUploadTokenSigner(str(path), "face-v1")


def decode(token, public_pem):
    return jwt.decode(token, public_pem, algorithms=["RS256"], audience="semisocial-image-upload",
                      issuer="semisocial-face-auth", options={"verify_iat": False, "verify_exp": False})


def test_signed_claims_and_random_jti(signer, public_pem):
    token = signer.issue(CID, NOW, 120)
    assert jwt.get_unverified_header(token) == {"alg": "RS256", "typ": "JWT", "kid": "face-v1"}
    claims = decode(token, public_pem)
    assert claims == {"iss": "semisocial-face-auth", "aud": "semisocial-image-upload", "purpose": "faceCapture",
                      "challengeId": CID, "iat": NOW, "exp": NOW + 120, "jti": claims["jti"]}
    assert decode(signer.issue(CID, NOW, 120), public_pem)["jti"] != claims["jti"]
    parts = token.split(".")
    claims["challengeId"] = "otro-reto"
    parts[1] = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    with pytest.raises(jwt.InvalidSignatureError):
        decode(".".join(parts), public_pem)


def test_node_can_verify_python_and_python_can_verify_node(signer, public_pem, tmp_path):
    node = shutil.which("node")
    assert node, "Se requiere Node para verificar interoperabilidad real"
    public_file = tmp_path / "public.pem"
    public_file.write_bytes(public_pem)
    script = """
const c = require('crypto'), fs = require('fs');
const [token, pub, priv] = process.argv.slice(1);
const [h,p,s] = token.split('.');
if (!c.verify('RSA-SHA256', Buffer.from(h+'.'+p), fs.readFileSync(pub), Buffer.from(s,'base64url'))) process.exit(1);
const sig = c.sign('RSA-SHA256', Buffer.from(h+'.'+p), fs.readFileSync(priv)).toString('base64url');
process.stdout.write(h+'.'+p+'.'+sig);
"""
    token = signer.issue(CID, NOW, 120)
    result = subprocess.run([node, "-e", script, token, str(public_file), signer._private_key_file],
                            check=True, capture_output=True, text=True)
    assert decode(result.stdout, public_pem)["challengeId"] == CID


@pytest.mark.parametrize("ttl", [0, 29, 301, 120.5])
def test_invalid_ttl_is_503(signer, ttl):
    with pytest.raises(ApiError) as exc:
        signer.issue(CID, NOW, ttl)
    assert exc.value.status_code == 503


def test_missing_invalid_or_non_rsa_key_is_503(tmp_path):
    path = tmp_path / "private.pem"
    for pem in [b"invalid", ec.generate_private_key(ec.SECP256R1()).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())]:
        path.write_bytes(pem)
        with pytest.raises(ApiError) as exc:
            FaceUploadTokenSigner(str(path), "face-v1").issue(CID, NOW, 120)
        assert exc.value.status_code == 503
        assert str(path) not in str(exc.value)
    with pytest.raises(ApiError):
        FaceUploadTokenSigner(None, None).issue(CID, NOW, 120)


def test_real_and_decoy_use_signed_tokens_with_same_expiry(signer, public_pem):
    cognito = FakeCognito()
    cognito.face_init_results = [AuthChallenge("CUSTOM_CHALLENGE", "session", {"challengeId": CID}),
                                ApiError(401, details={"reason": "FACE_UNKNOWN_USER"})]
    store = FaceChallengeStore(clock=lambda: 1000)
    service = FaceLoginService(cognito, None, store, "Fotos_Perfil/captures/",
                               wall_clock=lambda: datetime.fromtimestamp(NOW + .789, timezone.utc),
                               token_factory=signer.issue)
    real = service.create_challenge(email="test@example.com")
    decoy = service._decoy("UNKNOWN_USER")
    for body in (real, decoy):
        claims = decode(body["uploadToken"], public_pem)
        assert claims["challengeId"] == body["challengeId"]
        assert claims["exp"] == datetime.fromisoformat(body["expiresAt"]).timestamp()
        assert store.take(body["challengeId"]).expires_at == pytest.approx(1119.211)


def test_missing_signer_never_stores_or_returns_opaque_token():
    store = FaceChallengeStore()
    service = FaceLoginService(FakeCognito(), None, store, "Fotos_Perfil/captures/")
    with pytest.raises(ApiError) as exc:
        service._decoy("UNKNOWN_USER")
    assert exc.value.status_code == 503
    assert len(store) == 0
