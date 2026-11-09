'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
const policy = JSON.parse(fs.readFileSync(path.join(root, 'static/briefing.json'), 'utf8'));
const selectionCode = fs.readFileSync(path.join(root, 'static/briefing.js'), 'utf8');
const hostedCode = fs.readFileSync(path.join(root, 'static/hosted.js'), 'utf8');
const plain = value => JSON.parse(JSON.stringify(value));
const anchor = Date.parse('2026-11-08T01:00:00Z');
const settings = { ...policy.defaults, retention_days: 30 };

function story(id, category, extra = {}) {
  return { id, title: `A useful ${category} development ${id}`, category, source_id: `${category}-${id}`,
    source: 'Test publisher', url: `https://example.org/${id}`, published_at: new Date(anchor - 3600000).toISOString(),
    discovered_at: new Date(anchor).toISOString(), ...extra };
}

function runtime(edition, profile = {}) {
  const storage = new Map([['morning-signal-hosted-profile', JSON.stringify(profile)]]);
  const context = vm.createContext({ URL, AbortSignal, Date,
    localStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) },
    fetch: async () => ({ ok: true, json: async () => edition }) });
  context.window = context;
  vm.runInContext(selectionCode, context);
  if (edition) vm.runInContext(hostedCode, context);
  return { api: context.morningSignalHosted, briefing: context.MorningBriefing, storage };
}

test('nine-story selection keeps breadth despite many matching car stories', () => {
  const { briefing } = runtime();
  const rows = ['world', 'business', 'tech', 'science', 'cars', 'animals', 'gaming']
    .flatMap(category => [story(`${category}-1`, category), story(`${category}-2`, category)]);
  rows.push(...Array.from({ length: 20 }, (_, n) => story(`car-${n}`, 'cars', { title: 'Porsche 944 Alpina Brabus' })));
  const selected = briefing.select(rows, settings, policy, anchor);
  assert.equal(selected.length, 9);
  assert.equal(selected.filter(row => row.category === 'cars').length, 1);
  for (const category of ['world', 'business', 'tech', 'science', 'animals', 'gaming']) {
    assert.ok(selected.some(row => row.category === category), category);
  }
  const afterRead = briefing.select(rows.map(row => ({ ...row, read: true })), settings, policy, anchor);
  assert.deepEqual(plain(afterRead.map(row => row.id)), plain(selected.map(row => row.id)));
});

test('quiet editions stay short; no stale, future, promotional or routine local filler', () => {
  const { briefing } = runtime();
  const rows = [story('good', 'science'), story('stale', 'world', { published_at: new Date(anchor - 49 * 3600000).toISOString() }),
    story('future', 'business', { published_at: new Date(anchor + 3600000).toISOString() }),
    story('promo', 'cars', { title: 'Best deals on car accessories' }),
    story('gossip', 'local', { title: 'Politician spotted at dinner' }),
    story('flood', 'local', { title: 'Flood evacuations across Malaysia' })];
  assert.deepEqual(plain(briefing.select(rows, settings, policy, anchor).map(row => row.id)), ['flood', 'good']);
});

test('custom larger limits scale topic and publisher caps', () => {
  const { briefing } = runtime();
  const rows = policy.categories.flatMap(category => Array.from({ length: 12 }, (_, n) =>
    story(`${category}-${n}`, category, { title: category === 'local' ? `Flood evacuations ${n}` : `Research update ${n}` })));
  const selected = briefing.select(rows, { ...settings, digest_size: 24 }, policy, anchor);
  assert.equal(selected.length, 24);
  assert.ok(selected.filter(row => row.category === 'cars').length <= 3);
});

test('older cached editions remain readable without new policy or network', async () => {
  const old = edition();
  delete old.briefing;
  old.settings.digest_size = 15;
  const run = runtime(old);
  run.storage.set('morning-signal-state', JSON.stringify(old));
  const restored = run.api.restore();
  const selected = run.briefing.select(restored.stories, restored.settings, restored.briefing,
    Date.parse(restored.refresh.last_success_at));
  assert.equal(selected.length, 1);
  assert.equal(selected[0].id, 'current');
});

test('watch phrases have boundaries and overlapping interests get one small boost', () => {
  const { briefing } = runtime();
  assert.deepEqual(plain(briefing.matches({ title: 'He said the trailer is ready' }, ['AI'])), []);
  assert.deepEqual(plain(briefing.matches({ title: 'AI inference on 987.2 hardware' }, ['AI', '987.2'])), ['AI', '987.2']);
  const row = story('car', 'cars', { title: 'Porsche 944 Brabus engineering' });
  assert.equal(briefing.score(row, anchor, ['Porsche 944'], policy), briefing.score(row, anchor, ['Porsche 944', 'Brabus'], policy));
});

