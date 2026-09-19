#!/usr/bin/env python3
"""Offline research intake, evidence validation, export, and spending reservations.

The host agent does the research. This module never calls a paid provider.
Reservations are conservative accounting, not a provider-side spending limit.
"""
import argparse
import contextlib
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import sys
from datetime import date, datetime
from urllib.parse import urlsplit, parse_qs

from detect_state import collect_state
from output_paths import allocate_run_directory, resolve_project_root
from playbook import render_playbook
import research_store as store
from research_store import atomic_write, read_json, write_json

SOURCES = {'reddit', 'x', 'youtube', 'web', 'telegram', 'threads', 'hackernews', 'github'}
KINDS = {'post', 'comment', 'thread', 'transcript', 'web', 'model_summary'}
ID = re.compile(r'^[A-Za-z][A-Za-z0-9_-]{0,79}$')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value, name):
    require(isinstance(value, str) and bool(value.strip()), name + ' must be non-empty text')


def strings(value, name, required=False):
    require(isinstance(value, list), name + ' must be a list')
    require(not required or len(value) > 0, name + ' must not be empty')
    for item in value:
        nonempty(item, name)


def iso_date(value, name, nullable=False):
    if value is None and nullable:
        return
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value), name + ' must be an ISO date')
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(name + ' must be an ISO date') from exc


def source_date(value, name, nullable=False):
    if value is None and nullable:
        return
    nonempty(value, name)
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError(name + ' must be an ISO date or timestamp') from exc


def amount(value, name):
    require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0,
            name + ' must be finite and non-negative')


def public_url(value):
    nonempty(value, 'url')
    require(not any(c.isspace() or ord(c) < 32 for c in value), 'URL contains whitespace/control characters')
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ''
        _ = parsed.port
    except ValueError as exc:
        raise ValueError('invalid URL') from exc
    require(parsed.scheme in {'https', 'http'} and bool(host) and not parsed.username and not parsed.password,
            'only public HTTP(S) URLs without credentials are allowed')
    require('.' in host and not host.endswith(('.localhost', '.local', '.internal')) and host != 'localhost', 'private host is not allowed')
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # DNS is not resolved here: validation makes no network calls and does not fetch URLs.
        require(not host.replace('.', '').isdigit(), 'ambiguous numeric host is not allowed')
    else:
        require(ip.is_global, 'private IP is not allowed')
    return value


