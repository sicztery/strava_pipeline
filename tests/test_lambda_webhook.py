import json
import os
import unittest
from unittest.mock import Mock, patch

from lambda_src import webhook_handler


class LambdaWebhookTests(unittest.TestCase):
    def setUp(self):
        webhook_handler._secret_cache.clear()
        self.env_patcher = patch.dict(
            os.environ,
            {
                "AWS_REGION": "eu-north-1",
                "WEBHOOK_VERIFY_TOKEN_SECRET": "strava-webhook-verify-token",
                "ECS_CLUSTER": "cluster-arn",
                "ECS_TASK_DEFINITION": "worker-task-arn",
                "ECS_SUBNETS": "subnet-a,subnet-b",
                "ECS_SECURITY_GROUPS": "sg-a",
                "ECS_ASSIGN_PUBLIC_IP": "ENABLED",
            },
            clear=False,
        )
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()
        webhook_handler._secret_cache.clear()

    @patch("lambda_src.webhook_handler._secrets_client")
    def test_get_webhook_returns_challenge_for_valid_token(self, mock_secrets_client):
        secrets_client = Mock()
        secrets_client.get_secret_value.return_value = {
            "SecretString": "expected-token"
        }
        mock_secrets_client.return_value = secrets_client

        event = {
            "requestContext": {"http": {"method": "GET"}},
            "queryStringParameters": {
                "hub.mode": "subscribe",
                "hub.verify_token": "expected-token",
                "hub.challenge": "12345",
            },
        }

        response = webhook_handler.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), {"hub.challenge": "12345"})

    @patch("lambda_src.webhook_handler._secrets_client")
    def test_get_webhook_rejects_invalid_token(self, mock_secrets_client):
        secrets_client = Mock()
        secrets_client.get_secret_value.return_value = {
            "SecretString": "expected-token"
        }
        mock_secrets_client.return_value = secrets_client

        event = {
            "requestContext": {"http": {"method": "GET"}},
            "queryStringParameters": {
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "12345",
            },
        }

        response = webhook_handler.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 403)
        self.assertEqual(json.loads(response["body"]), {"error": "Forbidden"})

    @patch("lambda_src.webhook_handler._ecs_client")
    def test_post_ignores_unsupported_events(self, mock_ecs_client):
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "body": json.dumps(
                {
                    "aspect_type": "update",
                    "object_type": "activity",
                    "object_id": 123,
                }
            ),
        }

        response = webhook_handler.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), {"status": "ignored"})
        mock_ecs_client.assert_not_called()

    @patch("lambda_src.webhook_handler._ecs_client")
    def test_post_runs_worker_for_valid_event(self, mock_ecs_client):
        ecs_client = Mock()
        mock_ecs_client.return_value = ecs_client

        event = {
            "requestContext": {"http": {"method": "POST"}},
            "body": json.dumps(
                {
                    "aspect_type": "create",
                    "object_type": "activity",
                    "object_id": 123,
                }
            ),
        }

        response = webhook_handler.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), {"status": "ok"})
        ecs_client.run_task.assert_called_once_with(
            cluster="cluster-arn",
            taskDefinition="worker-task-arn",
            launchType="FARGATE",
            count=1,
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": ["subnet-a", "subnet-b"],
                    "securityGroups": ["sg-a"],
                    "assignPublicIp": "ENABLED",
                }
            },
        )

    @patch("lambda_src.webhook_handler._ecs_client")
    def test_post_returns_200_when_ecs_trigger_fails(self, mock_ecs_client):
        ecs_client = Mock()
        ecs_client.run_task.side_effect = RuntimeError("boom")
        mock_ecs_client.return_value = ecs_client

        event = {
            "requestContext": {"http": {"method": "POST"}},
            "body": json.dumps(
                {
                    "aspect_type": "create",
                    "object_type": "activity",
                    "object_id": 123,
                }
            ),
        }

        response = webhook_handler.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
