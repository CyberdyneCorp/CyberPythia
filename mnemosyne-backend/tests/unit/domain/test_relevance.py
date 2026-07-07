from app.domain.services.relevance import keyword_score, tokenize


class TestTokenize:
    def test_drops_stopwords_and_short_tokens(self):
        assert tokenize("How is the auth implemented?") == {"auth", "implemented"}

    def test_keeps_technical_tokens(self):
        assert "opencl" in tokenize("Implement OpenCL backend")
        assert "gpu-backend" in tokenize("see gpu-backend module")


class TestKeywordScore:
    def test_full_match_scores_high(self):
        assert keyword_score("OpenCL backend", "Add OpenCL backend support") == 1.0

    def test_no_match_scores_zero(self):
        assert keyword_score("OpenCL backend", "Fix login typo") == 0.0

    def test_partial_match(self):
        score = keyword_score("OpenCL backend dispatch", "backend refactor")
        assert 0.0 < score < 1.0

    def test_weights_prioritize_title(self):
        title_hit = keyword_score("opencl", "OpenCL support", "", weights=(2.0, 1.0))
        body_hit = keyword_score("opencl", "", "OpenCL support", weights=(2.0, 1.0))
        assert title_hit > body_hit

    def test_none_fields_are_safe(self):
        assert keyword_score("query terms", None, None) == 0.0

    def test_empty_query(self):
        assert keyword_score("", "anything") == 0.0
