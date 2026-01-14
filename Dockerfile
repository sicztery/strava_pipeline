FROM python:3.11-slim

WORKDIR /app

COPY . /app

ENV STRAVA_GCP_PROJECT=my-gcp-project-id

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "app.strava_client"]
