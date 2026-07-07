# add-rate-limit-resilient-sync

Makes the ~238-repo nightly sync degrade gracefully under GitHub rate limits: stagger the
enqueues to smooth the request rate, and bound the in-request rate-limit wait so a limited repo
fails fast (retried next night) instead of stalling a worker slot for up to an hour. Honours
Retry-After for secondary limits. Config-driven; no new data model.
