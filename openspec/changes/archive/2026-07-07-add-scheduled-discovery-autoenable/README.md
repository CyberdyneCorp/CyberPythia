# add-scheduled-discovery-autoenable

Extends the daily worker job to re-discover repositories the connections can see and
auto-enable newly-appearing non-archived repos in a configured mode (default
project_intelligence), chained ahead of the daily full sync — so coverage stays current
automatically without overriding manual disables. Config-driven, disableable, no new data model.
