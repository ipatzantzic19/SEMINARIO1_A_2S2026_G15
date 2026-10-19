"""ImageObjects.head con Stubber sobre un cliente S3 sin firma (sin AWS)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import EndpointConnectionError, NoCredentialsError
from botocore.stub import Stubber

from app.common.errors import ApiError
from app.modules.integrations.s3.objects import ImageObjects, ObjectInfo

BUCKET = "semisocial-g15-images-581117996165"
KEY = "Fotos_Perfil/public/sub/0b6f6c4e-873e-486a-847e-aeaf52aa4e2e.jpg"


@pytest.fixture
def stubbed() -> Iterator[tuple[ImageObjects, Stubber]]:
    client = boto3.client("s3", region_name="us-east-1", config=Config(signature_version=UNSIGNED))
    with Stubber(client) as stubber:
        yield ImageObjects(BUCKET, lambda: client), stubber
        stubber.assert_no_pending_responses()


def test_existing_object_returns_metadata(stubbed) -> None:
    objects, stubber = stubbed
    stubber.add_response(
        "head_object", {"ContentType": "image/jpeg", "ContentLength": 1234}, {"Bucket": BUCKET, "Key": KEY}
    )
    assert objects.head(KEY) == ObjectInfo("image/jpeg", 1234)


@pytest.mark.parametrize(("status", "code"), [(404, "404"), (403, "403"), (404, "NoSuchKey")])
def test_missing_or_unreadable_object_is_none(stubbed, status: int, code: str) -> None:
    objects, stubber = stubbed
    stubber.add_client_error("head_object", service_error_code=code, http_status_code=status)
    assert objects.head(KEY) is None


def test_other_s3_errors_are_503(stubbed) -> None:
    objects, stubber = stubbed
    stubber.add_client_error("head_object", service_error_code="500", http_status_code=500)
    with pytest.raises(ApiError) as info:
        objects.head(KEY)
    assert info.value.status_code == 503


@pytest.mark.parametrize("exc", [NoCredentialsError(), EndpointConnectionError(endpoint_url="https://s3")])
def test_credentials_and_network_errors_are_503(exc: Exception) -> None:
    class Broken:
        def head_object(self, **_: Any) -> Any:
            raise exc

    with pytest.raises(ApiError) as info:
        ImageObjects(BUCKET, Broken).head(KEY)
    assert info.value.status_code == 503
