import json
from google.cloud import secretmanager
from google.api_core.exceptions import NotFound

_client = secretmanager.SecretManagerServiceClient()
_cache = {}

def get_json_secret(secret_name: str, project_id: str) -> dict:
    if secret_name in _cache:
        return _cache[secret_name]

    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = _client.access_secret_version(name=name)

    value = json.loads(response.payload.data.decode("utf-8"))
    _cache[secret_name] = value
    return value


def update_json_secret_if_changed(
    secret_name: str,
    project_id: str,
    new_payload: dict
) -> bool:
    """
    Zapisuje nową wersję secreta TYLKO jeśli payload się zmienił.
    Zwraca True jeśli utworzono nową wersję.
    """

    try:
        current_payload = get_json_secret(secret_name, project_id)
    except NotFound:
        current_payload = None

    if current_payload == new_payload:
        return False

    parent = f"projects/{project_id}/secrets/{secret_name}"
    _client.add_secret_version(
        parent=parent,
        payload={
            "data": json.dumps(new_payload).encode("utf-8")
        }
    )

    _cache[secret_name] = new_payload
    return True
