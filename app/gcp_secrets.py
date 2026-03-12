import json
from google.cloud import secretmanager

_client = secretmanager.SecretManagerServiceClient()
_cache = {}

def get_secret(secret_name: str, project_id: str) -> str:
    if secret_name in _cache:
        return _cache[secret_name]

    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = _client.access_secret_version(name=name)

    value = response.payload.data.decode("utf-8")
    _cache[secret_name] = value
    return value


def update_refresh_token_if_changed(
    secret_name: str,
    project_id: str,
    new_refresh_token: str
) -> bool:
    """
    Sekret = JSON:
    { "refresh_token": "..." }

    Zapisuje nową wersję tylko jeśli refresh_token się zmienił.
    """

    try:
        raw = get_secret(secret_name, project_id)
        current = json.loads(raw).get("refresh_token")
    except Exception:
        current = None

    if current == new_refresh_token:
        return False

    payload = json.dumps(
        {"refresh_token": new_refresh_token}
    ).encode("utf-8")

    parent = f"projects/{project_id}/secrets/{secret_name}"
    _client.add_secret_version(
        parent=parent,
        payload={"data": payload}
    )

    _cache[secret_name] = payload.decode("utf-8")
    return True
