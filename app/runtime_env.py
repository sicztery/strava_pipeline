import os


def load_local_dotenv() -> None:
    # AWS-managed runtimes (Lambda, ECS/Fargate) should rely on injected env vars
    # and Secrets Manager, not on a baked-in .env file from the container image.
    if os.getenv("AWS_EXECUTION_ENV"):
        return

    from dotenv import load_dotenv

    load_dotenv()
