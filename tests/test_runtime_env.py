import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

class RuntimeEnvTests(unittest.TestCase):
    def test_skips_dotenv_in_aws_runtime(self):
        from app.runtime_env import load_local_dotenv

        fake_dotenv = types.SimpleNamespace(load_dotenv=Mock())

        with patch.dict(os.environ, {"AWS_EXECUTION_ENV": "AWS_ECS_FARGATE"}, clear=False):
            with patch.dict(sys.modules, {"dotenv": fake_dotenv}):
                load_local_dotenv()

        fake_dotenv.load_dotenv.assert_not_called()

    def test_loads_dotenv_locally(self):
        from app.runtime_env import load_local_dotenv

        fake_dotenv = types.SimpleNamespace(load_dotenv=Mock())

        with patch.dict(os.environ, {}, clear=True):
            with patch.dict(sys.modules, {"dotenv": fake_dotenv}):
                load_local_dotenv()

        fake_dotenv.load_dotenv.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
