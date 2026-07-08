# web-ui Specification

## ADDED Requirements

### Requirement: API key management panel

The web UI SHALL provide an admin panel (on the Connections screen) to generate,
list, and revoke Mnemosyne API keys. Generating a key SHALL let the admin enter a
label and choose an expiry from presets (including "never"). On creation the UI
SHALL display the plaintext key once with a copy affordance and a warning that it
will not be shown again. The panel SHALL list existing keys with label, display
prefix, expiry, and state, and SHALL offer a revoke action per key.

#### Scenario: Generate and reveal once
- **WHEN** an admin submits the generate form with a label and expiry
- **THEN** the UI SHALL show the new plaintext key with a copy button and a "shown once" warning, and add the key to the list

#### Scenario: Revoke from the list
- **WHEN** an admin clicks revoke on a listed key
- **THEN** the UI SHALL revoke the key and reflect it as revoked in the list
