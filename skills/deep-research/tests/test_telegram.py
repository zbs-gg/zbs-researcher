"""U6 — Telegram connector (R9; KTD4): opt-in moat channel behind a hard
separate-account warning gate.

channel_telegram (connectors/telegram.py) reads Telegram channels + comment
threads through a Telethon CLIENT session — real user-visible engagement
(views, reactions, discussion replies) that no bot API exposes. Because a
client session risks the underlying account, the connector is triple-gated:

  1. acknowledgement — env DEEP_RESEARCH_TELEGRAM_ACK=separate-account
     (exact value) or a refusal naming the hard warning (separate account
     only, ban risk, personal-DM risk);
  2. session — a Telethon *.session file resolved ONLY under the SECRETS
     dir (KTD4: never the project/output tree; a decoy .session in cwd is
     ignored); on POSIX the session file is best-effort chmod 0600;
  3. Telethon — an OPTIONAL lazy import; missing package degrades to clean
     install guidance, never a traceback crash.

All tests run OFFLINE and WITHOUT Telethon installed: the Telethon-touching
logic lives behind small module hooks (_make_client, _search_channels,
_recommend_channels) that tests monkeypatch with a fake client layer.
"""
import importlib.util
import os
import stat
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "deep-research.py"

scripts_path = str(SCRIPTS)
path_added = scripts_path not in sys.path
if path_added:
    sys.path.insert(0, scripts_path)
try:
    SPEC = importlib.util.spec_from_file_location("deep_research_telegram", RUNNER)
    deep_research = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(deep_research)
    import connectors as connectors_pkg
    from connectors import telegram as telegram_mod
finally:
    if path_added:
        sys.path.remove(scripts_path)


TOPIC = "ai research tools"
ACK_ENV = "DEEP_RESEARCH_TELEGRAM_ACK"
ACK_VALUE = "separate-account"


