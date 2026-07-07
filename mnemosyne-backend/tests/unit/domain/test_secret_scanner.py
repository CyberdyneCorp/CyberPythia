import pytest

from app.domain.services.secret_scanner import has_secrets, scan_for_secrets


class TestPatternRules:
    @pytest.mark.parametrize(
        ("rule", "content"),
        [
            ("github_token", "token = ghp_" + "a1B2" * 10),
            ("github_fine_grained_pat", "auth: github_pat_" + "x9" * 35),
            ("aws_access_key", "key=AKIAIOSFODNN7EXAMPLE"),
            ("private_key_block", "-----BEGIN RSA PRIVATE KEY-----"),
            ("slack_token", "xoxb-123456789012-abcdefghijkl"),
            ("jwt", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9P"),
            ("generic_assignment", 'password = "correct-horse-battery-staple"'),
        ],
    )
    def test_detects(self, rule, content):
        findings = scan_for_secrets(content)
        assert findings, f"expected {rule} to be detected"
        assert findings[0].rule == rule

    def test_reports_line_numbers(self):
        content = "line one\nkey = AKIAIOSFODNN7EXAMPLE\n"
        assert scan_for_secrets(content)[0].line_number == 2


class TestEntropyRule:
    def test_high_entropy_string_flagged(self):
        content = 'value = "kJ8s2Lm9Qw4Xz7Yv1Bn6Tr3Ep5Ui0Oa2Hd8Fg4c"'
        assert any(f.rule in ("high_entropy", "generic_assignment") for f in scan_for_secrets(content))

    def test_low_entropy_long_string_not_flagged(self):
        assert not has_secrets('name = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"')


class TestCleanContent:
    def test_normal_markdown_passes(self):
        content = "# Setup\n\nRun `just install`, then set your API key in `.env`.\n"
        assert not has_secrets(content)

    def test_code_examples_with_placeholders_pass(self):
        assert not has_secrets("export GITHUB_TOKEN=<your-token-here>")
