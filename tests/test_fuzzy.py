"""Tests for the pure-Python fuzzy matcher."""

from bookmarker.utils.fuzzy import fuzzy_score, fuzzy_search


class TestFuzzyScore:
    def test_empty_query_scores_zero(self):
        assert fuzzy_score("", "anything") == 0.0

    def test_empty_text_no_match(self):
        assert fuzzy_score("x", "") is None

    def test_exact_substring_matches(self):
        assert fuzzy_score("git", "github") is not None

    def test_case_insensitive(self):
        assert fuzzy_score("GIT", "github") is not None

    def test_non_subsequence_is_none(self):
        # 'z' is not in the text at all.
        assert fuzzy_score("gz", "github") is None

    def test_out_of_order_is_none(self):
        # 'bg' cannot be an in-order subsequence of 'github'.
        assert fuzzy_score("bg", "github") is None

    def test_subsequence_matches(self):
        # g..h..b as an ordered subsequence of 'github'
        assert fuzzy_score("ghb", "github") is not None

    def test_prefix_beats_midword(self):
        assert fuzzy_score("hub", "hubspot") > fuzzy_score("hub", "github")

    def test_substring_beats_subsequence(self):
        substring = fuzzy_score("doc", "docs")           # contiguous
        subseq = fuzzy_score("dcs", "docs")              # d-c-s subsequence
        assert substring > subseq

    def test_word_boundary_bonus(self):
        # "read" at a boundary (after space) beats the same length buried mid-word.
        boundary = fuzzy_score("read", "the read me")
        buried = fuzzy_score("read", "unreadable")
        assert boundary > buried


class TestFuzzySearch:
    def _items(self):
        return [
            {"title": "GitHub", "url": "https://github.com"},
            {"title": "GitLab", "url": "https://gitlab.com"},
            {"title": "Example", "url": "https://git.example.com/repo"},
            {"title": "News", "url": "https://news.ycombinator.com"},
        ]

    def test_returns_ranked_matches_only(self):
        results = fuzzy_search("git", self._items(), key=lambda i: (i["title"], i["url"]))
        titles = [r[0]["title"] for r in results]
        # GitHub / GitLab match on title; Example matches only via url.
        assert "GitHub" in titles and "GitLab" in titles
        assert "News" not in titles
        # sorted best-first
        scores = [r[1] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_title_match_outranks_url_only_match(self):
        results = fuzzy_search("git", self._items(), key=lambda i: (i["title"], i["url"]))
        titles = [r[0]["title"] for r in results]
        # A title hit (GitHub/GitLab) should rank above the url-only hit (Example).
        assert titles.index("GitHub") < titles.index("Example")
        assert titles.index("GitLab") < titles.index("Example")

    def test_no_match_returns_empty(self):
        results = fuzzy_search("zzzz", self._items(), key=lambda i: (i["title"], i["url"]))
        assert results == []
