import json
import os
import boto3
from botocore.exceptions import ClientError

_cache = {}


def _client():
    region = os.getenv("AWS_REGION")
    if region:
        return boto3.client("secretsmanager", region_name=region)
    return boto3.client("secretsmanager")


def get_secret(secret_name: str) -> str:
    if secret_name in _cache:
        return _cache[secret_name]

    client = _client()

    try:
        response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        raise RuntimeError(f"Failed to read secret: {secret_name}") from e

    value = response.get("SecretString")
    if value is None:
        value = response.get("SecretBinary")
        if value is None:
            raise RuntimeError(f"Secret has no string value: {secret_name}")
        value = value.decode("utf-8")

    _cache[secret_name] = value
    return value


def update_refresh_token_if_changed(
    secret_name: str,
    new_refresh_token: str
) -> bool:
    """
    Secret value is JSON:
    { "refresh_token": "..." }

    Writes new version only if refresh_token has changed.
    """

    try:
        raw = get_secret(secret_name)
        current = json.loads(raw).get("refresh_token")
    except Exception:
        current = None

    if current == new_refresh_token:
        return False

    payload = json.dumps(
        {"refresh_token": new_refresh_token}
    )

    client = _client()
    client.put_secret_value(
        SecretId=secret_name,
        SecretString=payload
    )

    _cache[secret_name] = payload
    return True