test('legacy defaults migrate once, preserving custom settings and disabled sources', () => {
  const { briefing } = runtime();
  const profile = { settings: { watchlist: policy.legacy.watchlist, digest_size: 15, enabled_sources: ['ars'], muted_keywords: ['spoiler'] } };
  const sources = [{ id: 'ars' }, { id: 'physanimals' }, { id: 'bbcworld' }];
  briefing.migrate(profile, policy, sources);
  assert.equal(profile.settings.digest_size, 9);
  assert.deepEqual(plain(profile.settings.watchlist), policy.defaults.watchlist);
  assert.deepEqual(profile.settings.enabled_sources, ['ars', 'bbcworld']);
  assert.deepEqual(profile.settings.muted_keywords, ['spoiler']);
  profile.settings.digest_size = 15;
  profile.settings.watchlist = ['custom'];
  briefing.migrate(profile, policy, sources);
  assert.equal(profile.settings.digest_size, 15);
  assert.deepEqual(profile.settings.watchlist, ['custom']);
  const off = { settings: { enabled_sources: [], watchlist: [], digest_size: 24 } };
  briefing.migrate(off, policy, sources);
  assert.deepEqual(off.settings.enabled_sources, []);
  assert.deepEqual(off.settings.watchlist, []);
  assert.equal(off.settings.digest_size, 24);
});

function edition() {
  const now = new Date().toISOString();
  return { briefing: policy, settings, sources: [{ id: 'ars', category: 'tech' }, { id: 'bbcworld', category: 'world' }],
    stories: [story('current', 'tech', { source_id: 'ars', published_at: now, discovered_at: now })],
    refresh: { last_success_at: now }, updated_at: now };
}

test('hosted migration, saving, reload and backup roundtrip preserve retired-source bookmarks', async () => {
  const bookmark = story('retired', 'culture', { source_id: 'variety', published_at: '2020-01-01T00:00:00Z' });
  const profile = { settings: { watchlist: policy.legacy.watchlist, digest_size: 15, enabled_sources: ['ars'] }, bookmarks: [bookmark], read: ['current'] };
  const run = runtime(edition(), profile);
  const initial = await run.api('/api/state');
  assert.equal(initial.settings.digest_size, 9);
  assert.ok(initial.stories.find(row => row.id === 'retired').saved);
  assert.ok(initial.stories.find(row => row.id === 'current').read);
  await run.api('/api/settings', { digest_size: 15, enabled_sources: ['ars', 'bbcworld'], watchlist: ['custom'] });
  await run.api('/api/story', { id: 'current', saved: true });
  const backup = await run.api('/api/backup');
  const destination = runtime(edition(), { bookmarks: [story('existing', 'gaming')] });
  await destination.api('/api/state');
  await destination.api('/api/backup', plain(backup));
  await destination.api('/api/backup', plain(backup));
  const restored = await destination.api('/api/state');
  assert.equal(restored.settings.digest_size, 15);
  assert.deepEqual(plain(restored.settings.watchlist), ['custom']);
  assert.deepEqual(plain(restored.stories.filter(row => row.saved).map(row => row.id)).sort(), ['current', 'existing', 'retired']);
  const before = destination.storage.get('morning-signal-hosted-profile');
  await assert.rejects(destination.api('/api/backup', { ...plain(backup), bookmarks: [{ ...bookmark, url: 'javascript:bad()' }] }));
  assert.equal(destination.storage.get('morning-signal-hosted-profile'), before);
  const reopened = runtime(edition(), JSON.parse(before));
  assert.equal((await reopened.api('/api/state')).settings.digest_size, 15);
});

test('legacy backup import migrates without discarding destination bookmarks', async () => {
  const run = runtime(edition(), { bookmarks: [story('kept', 'cars')] });
  await run.api('/api/state');
  const backup = { format: 'morning-signal-backup', version: 1,
    settings: { digest_size: 15, watchlist: policy.legacy.watchlist, enabled_sources: [] }, bookmarks: [] };
  const restored = await run.api('/api/backup', backup);
  assert.equal(restored.settings.digest_size, 9);
  assert.deepEqual(plain(restored.settings.enabled_sources), []);
  assert.ok(restored.stories.find(row => row.id === 'kept').saved);
});
