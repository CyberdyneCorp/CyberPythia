# add-scheduled-daily-sync

A daily worker cron that enqueues a full sync for every enabled repository, so metrics,
health, delivery analytics, and the metrics time-series refresh at least once per day
without depending on webhooks. Reuses the existing sync trigger, queue, and per-repo locks;
configurable UTC hour, disableable. No new data model or API surface.
