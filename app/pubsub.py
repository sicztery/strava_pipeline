import os
import json
import logging
from google.cloud import pubsub_v1

logger = logging.getLogger("strava_pipeline")

PROJECT_ID = os.getenv("STRAVA_GCP_PROJECT")
TOPIC_ID = os.getenv("STRAVA_PUBSUB_TOPIC")

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)


def publish_event(event: dict, topic: str):

    topic_path = publisher.topic_path(PROJECT_ID, topic)

    message = json.dumps(event).encode("utf-8")

    future = publisher.publish(topic_path, message)

    logger.info(
        f"Published event to PubSub: "
        f"type={event.get('aspect_type')} "
        f"id={event.get('object_id')}"
    )

    return future