from google.cloud import secretmanager

_client = secretmanager.SecretManagerServiceClient()
_cache = {}

def get_secret(secret_name: str, project_id: str) -> str:
    if secret_name in _cache:
        return _cache[secret_name]

    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = _client.access_secret_version(name=name)

    value = response.payload.data.decode("UTF-8")
    _cache[secret_name] = value
    return value


def update_secret_if_changed(
    secret_name: str,
    project_id: str,
    new_value: str
) -> bool:
    """
    Zapisuje nową wersję sekretu TYLKO jeśli wartość się zmieniła.

    Returns:
        True  -> utworzono nową wersję
        False -> brak zmian
    """

    try:
        current_value = get_secret(secret_name, project_id)
    except Exception:
        # sekret istnieje, ale brak wersji / brak dostępu – traktujemy jak zmianę
        current_value = None

    if current_value == new_value:
        return False

    parent = f"projects/{project_id}/secrets/{secret_name}"
    _client.add_secret_version(
        parent=parent,
        payload={"data": new_value.encode("UTF-8")}
    )

    # aktualizujemy cache
    _cache[secret_name] = new_value
    return True
