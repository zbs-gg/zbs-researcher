"""U13 — Revenue/exit-radar connector (R22/KTD7): what's selling / sold.

channel_revenue_radar (connectors/revenue_radar.py) aggregates realized-money
signal from free sources, verified live 2026-07-18:

  - Flippa: `api.flippa.com/v3/listings` is reachable WITHOUT auth;
    `filter[status]=won` returns sold auctions with real final prices
    (current_price), profit/revenue per month, property_type and end dates.
    There is no server-side text search (unknown filters 400, `q` is
    ignored), so topic matching is client-side via the shared relevance
    floor. Ordering is by realized sold price DESC — never by votes/bids.
  - Substack: `substack.com/api/v1/categories` + `category/public/{id}/all`
    return leaderboard publications with bestseller TIER wording
    (`rankingDetail`, e.g. "Tens of thousands of paid subscribers") and
    numeric tier (`author_bestseller_tier`). Substack publishes tiers, NOT
    revenue — the report renders tier wording verbatim and never invents
    ARR numbers.
  - Whop Trends / Gumtrends are paid datasets: NOT built, one honest
    opt-in line each, zero network calls.

Sub-sources are isolated: one failing writes a note, siblings continue.
All network is mocked — no live calls in tests.
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"

scripts_path = str(SCRIPTS)
path_added = scripts_path not in sys.path
if path_added:
    sys.path.insert(0, scripts_path)
try:
    SPEC = importlib.util.spec_from_file_location("deep_research_revenue_radar", RUNNER)
    deep_research = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(deep_research)
    import connectors as connectors_pkg
    from connectors import revenue_radar  # noqa: F401 — asserts module exists
finally:
    if path_added:
        sys.path.remove(scripts_path)


TOPIC = "AI SaaS"


def flippa_listing(title, price, profit_per_month=0, revenue_per_month=0,
                   property_type="saas", bid_count=None, listing_id="1"):
    return {
        "id": listing_id,
        "title": title,
        "current_price": price,
        "display_price": price,
        "profit_per_month": profit_per_month,
        "revenue_per_month": revenue_per_month,
        "property_type": property_type,
        "bid_count": bid_count,
        "sale_method": "auction",
        "status": "won",
        "ends_at": "2026-07-10T08:00:00+10:00",
        "html_url": f"https://flippa.com/{listing_id}",
        "summary": title,
    }


def substack_pub(name, ranking_detail=None, bestseller_tier=None,
                 magnitude=None, subdomain="pub"):
    pub = {
        "name": name,
        "author_name": f"{name} Author",
        "subdomain": subdomain,
        "base_url": f"https://{subdomain}.substack.com",
        "hostname": f"{subdomain}.substack.com",
        "freeSubscriberCountOrderOfMagnitude": "100K+",
    }
    if ranking_detail is not None:
        pub["rankingDetail"] = ranking_detail
    if bestseller_tier is not None:
        pub["author_bestseller_tier"] = bestseller_tier
    if magnitude is not None:
        pub["rankingDetailOrderOfMagnitude"] = magnitude
    return pub


CATEGORIES = [
    {"id": 4, "name": "Technology", "slug": "technology"},
    {"id": 153, "name": "Finance", "slug": "finance"},
]


class FakeGetJson:
    """URL-routing stand-in for the runner's get_json. Records URLs."""

    def __init__(self, flippa_pages=None, categories=None, pubs=None,
                 errors=None):
        # flippa_pages: list of {"data": [...], "links": {...}} per page
        self.flippa_pages = flippa_pages or [{"data": [], "links": {}}]
        self.categories = categories if categories is not None else CATEGORIES
        self.pubs = pubs if pubs is not None else {"publications": []}
        self.errors = errors or {}  # substring -> exception
        self.urls = []
        self._flippa_calls = 0

    def __call__(self, url, headers=None, timeout=30):
        self.urls.append(url)
        for needle, exc in self.errors.items():
            if needle in url:
                raise exc
        if "api.flippa.com" in url:
            page = self.flippa_pages[
                min(self._flippa_calls, len(self.flippa_pages) - 1)
            ]
            self._flippa_calls += 1
            return page
        if "substack.com/api/v1/categories" in url:
            return self.categories
        if "substack.com/api/v1/category/public/" in url:
            return self.pubs
        raise AssertionError(f"unexpected get_json url: {url}")