def source_identity(url):
    """Equate known platform permalinks, never a host-supplied alias field."""
    parsed = urlsplit(public_url(url))
    host = parsed.hostname
    query = parse_qs(parsed.query)
    if host in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'}:
        video = parsed.path.strip('/') if host == 'youtu.be' else (query.get('v') or [''])[0]
        if host != 'youtu.be' and parsed.path.startswith(('/shorts/', '/live/', '/embed/')):
            video = parsed.path.split('/')[2]
        if re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
            return ('youtube', video, (query.get('lc') or [''])[0])
    if host in {'reddit.com', 'www.reddit.com', 'old.reddit.com', 'new.reddit.com', 'np.reddit.com'}:
        parts = parsed.path.strip('/').split('/')
        if 'comments' in parts:
            tail = parts[parts.index('comments') + 1:]
            if tail and re.fullmatch('[a-z0-9]+', tail[0]):
                return ('reddit', tail[0], tail[2] if len(tail) > 2 else '')
    if host in {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'}:
        match = re.fullmatch(r'/[^/]+/status/(\d+)/?', parsed.path)
        if match:
            return ('x', match.group(1))
    return (parsed.scheme, host, parsed.port, parsed.path.rstrip('/'), parsed.query)


def validate_brief(brief):
    require(isinstance(brief, dict), 'brief must be an object')
    for key in ('goal', 'decision', 'audience', 'output_language'):
        nonempty(brief.get(key), key)
    strings(brief.get('success_criteria'), 'success_criteria', True)
    strings(brief.get('languages'), 'languages', True)
    require(set(brief['languages']) <= {'ru', 'en'}, 'languages must contain ru and/or en')
    require(len(brief['languages']) == len(set(brief['languages'])), 'duplicate language')
    require(brief['output_language'] in {'ru', 'en'}, 'output_language must be ru or en')
    strings(brief.get('sources'), 'sources', True)
    require(set(brief['sources']) <= SOURCES, 'unknown source family')
    require(len(brief['sources']) == len(set(brief['sources'])), 'duplicate source')
    strings(brief.get('seeds'), 'seeds')
    require(len(brief['seeds']) == len(set(brief['seeds'])), 'duplicate seed')
    for url in brief['seeds']:
        public_url(url)
    iso_date(brief.get('as_of'), 'as_of')
    amount(brief.get('budget_usd'), 'budget_usd')
    return brief


def readiness(brief, state=None):
    state = collect_state() if state is None else state
    providers = state.get('providers', {})
    media = state.get('local_media', {})
    routes = {
        'reddit': (bool(providers.get('perplexity') or providers.get('openrouter')), 'Perplexity or OpenRouter for discovery; free targeted archive reader; archive gaps remain possible'),
        'x': (bool(providers.get('grok')), 'xAI Grok native X search/thread reading; Monid is a separate search fallback, not equivalent thread access'),
        'youtube': (bool(media.get('yt_dlp')), 'yt-dlp for metadata, captions and bounded comments; missing captions need separately approved transcription'),
        'web': (bool(providers.get('perplexity') or providers.get('openrouter') or providers.get('gemini')), 'Perplexity/OpenRouter or Gemini search; host web tools may also be used'),
        'telegram': (bool(state.get('telegram_session')), 'Existing authorized public-channel session; no account setup performed'),
        'threads': (bool(providers.get('threads')), 'Configured Threads provider'),
        'hackernews': (True, 'Public API'), 'github': (True, 'Public API; unauthenticated rate limits apply'),
    }
    return {source: {'status': 'configured_unverified' if routes[source][0] else 'needs_connection',
                     'route': routes[source][1], 'live_verified': False} for source in brief['sources']}


def prepare(brief, project_root):
    validate_brief(brief)
    store.check_index_ownership(store.research_root(project_root))
    source_state = readiness(brief)
    root = allocate_run_directory(project_root, brief['goal'])
    if os.name != 'nt':
        root.chmod(0o700)
    store.initialize(root)
    write_json(root / 'research-brief.json', brief)
    write_json(root / 'source-readiness.json', source_state)
    plan = '# Research plan\n\n' + brief['goal'] + '\n\nDecision: ' + brief['decision']
    plan += '\n\nAs of: ' + brief['as_of'] + '\n\nLanguages: ' + ', '.join(brief['languages'])
    plan += '\n\nBudget ceiling: $' + str(brief['budget_usd'])
    plan += '\n\n1. Read supplied seeds; preserve raw evidence and gaps.\n2. Search each source/language independently.\n3. Follow useful leads into posts, comments, threads and transcripts.\n4. Seek counterexamples; distinguish direct observations from model reports.\n5. Validate a shared dossier; export playbook.html and agent-context.json.\n'
    atomic_write(root / 'research-plan.md', plan)
    write_json(root / 'spending.json', {'budget_usd': brief['budget_usd'], 'calls': []})
    index = _refresh_index(project_root)
    return {'run_dir': str(root), 'raw_dir': str(root / 'raw'),
            'processed_dir': str(root / 'processed'), 'dossier': str(store.dossier_path(root)),
            **index, 'readiness': source_state, 'network_calls': 0}


def _objects(data, name):
    value = data.get(name)
    require(isinstance(value, list) and all(isinstance(x, dict) for x in value), name + ' must be a list of objects')
    return value


def _indexed(items, name):
    result = {}
    for item in items:
        ident = item.get('id')
        require(isinstance(ident, str) and ID.fullmatch(ident), name + ' invalid id')
        require(ident not in result, name + ' duplicate id: ' + ident)
        require(ident not in {'actions', 'findings', 'coverage', 'evidence', 'questions'}, 'id collides with playbook section')
        result[ident] = item
    return result


def _refs(item, key, index, required=False):
    values = item.get(key)
    strings(values, key, required)
    require(len(values) == len(set(values)), key + ' duplicate references')
    require(all(value in index for value in values), key + ' has unknown reference')
    return [index[value] for value in values]


def validate_dossier(data, brief, root):
    validate_brief(brief)
    require(isinstance(data, dict) and data.get('schema_version') == 1, 'dossier schema_version must be 1')
    require(data.get('brief') == brief, 'dossier brief differs from saved brief')
    nonempty(data.get('summary'), 'summary')
    require(data.get('status') in {'complete', 'partial'}, 'invalid dossier status')
    strings(data.get('open_questions'), 'open_questions')
    evidence = _indexed(_objects(data, 'evidence'), 'evidence')
    claims = _indexed(_objects(data, 'claims'), 'claims')
    actions = _indexed(_objects(data, 'actions'), 'actions')
    require(not (set(evidence) & set(claims) or set(evidence) & set(actions) or set(claims) & set(actions)), 'IDs must be globally unique')
    root = Path(root).resolve()
    for item in evidence.values():
        require(item.get('source') in SOURCES, 'invalid evidence source')
        require(item.get('kind') in KINDS, 'invalid evidence kind')
        public_url(item.get('url'))
        identity = source_identity(item['url'])
        if item['source'] == 'reddit' and identity[0] == 'reddit' and item['kind'] == 'post':
            require(not identity[2], 'Reddit post evidence cannot use a comment permalink')
        require(item.get('author') is None or isinstance(item.get('author'), str), 'author must be text or null')
        source_date(item.get('published_at'), 'published_at', True)
        source_date(item.get('retrieved_at'), 'retrieved_at')
        require(item.get('language') in {'ru', 'en', 'unknown'}, 'invalid evidence language')
        nonempty(item.get('text'), 'evidence text')
        require(item.get('verification') in {'direct', 'model_reported'}, 'invalid verification')
        require(item['kind'] != 'model_summary' or item['verification'] == 'model_reported', 'model_summary cannot be direct')
        strings(item.get('limitations'), 'limitations')
        nonempty(item.get('artifact'), 'artifact')
        artifact = Path(item['artifact'])
        require((root / artifact).resolve() != store.dossier_path(root).resolve(),
                'dossier cannot be its own supporting artifact')
        if store.structured(root):
            require(artifact.parts and artifact.parts[0] in {'raw', 'processed'}, 'artifact must be under raw/ or processed/')
            target = store.local_path(root, artifact)
            require(target != store.dossier_path(root), 'dossier cannot be its own supporting artifact')
        require(not artifact.is_absolute() and (root / artifact).resolve().is_relative_to(root), 'artifact escapes run directory')
        require((root / artifact).resolve() not in {(root / 'playbook.html').resolve(), (root / 'agent-context.json').resolve()},
                'raw artifact cannot be a final export target')
        require((root / artifact).is_file(), 'raw artifact does not exist: ' + str(artifact))
    for item in claims.values():
        nonempty(item.get('text'), 'claim text')
        refs = _refs(item, 'evidence_ids', evidence)
        require(item.get('confidence') in {'supported', 'inference', 'unsupported'}, 'invalid confidence')
        iso_date(item.get('fact_date'), 'fact_date', True)
        require(isinstance(item.get('caveat'), str), 'claim caveat must be text')
        if item['confidence'] == 'supported':
            require(item['fact_date'] is not None and any(x['verification'] == 'direct' and x['published_at'] for x in refs),
                    'supported claim requires dated direct evidence and fact_date')
        if item['confidence'] != 'supported':
            nonempty(item['caveat'], 'inference/unsupported caveat')
    for item in actions.values():
        for key in ('title', 'why', 'measure', 'stop_when'):
            nonempty(item.get(key), 'action ' + key)
        strings(item.get('steps'), 'action steps', True)
        refs = _refs(item, 'claim_ids', claims, True)
        require(all(x['confidence'] != 'unsupported' for x in refs), 'unsupported claim cannot drive action')
        require(all(x['confidence'] == 'supported' for x in refs) or item.get('experimental') is True,
                'inference-driven action must be explicitly experimental')
    coverage = _objects(data, 'coverage')
    actual = set()
    partial = False
    for row in coverage:
        key = (row.get('source'), row.get('language'))
        require(key not in actual, 'duplicate coverage row')
        require(key[0] in brief['sources'] and key[1] in brief['languages'], 'unexpected coverage row')
        actual.add(key)
        require(row.get('status') in {'covered', 'partial', 'unavailable'}, 'invalid coverage status')
        nonempty(row.get('note'), 'coverage note')
        refs = _refs(row, 'evidence_ids', evidence, row['status'] == 'covered')
        require(all((x['source'], x['language']) == key for x in refs), 'coverage references wrong source/language')
        if row['status'] == 'covered':
            require(any(x['verification'] == 'direct' for x in refs), 'covered requires direct evidence')
        partial |= row['status'] != 'covered'
    require(actual == {(s, lang) for s in brief['sources'] for lang in brief['languages']}, 'missing source/language coverage')
    seeds = _objects(data, 'seeds')
    seen = set()
    for row in seeds:
        url = row.get('url')
        require(url in brief['seeds'] and url not in seen, 'unexpected or duplicate seed')
        seen.add(url)
        require(row.get('status') in {'read', 'partial', 'unavailable'}, 'invalid seed status')
        nonempty(row.get('note'), 'seed note')
        refs = _refs(row, 'evidence_ids', evidence, row['status'] == 'read')
        if row['status'] == 'read':
            require(any(x['verification'] == 'direct' and source_identity(x['url']) == source_identity(url) for x in refs), 'read seed requires direct evidence at its URL')
        partial |= row['status'] != 'read'
    require(seen == set(brief['seeds']), 'missing seed disposition')
    require(not partial or data['status'] == 'partial', 'incomplete coverage requires partial status')
    require(data['status'] != 'complete' or (evidence and claims and actions), 'complete dossier requires evidence, claims, and actions')
    return data


@contextlib.contextmanager
def run_lock(root):
    """Fail closed on interrupted/concurrent writers; never silently steal a lock."""
    path = Path(root) / '.session.lock'
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError('session is locked; inspect the prior process before removing .session.lock') from exc
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        path.unlink()


def finalize(root, data=None):
    root = Path(root).absolute()
    require(not root.is_symlink() and not root.parent.is_symlink(), 'run and research root must not be symlinks')
    root = Path(root).resolve()
    project = root.parent.parent if root.parent.name == 'research' else None
    if project is not None:
        store.check_index_ownership(store.research_root(project))
    with run_lock(root):
        brief = read_json(store.local_path(root, 'research-brief.json'))
        dossier = store.dossier_path(root)
        data = read_json(dossier) if data is None else data
        validate_dossier(data, brief, root)
        # Validate layout and source paths before replacing any output.
        store.inventory(root)
        for name in ('playbook.html', 'agent-context.json', 'artifacts.json'):
            store.local_path(root, name)
        exported = dict(data)
        exported.pop('dossier_sha256', None)
        digest = hashlib.sha256(json.dumps(exported, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        exported['dossier_sha256'] = digest
        html = render_playbook(exported)
        # Validate and render before touching either final. Individually atomic; shared
        # digest exposes a crash between replacements. Re-running finalize repairs it.
        write_json(dossier, data)
        write_json(root / 'agent-context.json', exported)
        atomic_write(root / 'playbook.html', html)
        write_json(root / 'artifacts.json', store.inventory(root))
    index = _refresh_index(project) if project is not None else {}
    return {'status': data['status'], 'playbook': str(root / 'playbook.html'), 'agent_context': str(root / 'agent-context.json'),
            'artifacts': str(root / 'artifacts.json'), **index, 'dossier_sha256': digest}


def _index_run(root):
    row = {'path': root.name, 'goal': root.name, 'as_of': '', 'status': 'incomplete',
           'playbook': None, 'agent_context': None, 'artifacts': None, 'note': ''}
    try:
        brief = validate_brief(read_json(store.local_path(root, 'research-brief.json')))
        row.update(goal=brief['goal'], as_of=brief['as_of'])
        require(not (root / '.session.lock').exists(), 'session writer is active or interrupted; inspect before reuse')
        dossier = store.dossier_path(root)
        if not any((root / name).exists() for name in store.FINALS):
            row.update(status='draft', note='Исследование ещё не экспортировано.')
            return row
        data = read_json(store.local_path(root, 'agent-context.json'))
        validate_dossier(data, brief, root)
        expected = dict(data)
        digest = expected.pop('dossier_sha256', None)
        require(digest == hashlib.sha256(json.dumps(expected, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest(), 'invalid dossier digest')
        working = read_json(dossier)
        working.pop('dossier_sha256', None)
        require(working == expected, 'dossier changed since export')
        require(store.local_path(root, 'playbook.html').read_text(encoding='utf-8') == render_playbook(data), 'final pair mismatch')
        if store.structured(root) or (root / 'artifacts.json').exists():
            store.verify_inventory(root)
            row['artifacts'] = root.name + '/artifacts.json'
        row.update(status=data['status'], playbook=root.name + '/playbook.html',
                   agent_context=root.name + '/agent-context.json',
                   note='Проверь даты, ограничения и открытые вопросы перед использованием.')
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
        row['note'] = 'Результат не готов к повторному использованию: ' + str(exc)
    return row


def rebuild_index(project_root):
    return store.rebuild(project_root, _index_run)


def _refresh_index(project_root):
    # A committed run/export must not disappear behind an index error: return
    # its paths so the host repairs the index instead of allocating another run.
    try:
        return {'project_index': rebuild_index(project_root)['project_index']}
    except (OSError, ValueError) as exc:
        return {'project_index': None, 'index_error': str(exc)}


def _summarize_spending(ledger):
    for row in ledger['calls']:
        amount(row['reserved_usd'], 'reserved_usd')
        if row.get('actual_usd') is not None: amount(row['actual_usd'], 'actual_usd')
    ledger['committed_usd'] = round(sum(x['reserved_usd'] if x.get('actual_usd') is None else x['actual_usd'] for x in ledger['calls']), 8)
    ledger['remaining_usd'] = round(ledger['budget_usd'] - ledger['committed_usd'], 8)
    return ledger


def spending(root):
    path = Path(root) / 'spending.json'
    budget = read_json(Path(root) / 'research-brief.json')['budget_usd']
    amount(budget, 'budget_usd')
    ledger = read_json(path) if path.exists() else {'budget_usd': budget, 'calls': []}
    require(ledger['budget_usd'] == budget, 'budget changed since reservations; resolve explicitly')
    return _summarize_spending(ledger)


def reserve(root, call_id, provider, max_usd, basis):
    amount(max_usd, 'reservation')
    require(max_usd > 0, 'paid request reservation must be positive')
    for key, value in [('call_id', call_id), ('provider', provider), ('basis', basis)]: nonempty(value, key)
    with run_lock(root):
        ledger = spending(root)
        require(not any(x['id'] == call_id for x in ledger['calls']), 'duplicate call reservation')
        require(ledger['committed_usd'] + max_usd <= ledger['budget_usd'] + 1e-9, 'budget ceiling exceeded; do not call provider')
        ledger['calls'].append({'id': call_id, 'provider': provider, 'reserved_usd': max_usd, 'actual_usd': None, 'basis': basis})
        write_json(Path(root) / 'spending.json', _summarize_spending(ledger))
        return spending(root)


def settle(root, call_id, actual_usd):
    if actual_usd is not None: amount(actual_usd, 'actual_usd')
    with run_lock(root):
        ledger = spending(root)
        matches = [x for x in ledger['calls'] if x['id'] == call_id]
        require(len(matches) == 1, 'unknown call reservation')
        matches[0]['actual_usd'] = actual_usd
        write_json(Path(root) / 'spending.json', _summarize_spending(ledger))
        result = spending(root)
        result['overrun'] = actual_usd is not None and actual_usd > matches[0]['reserved_usd']
        return result


def example():
    return {'schema_version': 1, 'brief': {'goal': 'REPLACE: question', 'decision': 'REPLACE: decision this research enables',
             'audience': 'Research owner', 'success_criteria': ['Dated evidence and executable next steps'], 'languages': ['ru', 'en'],
             'output_language': 'ru', 'as_of': date.today().isoformat(), 'sources': ['reddit', 'x', 'youtube', 'web'], 'seeds': [], 'budget_usd': 0},
            'summary': 'REPLACE after reading sources', 'status': 'partial', 'evidence': [], 'claims': [], 'actions': [],
            'coverage': [], 'seeds': [], 'open_questions': []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('example')
    p = commands.add_parser('prepare'); p.add_argument('--brief', required=True); p.add_argument('--project-root')
    p = commands.add_parser('index'); p.add_argument('--project-root')
    for name in ('status', 'finalize', 'reserve', 'settle'):
        p = commands.add_parser(name); p.add_argument('--run-dir', required=True)
        if name in ('reserve', 'settle'): p.add_argument('--call-id', required=True)
        if name == 'reserve':
            p.add_argument('--provider', required=True); p.add_argument('--max-usd', required=True, type=float); p.add_argument('--basis', required=True)
        if name == 'settle': p.add_argument('--actual-usd', type=float, help='omit if cost remains unknown; reservation stays committed')
    args = parser.parse_args()
    try:
        if args.command == 'example': result = example()
        elif args.command == 'prepare': result = prepare(read_json(args.brief), resolve_project_root(Path.cwd(), args.project_root))
        elif args.command == 'index': result = rebuild_index(resolve_project_root(Path.cwd(), args.project_root))
        elif args.command == 'status': result = {'readiness': readiness(read_json(Path(args.run_dir) / 'research-brief.json')), 'spending': spending(args.run_dir)}
        elif args.command == 'finalize': result = finalize(args.run_dir)
        elif args.command == 'reserve': result = reserve(args.run_dir, args.call_id, args.provider, args.max_usd, args.basis)
        else: result = settle(args.run_dir, args.call_id, args.actual_usd)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__': sys.exit(main())
