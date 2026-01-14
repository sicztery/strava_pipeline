from google.cloud import secretmanager

_client = secretmanager.SecretManagerServiceClient()
_cache = {}

def get_secret(secret_name: str, project_id: str) -> str:
    if secret_name in _cache:
        return _cache[secret_name]

    secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = _client.access_secret_version(name=secret_path)

    value = response.payload.data.decode("UTF-8")
    _cache[secret_name] = value
    return value