class RevenueRadarCase(unittest.TestCase):
    def setUp(self):
        connectors_pkg.attach_runner(deep_research.__dict__)

    def run_channel(self, get_json, topic=TOPIC, max_items=10):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "revenue-radar.md"
            with mock.patch.object(deep_research, "get_json", get_json):
                n = deep_research.channel_revenue_radar(topic, out, max_items)
            return n, out.read_text(encoding="utf-8")


class FlippaTests(RevenueRadarCase):
    def test_sold_prices_and_multiples_extracted_sorted_desc(self):
        fake = FakeGetJson(flippa_pages=[{
            "data": [
                flippa_listing("AI SaaS churn reducer", 5000,
                               profit_per_month=100, listing_id="11"),
                flippa_listing("AI SaaS analytics platform", 25000,
                               profit_per_month=500, listing_id="12"),
                flippa_listing("Tiny AI SaaS side project", 900,
                               listing_id="13"),
            ],
            "links": {},
        }])
        n, text = self.run_channel(fake)
        self.assertGreaterEqual(n, 3)
        # sorted by realized price desc
        self.assertLess(text.index("$25,000"), text.index("$5,000"))
        self.assertLess(text.index("$5,000"), text.index("$900"))
        # multiple = price / annual profit where profit known
        self.assertIn("4.2", text)   # 25000 / (500*12)
        self.assertIn("https://flippa.com/12", text)
        # sold-status wording + niche map line
        self.assertIn("sold", text.lower())
        self.assertIn("microsaas", text)
        self.assertIn("infoproducts", text)

    def test_ordering_is_by_price_not_votes(self):
        fake = FakeGetJson(flippa_pages=[{
            "data": [
                flippa_listing("AI SaaS with a bidding frenzy", 300,
                               bid_count=99, listing_id="21"),
                flippa_listing("AI SaaS quiet big exit", 90000,
                               bid_count=1, listing_id="22"),
            ],
            "links": {},
        }])
        _, text = self.run_channel(fake)
        self.assertLess(
            text.index("quiet big exit"), text.index("bidding frenzy")
        )

    def test_flippa_url_requests_won_status_no_auth_header(self):
        fake = FakeGetJson()
        self.run_channel(fake)
        flippa_urls = [u for u in fake.urls if "api.flippa.com" in u]
        self.assertTrue(flippa_urls)
        self.assertIn("won", flippa_urls[0])

    def test_off_topic_sales_get_degrade_note_not_silence(self):
        fake = FakeGetJson(flippa_pages=[{
            "data": [flippa_listing("Dropshipping lingerie store", 4000,
                                    property_type="ecommerce_store",
                                    listing_id="31")],
            "links": {},
        }])
        n, text = self.run_channel(fake, topic="quantum databases")
        # nothing matched the topic: honest note, best-effort list still shown
        self.assertIn("no sold listing matched", text.lower())
        self.assertIn("$4,000", text)


