"""Contract test: our introspection mapping only relies on fields CyberdyneAuth publishes.

The fixture is vendored from the live CyberdyneAuth openapi.json
(components.schemas.IntrospectionResponse). If CyberdyneAuth changes the
schema, refresh the fixture:

    curl -s https://auth.backend.coolify.cyberdynecorp.ai/openapi.json \
      | jq '{IntrospectionResponse: .components.schemas.IntrospectionResponse}' \
      > tests/fixtures/cyberdyneauth_introspection_schema.json
"""

import json
from pathlib import Path

FIXTURE = Path(__file__).parents[2] / "fixtures" / "cyberdyneauth_introspection_schema.json"

# Fields _identity_from_claims reads from an introspection response
FIELDS_WE_CONSUME = {"active", "sub", "username", "client_id", "scope", "entitlements", "is_admin"}


def test_consumed_fields_exist_in_published_schema():
    schema = json.loads(FIXTURE.read_text())["IntrospectionResponse"]
    published = set(schema["properties"].keys())
    missing = FIELDS_WE_CONSUME - published
    assert not missing, f"CyberdyneAuth no longer publishes: {missing}"


def test_entitlements_is_array_of_strings():
    schema = json.loads(FIXTURE.read_text())["IntrospectionResponse"]
    entitlements = schema["properties"]["entitlements"]
    # anyOf [array-of-strings, null] per current contract (design OQ3)
    variants = entitlements.get("anyOf", [entitlements])
    array_variant = next((v for v in variants if v.get("type") == "array"), None)
    assert array_variant is not None, "entitlements is not an array in the published schema"
    assert array_variant["items"]["type"] == "string"
