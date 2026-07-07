from app.domain.services.webhook_signature import compute_signature, verify_signature

SECRET = "s3cr3t-webhook"
BODY = b'{"action":"opened","issue":{"number":42}}'


class TestSignature:
    def test_valid_signature_accepted(self):
        sig = compute_signature(SECRET, BODY)
        assert sig.startswith("sha256=")
        assert verify_signature(SECRET, BODY, sig)

    def test_wrong_secret_rejected(self):
        sig = compute_signature("other-secret", BODY)
        assert not verify_signature(SECRET, BODY, sig)

    def test_tampered_body_rejected(self):
        sig = compute_signature(SECRET, BODY)
        assert not verify_signature(SECRET, BODY + b" ", sig)

    def test_missing_signature_rejected(self):
        assert not verify_signature(SECRET, BODY, None)
        assert not verify_signature(SECRET, BODY, "")

    def test_malformed_signature_rejected(self):
        assert not verify_signature(SECRET, BODY, "sha256=deadbeef")