class Obj:
    """Attribute bag standing in for Telethon entities/messages."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def reaction(count):
    return Obj(count=count)


def make_msg(mid, text, views=0, reactions=(), replies=0, date=None, sender=None):
    return Obj(
        id=mid,
        message=text,
        views=views,
        reactions=Obj(results=[reaction(c) for c in reactions]) if reactions else None,
        replies=Obj(replies=replies) if replies else None,
        date=date,
        sender=sender,
    )


class FakeClient:
    """Duck-typed Telethon client: get_entity / iter_messages / disconnect."""

    def __init__(self, entities=None, posts=None, comments=None, fail_iter=None):
        self.entities = entities or {}   # username -> entity Obj
        self.posts = posts or {}         # username -> [msg]
        self.comments = comments or {}   # (username, post_id) -> [msg]
        self.fail_iter = fail_iter
        self.disconnected = False

    def get_entity(self, handle):
        key = str(handle).lstrip("@")
        if key not in self.entities:
            raise ValueError(f"No user has {handle!r} as username")
        return self.entities[key]

    def iter_messages(self, entity, limit=None, reply_to=None):
        if self.fail_iter is not None:
            raise self.fail_iter
        name = getattr(entity, "username", None)
        if reply_to is not None:
            return list(self.comments.get((name, reply_to), []))[:limit]
        return list(self.posts.get(name, []))[:limit]

    def disconnect(self):
        self.disconnected = True


class TelegramCase(unittest.TestCase):
    """Base: wire THIS module's deep-research copy into the connectors
    package, isolate env, point SECRETS at a tmp dir, and chdir into a
    decoy project carrying a .session that must NEVER be picked up."""

    def setUp(self):
        connectors_pkg.attach_runner(deep_research.__dict__)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(ACK_ENV, None)

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.secrets = Path(tmp.name) / "secrets"
        self.secrets.mkdir()
        patcher = mock.patch.object(deep_research, "SECRETS", self.secrets)
        patcher.start()
        self.addCleanup(patcher.stop)

        # KTD4 decoy: a session file inside the project/cwd tree.
        self.project = Path(tmp.name) / "project"
        self.project.mkdir()
        (self.project / "decoy.session").write_text("decoy", encoding="utf-8")
        previous_cwd = os.getcwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, previous_cwd)

    def add_session(self, name="research.session"):
        path = self.secrets / name
        path.write_text("fake-telethon-session", encoding="utf-8")
        return path

    def run_channel(self, query, max_items=10):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "telegram.md"
            n = deep_research.channel_telegram(query, out, max_items)
            return n, out.read_text(encoding="utf-8")


class AckGateTests(TelegramCase):
    def test_refusal_without_ack_names_the_hard_warning(self):
        self.add_session()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "telegram.md"
            with self.assertRaises(RuntimeError) as ctx:
                deep_research.channel_telegram(TOPIC, out, 10)
            self.assertFalse(out.exists())  # refusal writes nothing
        message = str(ctx.exception)
        lowered = message.lower()
        for needle in ("separate", "personal", "ban"):
            self.assertIn(needle, lowered)
        self.assertIn(ACK_ENV, message)
        self.assertIn(ACK_VALUE, message)

    def test_wrong_ack_value_still_refused(self):
        os.environ[ACK_ENV] = "yes"
        self.add_session()
        with self.assertRaises(RuntimeError) as ctx:
            self.run_channel(TOPIC)
        self.assertIn(ACK_ENV, str(ctx.exception))


class SessionGateTests(TelegramCase):
    def setUp(self):
        super().setUp()
        os.environ[ACK_ENV] = ACK_VALUE

    def test_no_session_in_secrets_gives_guidance_and_ignores_cwd_decoy(self):
        # cwd (decoy project) DOES contain a .session — it must be ignored.
        with self.assertRaises(RuntimeError) as ctx:
            self.run_channel(TOPIC)
        message = str(ctx.exception)
        self.assertIn(".session", message)
        self.assertIn(str(self.secrets), message)
        self.assertNotIn("decoy", message)

    def test_session_resolves_under_secrets_only_and_is_chmodded(self):
        session = self.add_session()
        seen = {}

        def fake_factory(session_path):
            seen["path"] = Path(session_path)
            return FakeClient(
                entities={"acmeai": Obj(username="acmeai", title="Acme AI",
                                        broadcast=True)}
            )

        with mock.patch.object(telegram_mod, "_make_client", fake_factory):
            n, text = self.run_channel("@acmeai")
        resolved = seen["path"].resolve()
        self.assertEqual(resolved, session.resolve())
        self.assertIn(str(self.secrets.resolve()), str(resolved))
        self.assertNotIn(str(self.project.resolve()), str(resolved))
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(session.stat().st_mode), 0o600)
        self.assertEqual(n, 0)
        self.assertIn("No channel posts", text)  # honest empty, not fake data


class TelethonMissingTests(TelegramCase):
    def test_missing_telethon_gives_install_guidance(self):
        os.environ[ACK_ENV] = ACK_VALUE
        self.add_session()
        # Force the import to fail even if Telethon happens to be installed.
        with mock.patch.dict(sys.modules, {"telethon": None,
                                           "telethon.sync": None}):
            with self.assertRaises(RuntimeError) as ctx:
                self.run_channel(TOPIC)
        message = str(ctx.exception)
        self.assertIn("pip install telethon", message)
        self.assertIn("skipped", message.lower())
        self.assertNotIsInstance(ctx.exception, ImportError)


class PostsAndCommentsTests(TelegramCase):
    def setUp(self):
        super().setUp()
        os.environ[ACK_ENV] = ACK_VALUE
        self.add_session()

    def make_client(self):
        entity = Obj(username="acmeai", title="Acme AI", broadcast=True)
        posts = {"acmeai": [
            make_msg(101, "New ai research tools drop: agents that read papers",
                     views=1200, reactions=(30, 15), replies=2,
                     date=datetime(2026, 7, 1)),
            make_msg(102, "Weekend photo dump", views=90000, reactions=(5,),
                     replies=0, date=datetime(2026, 6, 2)),
        ]}
        comments = {("acmeai", 101): [
            make_msg(201, "Tried it on our lab corpus — solid", reactions=(3,),
                     sender=Obj(username="maria_r", first_name="Maria")),
            make_msg(202, "Ban risk though?",
                     sender=Obj(username=None, first_name="Olek")),
        ]}
        return FakeClient(entities={"acmeai": entity}, posts=posts,
                          comments=comments)

    def test_markdown_carries_posts_comments_reactions_links(self):
        client = self.make_client()
        with mock.patch.object(telegram_mod, "_make_client", lambda s: client):
            n, text = self.run_channel("@acmeai")
        self.assertEqual(n, 2)
        self.assertIn("Acme AI", text)
        self.assertIn("@acmeai", text)
        self.assertIn("agents that read papers", text)
        self.assertIn("views 1,200", text)
        self.assertIn("reactions 45", text)      # 30 + 15
        self.assertIn("comments 2", text)
        self.assertIn("https://t.me/acmeai/101", text)
        self.assertIn("@maria_r", text)
        self.assertIn("solid", text)
        self.assertIn("(reactions 3)", text)
        self.assertTrue(client.disconnected)

    def test_discovery_uses_search_and_recommendations(self):
        chan_a = Obj(username="ai_tools_daily", title="AI Tools Daily",
                     broadcast=True)
        chan_b = Obj(username="paper_radar", title="Paper Radar",
                     broadcast=True)
        client = FakeClient(posts={
            "ai_tools_daily": [make_msg(1, "ai research tools roundup",
                                        views=100, date=datetime(2026, 7, 3))],
            "paper_radar": [make_msg(7, "new ai research tools thread",
                                     views=50, date=datetime(2026, 7, 4))],
        })
        calls = {}

        def fake_search(_client, query, limit=10):
            calls["search"] = query
            return [chan_a]

        def fake_recommend(_client, seed):
            calls["seed"] = seed
            return [chan_b]

        with mock.patch.object(telegram_mod, "_make_client", lambda s: client), \
                mock.patch.object(telegram_mod, "_search_channels", fake_search), \
                mock.patch.object(telegram_mod, "_recommend_channels",
                                  fake_recommend):
            n, text = self.run_channel(TOPIC)
        self.assertEqual(calls["search"], TOPIC)
        self.assertIs(calls["seed"], chan_a)
        self.assertEqual(n, 2)
        self.assertIn("ai_tools_daily", text)
        self.assertIn("paper_radar", text)

    def test_auth_failure_from_client_propagates(self):
        err = RuntimeError(
            "The key is not registered in the system (AUTH_KEY_UNREGISTERED)"
        )
        client = FakeClient(
            entities={"acmeai": Obj(username="acmeai", title="Acme AI",
                                    broadcast=True)},
            fail_iter=err,
        )
        with mock.patch.object(telegram_mod, "_make_client", lambda s: client):
            with self.assertRaises(RuntimeError) as ctx:
                self.run_channel("@acmeai")
        self.assertIn("AUTH_KEY_UNREGISTERED", str(ctx.exception))
        self.assertTrue(client.disconnected)  # finally-close even on failure


class RegistryTests(unittest.TestCase):
    def test_connector_registered_off_by_default(self):
        conn = deep_research.CONNECTORS["telegram"]
        self.assertEqual(conn.kind, "direct")
        self.assertFalse(conn.default)
        self.assertEqual(conn.requires, [])
        self.assertIsNone(conn.fallback_key)
        self.assertTrue(conn.available())

    def test_not_in_default_selection(self):
        live, skipped = deep_research.select_connectors(None, None)
        names = [c.name for c in live] + [c.name for c in skipped]
        self.assertNotIn("telegram", names)

    def test_only_telegram_selects_it(self):
        live, _skipped = deep_research.select_connectors("telegram", None)
        self.assertEqual([c.name for c in live], ["telegram"])

    def test_output_name(self):
        self.assertEqual(deep_research.OUTPUT_NAMES["telegram"], "telegram.md")


class WindowsSafetyTests(unittest.TestCase):
    def test_connector_source_avoids_posix_only_calls(self):
        source = (SCRIPTS / "connectors" / "telegram.py").read_text(
            encoding="utf-8"
        )
        for token in ("SIGALRM", "killpg", "fcntl", "os.fork", "setsid",
                      "pwd.", "grp."):
            self.assertNotIn(token, source)

    def test_chmod_is_posix_guarded_best_effort(self):
        source = (SCRIPTS / "connectors" / "telegram.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("os.chmod", source)
        self.assertIn('os.name != "posix"', source)


if __name__ == "__main__":
    unittest.main()
