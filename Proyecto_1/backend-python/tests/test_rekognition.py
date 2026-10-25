"""PRO-34: adaptador de Rekognition (DetectLabels) con un cliente boto3 real intervenido por Stubber.

Sin credenciales ni red: el cliente usa firma UNSIGNED y ``botocore.stub.Stubber``
responde en lugar del servicio. Los reintentos usan un ``sleep`` falso.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import boto3
import pytest
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import EndpointConnectionError, NoCredentialsError, ReadTimeoutError
from botocore.stub import Stubber

from app.common.errors import ApiError
from app.config import RekognitionSettings
from app.modules.integrations.rekognition import ALLOWED_PREFIX, MAX_LABELS, MIN_CONFIDENCE
from app.modules.integrations.rekognition.client import build_rekognition_client
from app.modules.integrations.rekognition.detector import RETRY_DELAYS_SECONDS, LabelDetector
from app.modules.integrations.rekognition.labels import SPANISH_LABEL_MAP, normalize_filter, normalize_label, round_confidence
from tests.conftest import local_settings

BUCKET = "semisocial-g15-images-581117996165"
KEY = "Fotos_Publicadas/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/00000000-0000-4000-8000-000000000001.jpg"
AWS_INTERNAL_MESSAGE = "arn:aws:iam::123456789012:role/internal no autorizado (mensaje interno)"
NODE_SERVICE = Path(__file__).resolve().parents[2] / "backend-node/src/modules/posts/rekognition.service.ts"


def stubbed_client() -> Any:
    return boto3.client("rekognition", region_name="us-east-1", config=Config(signature_version=UNSIGNED))


class Sleeper:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


@pytest.fixture
def aws() -> Iterator[tuple[Any, Stubber]]:
    client = stubbed_client()
    with Stubber(client) as stubber:
        yield client, stubber
        stubber.assert_no_pending_responses()


@pytest.fixture
def sleeper() -> Sleeper:
    return Sleeper()


@pytest.fixture
def detector(aws, sleeper) -> LabelDetector:
    client, _ = aws
    return LabelDetector(lambda: client, BUCKET, sleep=sleeper)


def expected_params() -> dict[str, Any]:
    return {
        "Image": {"S3Object": {"Bucket": BUCKET, "Name": KEY}},
        "MaxLabels": 20,
        "MinConfidence": 80.0,
    }


def add_labels(stubber: Stubber, labels: list[dict[str, Any]]) -> None:
    stubber.add_response("detect_labels", {"Labels": labels}, expected_params())


def add_error(stubber: Stubber, code: str, status: int = 400) -> None:
    stubber.add_client_error(
        "detect_labels",
        service_error_code=code,
        service_message=AWS_INTERNAL_MESSAGE,
        http_status_code=status,
        expected_params=expected_params(),
    )


# --- Parámetros y resultado -------------------------------------------------------


def test_constants_match_labels_contract() -> None:
    assert (MAX_LABELS, MIN_CONFIDENCE, ALLOWED_PREFIX) == (20, 80.0, "Fotos_Publicadas/")
    assert RETRY_DELAYS_SECONDS == (0.25, 0.75)


def test_sends_bucket_key_maxlabels_and_minconfidence(aws, detector) -> None:
    _, stubber = aws
    add_labels(stubber, [{"Name": "Dog", "Confidence": 98.123}])
    labels = detector.detect(KEY)  # Stubber exige parámetros idénticos
    assert [(label.name, label.confidence, label.source_name) for label in labels] == [
        ("perro", Decimal("98.12"), "Dog")
    ]


def test_translates_to_spanish_and_keeps_source_name_sorted_by_confidence(aws, detector) -> None:
    _, stubber = aws
    add_labels(
        stubber,
        [
            {"Name": "Outdoors", "Confidence": 91.444},
            {"Name": "Dog", "Confidence": 98.125},
            {"Name": "Frisbee", "Confidence": 85.0},
        ],
    )
    labels = detector.detect(KEY)
    assert [(label.name, str(label.confidence), label.source_name) for label in labels] == [
        ("perro", "98.13", "Dog"),  # ROUND_HALF_UP: 98.125 -> 98.13
        ("exterior", "91.44", "Outdoors"),
        ("frisbee", "85.00", "Frisbee"),  # sin traducción: minúsculas del nombre de Rekognition
    ]


def test_discards_unnamed_and_below_threshold_labels(aws, detector) -> None:
    _, stubber = aws
    add_labels(
        stubber,
        [
            {"Confidence": 99.0},
            {"Name": "   ", "Confidence": 99.0},
            {"Name": "Cat", "Confidence": 79.99},
            {"Name": "Sky", "Confidence": 80.0},
        ],
    )
    assert [label.name for label in detector.detect(KEY)] == ["cielo"]


def test_no_qualified_labels_returns_empty_list_without_general(aws, detector) -> None:
    _, stubber = aws
    add_labels(stubber, [])
    assert detector.detect(KEY) == []


def test_duplicates_after_normalization_keep_highest_confidence(aws, detector) -> None:
    _, stubber = aws
    add_labels(
        stubber,
        [
            {"Name": "Car", "Confidence": 90.0},  # -> vehículo
            {"Name": "VEHÍCULO", "Confidence": 95.5},  # minúsculas -> vehículo
        ],
    )
    labels = detector.detect(KEY)
    assert [(label.name, str(label.confidence)) for label in labels] == [("vehículo", "95.50")]


# --- Normalización ----------------------------------------------------------------


def test_normalize_trims_nfc_lowercases() -> None:
    decomposed = "Café "  # "Café" con acento combinado y un espacio final
    label = normalize_label(decomposed, 90)
    assert label.name == "café" and label.source_name == "Café"
    assert len(label.name) == 4  # NFC: una sola marca


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(98.125, "98.13"), (98.124, "98.12"), (80, "80.00"), (91.445, "91.45"), (0.005, "0.01"), (99.999, "100.00")],
)
def test_confidence_rounds_half_up_to_two_decimals(raw: float, expected: str) -> None:
    assert str(round_confidence(raw)) == expected


def test_normalize_filter_matches_label_normalization() -> None:
    assert normalize_filter("  PERRO ") == "perro"
    assert normalize_filter("Árbol") == "árbol"


def test_dictionary_has_32_entries() -> None:
    assert len(SPANISH_LABEL_MAP) == 32


def test_dictionary_matches_node_adapter() -> None:
    if not NODE_SERVICE.exists():
        pytest.skip("backend-node no está presente en este despliegue")
    source = NODE_SERVICE.read_text(encoding="utf-8")
    block = re.search(r"SPANISH_LABEL_MAP: Record<string, string> = \{(.*?)\n\};", source, re.DOTALL)
    assert block is not None, "no se encontró SPANISH_LABEL_MAP en rekognition.service.ts"
    node_map = dict(re.findall(r"^\s*(\w+): '([^']+)',?\s*$", block.group(1), re.MULTILINE))
    assert node_map == SPANISH_LABEL_MAP


# --- Reintentos y errores ---------------------------------------------------------


@pytest.mark.parametrize("code", ["ThrottlingException", "ProvisionedThroughputExceededException", "InternalServerError"])
def test_retries_twice_with_250_and_750_ms_then_succeeds(aws, detector, sleeper, code: str) -> None:
    _, stubber = aws
    add_error(stubber, code, 500 if code == "InternalServerError" else 400)
    add_error(stubber, code, 500 if code == "InternalServerError" else 400)
    add_labels(stubber, [{"Name": "Sky", "Confidence": 90.0}])
    assert [label.name for label in detector.detect(KEY)] == ["cielo"]
    assert sleeper.calls == [0.25, 0.75]


def test_throttling_after_retries_is_429_without_aws_message(aws, detector, sleeper) -> None:
    _, stubber = aws
    for _ in range(3):
        add_error(stubber, "ThrottlingException")
    with pytest.raises(ApiError) as caught:
        detector.detect(KEY)
    assert (caught.value.status_code, caught.value.code) == (429, "RATE_LIMITED")
    assert AWS_INTERNAL_MESSAGE not in caught.value.message
    assert sleeper.calls == [0.25, 0.75]


def test_internal_error_after_retries_is_503(aws, detector, sleeper) -> None:
    _, stubber = aws
    for _ in range(3):
        add_error(stubber, "InternalServerError", 500)
    with pytest.raises(ApiError) as caught:
        detector.detect(KEY)
    assert (caught.value.status_code, caught.value.code) == (503, "SERVICE_UNAVAILABLE")
    assert AWS_INTERNAL_MESSAGE not in caught.value.message
    assert sleeper.calls == [0.25, 0.75]


@pytest.mark.parametrize(
    ("aws_code", "status", "code", "reason"),
    [
        ("InvalidS3ObjectException", 404, "NOT_FOUND", "IMAGE_NOT_FOUND"),
        ("InvalidImageFormatException", 400, "VALIDATION_ERROR", "IMAGE_UNSUPPORTED"),
        ("ImageTooLargeException", 400, "VALIDATION_ERROR", "IMAGE_UNSUPPORTED"),
        ("AccessDeniedException", 503, "SERVICE_UNAVAILABLE", None),
        ("UnrecognizedClientException", 503, "SERVICE_UNAVAILABLE", None),
        ("SomethingNewException", 503, "SERVICE_UNAVAILABLE", None),
    ],
)
def test_non_retryable_errors_map_without_retrying(aws, detector, sleeper, aws_code, status, code, reason) -> None:
    _, stubber = aws
    add_error(stubber, aws_code)
    with pytest.raises(ApiError) as caught:
        detector.detect(KEY)
    error = caught.value
    assert (error.status_code, error.code) == (status, code)
    assert (error.details or {}).get("reason") == reason
    assert AWS_INTERNAL_MESSAGE not in error.message and "arn:" not in error.message
    assert sleeper.calls == []


@pytest.mark.parametrize(
    "failure",
    [
        NoCredentialsError(),
        EndpointConnectionError(endpoint_url="https://rekognition.us-east-1.amazonaws.com"),
        ReadTimeoutError(endpoint_url="https://rekognition.us-east-1.amazonaws.com"),
    ],
    ids=["sin credenciales", "sin red", "timeout"],
)
def test_botocore_failures_are_503(failure: Exception, sleeper) -> None:
    class Broken:
        def detect_labels(self, **kwargs: Any) -> Any:
            raise failure

    detector = LabelDetector(lambda: Broken(), BUCKET, sleep=sleeper)
    with pytest.raises(ApiError) as caught:
        detector.detect(KEY)
    assert (caught.value.status_code, caught.value.code) == (503, "SERVICE_UNAVAILABLE")
    assert sleeper.calls == []


def test_client_is_created_once_and_lazily() -> None:
    created: list[int] = []
    client = stubbed_client()

    def factory() -> Any:
        created.append(1)
        return client

    detector = LabelDetector(factory, BUCKET)
    assert created == []
    with Stubber(client) as stubber:
        add_labels(stubber, [])
        add_labels(stubber, [])
        detector.detect(KEY)
        detector.detect(KEY)
    assert created == [1]


# --- Logs sin PII -----------------------------------------------------------------


def test_logs_have_aws_error_code_but_not_key_message_or_labels(aws, detector, log_stream) -> None:
    _, stubber = aws
    add_error(stubber, "AccessDeniedException")
    with pytest.raises(ApiError):
        detector.detect(KEY)
    add_labels(stubber, [{"Name": "Dog", "Confidence": 99.0}])
    detector.detect(KEY)
    output = log_stream.getvalue()
    assert '"awsErrorCode": "AccessDeniedException"' in output
    assert '"event": "rekognition.detected"' in output and '"labelCount": 1' in output
    for secret in (KEY, "aaaaaaaa-aaaa", AWS_INTERNAL_MESSAGE, "perro", "Dog"):
        assert secret not in output


# --- Cliente y configuración ------------------------------------------------------


@pytest.fixture
def isolated_aws_config(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    for name in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "credentials"))
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")


def test_build_client_uses_region_timeouts_and_single_attempt(isolated_aws_config) -> None:
    client = build_rekognition_client(RekognitionSettings(region="us-east-1", timeout_seconds=4))
    assert client.meta.region_name == "us-east-1"
    assert client.meta.config.connect_timeout == 4 and client.meta.config.read_timeout == 4
    assert client.meta.config.retries == {"mode": "standard", "total_max_attempts": 1}
    assert client.meta.service_model.service_name == "rekognition"


def test_settings_default_to_aws_region() -> None:
    settings = local_settings(AWS_REGION="us-west-2")
    assert settings.rekognition == RekognitionSettings(region="us-west-2", timeout_seconds=5)


def test_settings_overrides() -> None:
    settings = local_settings(REKOGNITION_REGION="eu-west-1", REKOGNITION_TIMEOUT_SECONDS="10")
    assert settings.rekognition == RekognitionSettings(region="eu-west-1", timeout_seconds=10)


def test_settings_reject_invalid_region_and_timeout() -> None:
    from app.config import ConfigError

    with pytest.raises(ConfigError, match="REKOGNITION_REGION"):
        local_settings(REKOGNITION_REGION="mars")
    with pytest.raises(ConfigError, match="REKOGNITION_TIMEOUT_SECONDS"):
        local_settings(REKOGNITION_TIMEOUT_SECONDS="0")