class SubstackTests(RevenueRadarCase):
    def test_tier_ranked_entries_render_tier_wording_never_arr(self):
        fake = FakeGetJson(pubs={"publications": [
            substack_pub("Small But Paid",
                         ranking_detail="Thousands of paid subscribers",
                         bestseller_tier=1000, magnitude=1000,
                         subdomain="small"),
            substack_pub("The Big One",
                         ranking_detail="Tens of thousands of paid subscribers",
                         bestseller_tier=10000, magnitude=10000,
                         subdomain="big"),
            substack_pub("Free Rider", ranking_detail="Launched 2 years ago",
                         subdomain="free"),
        ]})
        n, text = self.run_channel(fake)
        self.assertGreaterEqual(n, 3)
        # tier order: 10000 before 1000 before untiered
        self.assertLess(text.index("The Big One"), text.index("Small But Paid"))
        self.assertLess(text.index("Small But Paid"), text.index("Free Rider"))
        # tier wording verbatim; revenue never invented
        self.assertIn("Tens of thousands of paid subscribers", text)
        self.assertIn("Thousands of paid subscribers", text)
        self.assertNotIn("ARR", text)
        substack_section = text[text.lower().index("substack"):]
        self.assertNotIn("$", substack_section)
        # honest framing: tiers are ranges, not revenue
        self.assertIn("tier", substack_section.lower())

    def test_category_picked_from_topic_tokens(self):
        fake = FakeGetJson(pubs={"publications": [
            substack_pub("Money Weekly",
                         ranking_detail="Thousands of paid subscribers",
                         bestseller_tier=1000, subdomain="money"),
        ]})
        self.run_channel(fake, topic="finance newsletters")
        pub_urls = [u for u in fake.urls if "category/public/" in u]
        self.assertTrue(pub_urls)
        self.assertIn("/153/", pub_urls[0])

    def test_unmatched_topic_defaults_to_technology(self):
        fake = FakeGetJson(pubs={"publications": []})
        _, text = self.run_channel(fake, topic="AI SaaS")
        pub_urls = [u for u in fake.urls if "category/public/" in u]
        self.assertIn("/4/", pub_urls[0])


class PaidSourceTests(RevenueRadarCase):
    def test_whop_and_gumtrends_skipped_honestly_with_no_network(self):
        fake = FakeGetJson()
        _, text = self.run_channel(fake)
        self.assertIn("Whop", text)
        self.assertIn("Gumtrends", text)
        self.assertIn("opt-in, not configured", text)
        for url in fake.urls:
            self.assertNotIn("whop", url.lower())
            self.assertNotIn("gumtrends", url.lower())


class DegradeTests(RevenueRadarCase):
    def test_flippa_failure_notes_and_substack_survives(self):
        fake = FakeGetJson(
            pubs={"publications": [
                substack_pub("Survivor Weekly",
                             ranking_detail="Thousands of paid subscribers",
                             bestseller_tier=1000, subdomain="survivor"),
            ]},
            errors={"api.flippa.com": RuntimeError("rate limited")},
        )
        n, text = self.run_channel(fake)
        self.assertGreaterEqual(n, 1)
        self.assertIn("Flippa", text)
        self.assertIn("unavailable", text)
        self.assertIn("Survivor Weekly", text)

    def test_substack_failure_notes_and_flippa_survives(self):
        fake = FakeGetJson(
            flippa_pages=[{
                "data": [flippa_listing("AI SaaS toolkit", 7000,
                                        listing_id="41")],
                "links": {},
            }],
            errors={"substack.com": RuntimeError("blocked")},
        )
        n, text = self.run_channel(fake)
        self.assertGreaterEqual(n, 1)
        self.assertIn("$7,000", text)
        self.assertIn("Substack", text)
        self.assertIn("unavailable", text)


class RegistryTests(unittest.TestCase):
    def test_connector_registered_keyless_direct_default(self):
        conn = deep_research.CONNECTORS["revenue-radar"]
        self.assertEqual(conn.kind, "direct")
        self.assertEqual(conn.requires, [])
        self.assertTrue(conn.default)
        self.assertTrue(conn.available())
        self.assertIn("selling", conn.source.lower())

    def test_output_name_present(self):
        self.assertEqual(
            deep_research.OUTPUT_NAMES["revenue-radar"], "revenue-radar.md"
        )


class WindowsSafetyTests(unittest.TestCase):
    def test_connector_sources_avoid_posix_only_calls(self):
        for src in sorted((SCRIPTS / "connectors").glob("*.py")):
            text = src.read_text(encoding="utf-8")
            for token in ("SIGALRM", "killpg", "fcntl", "os.fork", "setsid",
                          "pwd.", "grp."):
                self.assertNotIn(token, text, f"{src.name} uses {token}")


if __name__ == "__main__":
    unittest.main()
