# add-organization-sync-scope

Let an admin choose which GitHub organizations Mnemosyne syncs. Tracks discovered orgs (each with
a sync-enabled flag, populated by discovery, default on), and has scheduled discovery + sync skip
repositories in disabled orgs — fail-open, so unknown/enabled orgs sync as today. New
`organizations` table (migration 0006), list/toggle REST endpoints, and an Organizations panel on
the GitHub Connection page.
