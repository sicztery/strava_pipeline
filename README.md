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

## Flexible Triggering

The worker is **decoupled from webhook delivery**. While the primary flow is event-driven via webhooks, the worker can also be triggered independently:

- **Webhook-driven** (default): Real-time ingestion when Strava pushes activity events.
- **Scheduled (cron)**: Periodic runs to catch missed events or refresh historical data. Useful as a safety net or for backfills.

Both modes use the same state management logic to track processed activities, so they can coexist without conflicts.

## Key Characteristics

* Event-driven architecture
* Push-based ingestion (no polling required)
* Designed for reliable, repeatable activity ingestion
* Easy to integrate with external data stores or analytics pipelines

## Status

Work in progress.
The project is currently focused on reliability and internal use rather than being a fully packaged public tool.

## Limitations

- **State management**: Current state tracking via filesystem/database snapshots. No distributed consensus for concurrent runs.
- **Error handling**: Limited retry logic for transient failures. Dead letter handling not yet implemented.
- **Data model**: Pipeline assumes specific Strava activity schema. Schema changes upstream would require manual updates.

## Future Development

Planned improvements for maturity:

- **Real-time monitoring & alerts**: Dashboard for pipeline health, failed runs, and data freshness metrics.
- **Intelligent retry & backoff**: Exponential backoff and dead-letter queue for handling ephemeral and persistent failures.
- **Schema evolution**: Versioned data model with backward compatibility for upstream API changes.
- **Deployment templates**: Helm charts / Terraform modules for multi-environment deployments.
- **Observability**: Structured logging with trace IDs, OpenTelemetry instrumentation, and cost attribution.


