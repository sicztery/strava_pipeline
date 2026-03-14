# Strava Pipeline

A lightweight pipeline for ingesting activity data from the Strava API and forwarding it to a downstream data consumer.

## Overview

`strava_pipeline` listens for activity updates from Strava and processes them in a simple event-driven workflow.
Instead of periodically polling the API, the system relies on **Strava webhooks**, meaning new activity data is **pushed into the pipeline** whenever an event occurs.

This approach reduces unnecessary API calls and enables near real-time processing.

## How it works

1. **Strava webhook** sends an event notification when an activity is created or updated.
2. The webhook endpoint receives the event and triggers the pipeline.
3. A worker fetches the full activity details from the Strava API.
4. The processed activity data is **pushed to the configured downstream consumer** (database, storage, or other service).

```
Strava → Webhook → Pipeline Worker → Data Consumer
```

## Key Characteristics

* Event-driven architecture
* Push-based ingestion (no polling required)
* Designed for reliable, repeatable activity ingestion
* Easy to integrate with external data stores or analytics pipelines

## Status

Work in progress.
The project is currently focused on reliability and internal use rather than being a fully packaged public tool.

## Notes

This repository may evolve as the pipeline architecture and data model are refined.

