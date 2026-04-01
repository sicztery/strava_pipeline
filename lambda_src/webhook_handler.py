import base64
import json
import logging
import os


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("strava_pipeline.lambda_webhook")


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _get_env(name: str, required: bool = True) -> str | None:
    value = os.getenv(name)
    if required and not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value


def _secrets_client():
    import boto3

    region = os.getenv("AWS_REGION")
    if region:
        return boto3.client("secretsmanager", region_name=region)
    return boto3.client("secretsmanager")


def _ecs_client():
    import boto3

    region = os.getenv("AWS_REGION")
    if region:
        return boto3.client("ecs", region_name=region)
    return boto3.client("ecs")


def _get_secret(secret_name: str) -> str:
    client = _secrets_client()

    try:
        response = client.get_secret_value(SecretId=secret_name)
    except Exception as exc:
        raise RuntimeError(f"Failed to read secret: {secret_name}") from exc

    value = response.get("SecretString")
    if value is None:
        value = response.get("SecretBinary")
        if value is None:
            raise RuntimeError(f"Secret has no string value: {secret_name}")
        value = value.decode("utf-8")

    return value


def _verify_token() -> str | None:
    token = os.getenv("WEBHOOK_VERIFY_TOKEN")
    if token:
        return token

    secret_name = _get_env("WEBHOOK_VERIFY_TOKEN_SECRET")

    try:
        return _get_secret(secret_name)
    except Exception:
        logger.warning(
            "Webhook verify token is missing and could not be loaded from Secrets Manager",
            exc_info=True,
        )
        return None


def _request_method(event: dict) -> str:
    return (
        event.get("requestContext", {})
        .get("http", {})
        .get("method", event.get("httpMethod", ""))
        .upper()
    )


def _query_params(event: dict) -> dict:
    return event.get("queryStringParameters") or {}


def _parse_json_body(event: dict) -> dict | None:
    body = event.get("body")
    if not body:
        return None

    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    return parsed


def _run_worker_task() -> None:
    cluster = _get_env("ECS_CLUSTER")
    task_definition = _get_env("ECS_TASK_DEFINITION")
    subnets = [
        subnet.strip()
        for subnet in _get_env("ECS_SUBNETS").split(",")
        if subnet.strip()
    ]
    security_groups = [
        group.strip()
        for group in _get_env("ECS_SECURITY_GROUPS").split(",")
        if group.strip()
    ]

    client = _ecs_client()
    client.run_task(
        cluster=cluster,
        taskDefinition=task_definition,
        launchType=os.getenv("ECS_LAUNCH_TYPE", "FARGATE"),
        count=1,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": subnets,
                "securityGroups": security_groups,
                "assignPublicIp": os.getenv("ECS_ASSIGN_PUBLIC_IP", "ENABLED"),
            }
        },
    )


def _handle_verification(event: dict) -> dict:
    params = _query_params(event)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    verify_token = _verify_token()

    if not verify_token:
        return _response(500, {"error": "Server misconfigured"})

    if mode == "subscribe" and token == verify_token and challenge:
        logger.info("Webhook verification successful")
        return _response(200, {"hub.challenge": challenge})

    logger.warning(
        "Verification failed",
        extra={"mode": mode, "token_match": token == verify_token},
    )
    return _response(403, {"error": "Forbidden"})


def _handle_event(event: dict) -> dict:
    payload = _parse_json_body(event)
    if not payload:
        logger.warning("Empty or invalid event payload")
        return _response(400, {"error": "Bad Request"})

    aspect_type = payload.get("aspect_type")
    object_type = payload.get("object_type")
    object_id = payload.get("object_id")

    if aspect_type != "create":
        logger.info("Ignoring event due to aspect_type=%s", aspect_type)
        return _response(200, {"status": "ignored"})

    if object_type != "activity":
        logger.info("Ignoring event due to object_type=%s", object_type)
        return _response(200, {"status": "ignored"})

    if not isinstance(object_id, int):
        logger.warning("Invalid object_id=%s", object_id)
        return _response(400, {"error": "Bad Request"})

    logger.info("Valid Strava webhook: activity_id=%s", object_id)

    try:
        _run_worker_task()
        logger.info("ECS task triggered for activity_id=%s", object_id)
    except Exception:
        logger.error("Failed to trigger ECS task", exc_info=True)

    return _response(200, {"status": "ok"})


def lambda_handler(event: dict, _context) -> dict:
    method = _request_method(event)

    if method == "GET":
        return _handle_verification(event)

    if method == "POST":
        return _handle_event(event)

    return _response(405, {"error": "Method Not Allowed"})
