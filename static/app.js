'use strict';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const CATEGORIES = {
  all: { label: 'Everything', color: '#676d5a' },
  gaming: { label: 'Gaming', color: '#8a583c' },
  tech: { label: 'Tech', color: '#536b70' },
  culture: { label: 'Culture', color: '#8e6273' },
  science: { label: 'Science', color: '#626b99' },
  animals: { label: 'Animals', color: '#5a7950' },
  motorsport: { label: 'Motorsport', color: '#aa533a' },
  local: { label: 'Malaysia', color: '#947a3e' },
};
const ICONS = {
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
  sunrise: '<path d="M3 17h18M6 20h12m-8 3h4M6 15a6 6 0 0 1 12 0M12 2v3M5 5l2 3m12-3-2 3M2 11l3 1m17-1-3 1"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  radar: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="M12 12l7-7"/><circle cx="12" cy="12" r="1"/>',
  bookmark: '<path d="M6 3h12v18l-6-4-6 4z"/>',
  settings: '<path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z"/><path d="m9 3 1-1h4l1 3 3 1 3 2v4l-2 2-1 3-2 3h-4l-2-2-3-1-3-2v-4l2-2 1-3z"/>',
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.1 6a8 8 0 0 1 13.2 3M4.7 15A8 8 0 0 0 18 18"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  arrow: '<path d="M6 18 18 6M6 6h12v12"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
};
let model = { stories: [], sources: [], settings: {}, refresh: {} };
const hosted = typeof window.morningSignalHosted === 'function';
let view = ['today', 'all', 'watchlist', 'saved'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'today';
let category = 'all';
let query = '';
let loaded = false;
let fetching = false;
let reloadingEdition = false;
let disconnected = false;
let shuttingDown = false;
let pollTimer;
let toastTimer;
let searchTimer;
let lastDialogTrigger = null;
const pendingStories = new Set();

function node(tag, className, content) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (content !== undefined && content !== null) element.textContent = String(content);
  return element;
}

function icon(name) {
  const holder = node('span');
  // All SVG markup is fixed application artwork, never data from a feed.
  holder.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ICONS.arrow}</svg>`;
  return holder.firstElementChild;
}

$$('[data-icon]').forEach(element => element.append(icon(element.dataset.icon)));

function safeURL(value) {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

function linkTo(url, text, className) {
  const cleanURL = safeURL(url);
  const element = node(cleanURL ? 'a' : 'span', className, text);
  if (cleanURL) {
    element.href = cleanURL;
    element.target = '_blank';
    element.rel = 'noopener noreferrer';
  }
  return element;
}

function dateOf(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function relativeTime(value) {
  const date = dateOf(value);
  if (!date) return 'Date unavailable';
  const minutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)}h ago`;
  if (minutes < 10080) return `${Math.floor(minutes / 1440)}d ago`;
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: 'Asia/Kuala_Lumpur' }).format(date);
}

function fullDate(value) {
  const date = dateOf(value);
  return date ? new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kuala_Lumpur' }).format(date) + ' MYT' : '';
}

function toast(message) {
  clearTimeout(toastTimer);
  $('#toast').textContent = message;
  $('#toast').hidden = false;
  toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 4000);
}

async function api(path, body) {
  if (hosted) return window.morningSignalHosted(path, body);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(path, {
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
      cache: 'no-store',
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `The request could not finish (${response.status}).`);
    return data;
  } finally { clearTimeout(timer); }
}

function normalizeState(data) {
  return {
    stories: Array.isArray(data.stories) ? data.stories : [],
    sources: Array.isArray(data.sources) ? data.sources.map(source => ({
      ...source,
      error: source.error || source.last_error || (Number(source.status) >= 400 ? `Source returned HTTP ${source.status}` : null),
      item_count: source.item_count ?? source.article_count ?? 0,
      last_fetched_at: source.last_fetched_at || source.last_checked_at,
    })) : [],
    settings: data.settings || {},
    refresh: data.refresh || {},
    digest_ids: Array.isArray(data.digest_ids) ? data.digest_ids : null,
    stats: data.stats || {},
  };
}

function cacheState() {
  try { localStorage.setItem('morning-signal-state', JSON.stringify(model)); } catch { /* Browser storage can be unavailable or full. */ }
}

function schedulePoll() {
  clearTimeout(pollTimer);
  if (shuttingDown) return;
  const delay = hosted ? 300000 : model.refresh.running ? 2000 : 60000;
  pollTimer = setTimeout(loadState, delay);
}

async function loadState() {
  if (fetching || shuttingDown) return;
  fetching = true;
  try {
    model = normalizeState(await api('/api/state'));
    loaded = true;
    disconnected = false;
    cacheState();
    render();
  } catch (error) {
    disconnected = true;
    loaded = true;
    render();
  } finally {
    fetching = false;
    schedulePoll();
  }
}

function matchesWatch(story) {
  if (Array.isArray(story.watch_matches) && story.watch_matches.length) return story.watch_matches;
  const text = `${story.title || ''} ${story.excerpt || ''}`.toLocaleLowerCase();
  return (model.settings.watchlist || []).filter(word => text.includes(String(word).toLocaleLowerCase()));
}

function storyIsCurrent(story) {
  if (story.saved) return true;
  const days = Number(model.settings.retention_days) || 30;
  const published = dateOf(story.published_at) || dateOf(story.discovered_at);
  return !published || published.getTime() >= Date.now() - days * 86400000;
}

function availableStories(includeHidden = false) {
  const enabled = new Set(model.sources.filter(source => source.enabled !== false).map(source => source.id));
  const muted = (model.settings.muted_keywords || []).map(word => String(word).toLocaleLowerCase()).filter(Boolean);
  return model.stories.filter(story => {
    if (!storyIsCurrent(story)) return false;
    if (!includeHidden && model.sources.length && story.source_id && !enabled.has(story.source_id)) return false;
    if (!includeHidden && story.muted) return false;
    if (!includeHidden && muted.length) {
      const text = `${story.title || ''} ${story.excerpt || ''}`.toLocaleLowerCase();
      if (muted.some(word => text.includes(word))) return false;
    }
    return true;
  });
}

function rank(stories, { now = Date.now(), preferUnread = true } = {}) {
  if (hosted) {
    return stories.map(story => {
      const published = dateOf(story.published_at) || dateOf(story.discovered_at);
      const ageHours = published ? Math.max(0, (now - published.getTime()) / 3600000) : 168;
      const score = Math.max(0, 100 - ageHours * 1.8) + Math.min(72, matchesWatch(story).length * 48) + (preferUnread && !story.read ? 8 : 0);
      return { story, score, published };
    }).sort((a, b) => b.score - a.score || (b.published || 0) - (a.published || 0)).map(item => item.story);
  }
  return [...stories].sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0) || ((dateOf(b.published_at) || 0) - (dateOf(a.published_at) || 0)));
}

function balancedDigest(stories, unfiltered = false) {
  const max = Number(model.settings.digest_size) || 15;
  const result = [];
  const used = new Set();
  const perCategory = {};
  const perSource = {};
  // Keep the website digest tied to its edition and independent of reading progress.
  const now = dateOf(model.refresh.last_success_at)?.getTime() ?? Date.now();
  let sorted = rank(stories, { now, preferUnread: false });
  function select(story) {
    const cat = story.category || 'tech';
    const source = story.source_id || story.source || 'unknown';
    result.push(story);
    used.add(story.id);
    perCategory[cat] = (perCategory[cat] || 0) + 1;
    perSource[source] = (perSource[source] || 0) + 1;
  }
  if (hosted) {
    sorted = sorted.filter(story => !story.title?.startsWith('Pre-release-shadPS4'));
    if (unfiltered) {
      const cutoff = now - 48 * 3600000;
      const recent = sorted.filter(story => (dateOf(story.published_at) || 0) >= cutoff);
      if (recent.length) sorted = recent;
      for (const key of Object.keys(CATEGORIES)) {
        if (result.length >= max) break;
        const story = sorted.find(item => item.category === key);
        if (story) select(story);
      }
    }
  }
  const orderedResult = () => hosted ? sorted.filter(story => used.has(story.id)) : result;
  const categoryLimit = Math.max(3, Math.ceil(max / 4));
  const sourceLimit = Math.max(2, Math.ceil(max / 5));
  // Keep the front page varied; progressively relax caps if a narrow filter needs it.
  for (const [categoryCap, sourceCap] of [[categoryLimit, sourceLimit], [categoryLimit + 2, sourceLimit + 1], [max, max]]) {
    for (const story of sorted) {
      if (result.length >= max) return orderedResult();
      if (used.has(story.id)) continue;
      const cat = story.category || 'tech';
      const source = story.source_id || story.source || 'unknown';
      if ((perCategory[cat] || 0) >= categoryCap || (perSource[source] || 0) >= sourceCap) continue;
      select(story);
    }
  }
  return orderedResult();
}

function filteredStories() {
  let stories = availableStories(view === 'saved');
  if (view === 'saved') stories = stories.filter(story => story.saved);
  if (view === 'watchlist') stories = stories.filter(story => matchesWatch(story).length);
  if (category !== 'all') stories = stories.filter(story => story.category === category);
  if (query) stories = stories.filter(story => `${story.title || ''} ${story.excerpt || ''} ${story.source || ''}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  if (view === 'today' && category === 'all' && !query && model.digest_ids) {
    const index = new Map(stories.map(story => [story.id, story]));
    return model.digest_ids.map(id => index.get(id)).filter(Boolean);
  }
  return view === 'today' ? balancedDigest(stories, category === 'all' && !query) : rank(stories);
}

function renderHeading() {
  const titles = {
    today: ['THE MORNING EDITION', 'Good morning,', 'curious mind.', 'Your corner of the internet, gathered in one place.', 'Worth your attention'],
    all: ['THE OPEN INTERNET', 'A world of', 'interesting things.', 'Browse your collected stories, including earlier days. Refresh adds new articles; each card shows when it was published.', 'The latest from your sources'],
    watchlist: ['FOLLOW YOUR CURIOSITY', 'Keep an eye', 'on the good stuff.', 'New stories about the people, projects, and places on your radar.', 'On your radar'],
    saved: ['FOR A QUIETER MOMENT', 'Good stories,', 'kept for later.', 'Your bookmarked stories stay here until you remove them, even after other news expires.', 'Your reading list'],
  };
  const values = titles[view];
  $('#page-eyebrow').textContent = values[0];
  if (hosted) $('#page-title').textContent = $(`.nav-item[data-view="${view}"] > span:nth-child(2)`).textContent;
  else $('#page-title').replaceChildren(document.createTextNode(values[1]), node('br'), node('em', '', values[2]));
  const keepDays = Number(model.settings.retention_days) || 30;
  $('#page-description').textContent = view === 'all'
    ? `Unsaved stories expire after ${keepDays} ${keepDays === 1 ? 'day' : 'days'}. Bookmark anything you want to keep longer.`
    : values[3];
  $('#stories-heading').textContent = query ? 'Search results' : values[4];
  $('#watchlist-strip').hidden = view !== 'watchlist';
  $('#watchlist-chips').replaceChildren(...(model.settings.watchlist || []).map(topic => node('span', 'topic-chip', topic)));
  $$('.nav-item').forEach(button => {
    const active = button.dataset.view === view;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  });
  $$('.category-filter').forEach(button => {
    const active = button.dataset.category === category;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
}

function renderCounts() {
  const stories = availableStories();
  const availableIds = new Set(stories.map(story => story.id));
  $('#count-today').textContent = model.digest_ids
    ? model.digest_ids.filter(id => availableIds.has(id)).length
    : hosted ? balancedDigest(stories, true).length : Math.min(stories.length, Number(model.settings.digest_size) || 15);
  $('#count-all').textContent = stories.length;
  $('#count-watchlist').textContent = stories.filter(story => matchesWatch(story).length).length;
  $('#count-saved').textContent = model.stories.filter(story => story.saved).length;
}

function createStoryCard(story, index, featured = false) {
  const categoryKey = story.category !== 'all' && Object.hasOwn(CATEGORIES, story.category) ? story.category : 'tech';
  const info = CATEGORIES[categoryKey];
  const card = node('article', `story-card${featured ? ' featured' : ''}${story.read ? ' is-read' : ''}`);
  const content = hosted ? node('div', 'story-copy') : card;
  card.style.setProperty('--category-color', info.color);
  const top = node('div', 'story-topline');
  top.append(node('span', 'category-tag', info.label), node('span', 'story-number', String(index + 1).padStart(2, '0')));
  if (hosted && story.read) top.append(node('span', 'read-status', 'Read'));
  const title = node('h3');
  const titleLink = linkTo(story.url, story.title || 'Untitled story');
  titleLink.addEventListener('click', () => markRead(story, true, true));
  title.append(titleLink);
  const excerpt = node('p', 'story-excerpt', story.excerpt || 'Follow the original story for the full details.');
  const meta = node('div', 'story-meta');
  meta.append(node('span', 'story-source', story.source || 'Original source'), node('span', '', '·'));
  const time = node('time', '', relativeTime(story.published_at || story.discovered_at));
  const published = dateOf(story.published_at || story.discovered_at);
  if (published) { time.dateTime = published.toISOString(); time.title = fullDate(published); }
  meta.append(time);
  content.append(top, title);
  if (!hosted || story.excerpt) content.append(excerpt);
  content.append(meta);
  const matches = matchesWatch(story);
  if (matches.length) {
    const flags = node('div', 'story-flags');
    flags.append(...matches.slice(0, 3).map(match => node('span', 'watch-match', `Watching: ${match}`)));
    content.append(flags);
  }
  if (Array.isArray(story.related_sources) && story.related_sources.length) {
    const related = node('div', 'related-sources', 'Also covered by ');
    story.related_sources.slice(0, 3).forEach((source, sourceIndex) => {
      if (sourceIndex) related.append(document.createTextNode(', '));
      if (typeof source === 'string') related.append(document.createTextNode(source));
      else related.append(linkTo(source.url, source.name || source.source || 'another source'));
    });
    content.append(related);
  }
  const bottom = node('div', 'story-bottom');
  const readLink = linkTo(story.url, 'Read original', 'read-original');
  readLink.append(icon('arrow'));
  readLink.addEventListener('click', () => markRead(story, true, true));
  const actions = node('div', 'card-actions');
  const read = node('button', 'card-action read-action');
  read.type = 'button';
  read.title = story.read ? 'Mark unread' : 'Mark as read';
  read.setAttribute('aria-label', `${hosted ? 'Mark as read' : read.title}: ${story.title}`);
  read.setAttribute('aria-pressed', String(Boolean(story.read)));
  if (hosted) read.dataset.storyId = story.id;
  read.append(icon('check'));
  read.addEventListener('click', () => markRead(story, !story.read));
  const save = node('button', 'card-action save-action');
  save.type = 'button';
  save.title = story.saved ? 'Remove from saved' : 'Save for later';
  save.setAttribute('aria-label', `${save.title}: ${story.title}`);
  save.setAttribute('aria-pressed', String(Boolean(story.saved)));
  save.append(icon('bookmark'));
  save.addEventListener('click', () => updateStory(story, 'saved', !story.saved));
  actions.append(read, save);
  bottom.append(readLink, actions);
  content.append(bottom);
  if (hosted) {
    const art = node('img', 'category-art');
    art.alt = '';
    art.decoding = 'async';
    if (!featured) art.loading = 'lazy';
    art.src = `/static/category-${categoryKey}.svg`;
    card.append(art, content);
  }
  return card;
}

function websiteDigest(stories) {
  const board = node('div', 'edition-board');
  board.append(createStoryCard(stories[0], 0, true));
  if (stories.length > 1) {
    const rail = node('section', 'edition-rail');
    rail.append(node('h2', 'edition-subtitle', 'In this edition'));
    rail.append(...stories.slice(1, 4).map((story, index) => createStoryCard(story, index + 1)));
    board.append(rail);
  }
  if (stories.length <= 4) return [board];
  const more = node('section', 'edition-more');
  const grid = node('div', 'stories-grid');
  grid.append(...stories.slice(4).map((story, index) => createStoryCard(story, index + 4)));
  more.append(node('h2', 'edition-subtitle', 'More to explore'), grid);
  return [board, more];
}

function renderEmpty(hasReadStories) {
  const empty = node('div', 'empty-state');
  empty.append(node('span', 'empty-symbol', '✳'));
  let title = 'Nothing here just yet.';
  let description = hosted ? 'Check for the latest published edition.' : 'Refresh your sources to bring in the latest stories.';
  let buttonText = hosted ? 'Reload edition' : 'Refresh feeds';
  let action = refreshFeeds;
  if (!loaded || model.refresh.running) {
    title = 'A little curiosity is on its way.';
    description = hosted ? 'Opening the latest edition.' : 'Gathering headlines from your sources. The first edition can take a moment; you can leave this page open.';
    buttonText = null;
  } else if (hasReadStories) {
    title = 'You’re all caught up here.';
    description = 'Turn off Unread only to see the stories you’ve read.';
    buttonText = 'Show read stories';
    action = () => { $('#unread-only').checked = false; render(); };
  } else if (query || category !== 'all') {
    title = 'No stories in this corner.';
    description = 'Try a different phrase or open up your category filter.';
    buttonText = 'Clear filters';
    action = () => { category = 'all'; query = ''; $('#search').value = ''; render(); };
  } else if (view === 'saved') {
    title = 'Make room for a good read.';
    description = 'Use the bookmark on any story to keep it here for later.';
    buttonText = 'Explore today’s digest';
    action = () => changeView('today');
  } else if (view === 'watchlist') {
    title = (model.settings.watchlist || []).length ? 'Your radar is quiet for now.' : 'What are you curious about?';
    description = (model.settings.watchlist || []).length ? 'No stories match your watched topics yet. New matches will appear as your sources update.' : 'Add games, projects, people, or places, and matching stories will gather here.';
    buttonText = 'Edit watched topics';
    action = () => openSettings(true);
  } else if (disconnected) {
    title = 'Your reading room is offline.';
    description = hosted
      ? 'Check your connection and try again. This browser keeps a copy of your last edition.'
      : 'Start Morning Signal with its launch shortcut, then try again. Your saved edition is kept on this computer.';
    buttonText = 'Try again';
    action = loadState;
  } else if (model.sources.length && !model.sources.some(source => source.enabled !== false)) {
    title = 'Your source desk is quiet.';
    description = 'Turn on a few sources to start building your edition.';
    buttonText = 'Choose sources';
    action = () => openSettings();
  }
  empty.append(node('h3', '', title), node('p', '', description));
  if (buttonText) {
    const button = node('button', 'button', buttonText);
    button.addEventListener('click', action);
    empty.append(button);
  }
  return empty;
}

function renderRefresh() {
  const refresh = model.refresh;
  const running = Boolean(refresh.running) && !disconnected;
  $('#refresh-button').disabled = running || shuttingDown || reloadingEdition;
  $('#refresh-button').classList.toggle('spinning', running || reloadingEdition);
  $('#refresh-label').textContent = hosted
    ? reloadingEdition ? 'Opening…' : 'Reload edition'
    : running ? 'Gathering…' : 'Refresh feeds';
  $('#refresh-progress').hidden = !running;
  const total = Number(refresh.total) || 0;
  const completed = Number(refresh.completed) || 0;
  $('#refresh-progress-text').textContent = total ? `Checking your sources · ${Math.min(completed, total)} of ${total} complete` : 'Checking your sources…';
  $('#progress-fill').style.width = total ? `${Math.min(100, completed / total * 100)}%` : '12%';
  const refreshedAt = refresh.last_success_at || refresh.finished_at;
  const lastUpdated = refreshedAt ? `Updated ${relativeTime(refreshedAt).toLocaleLowerCase()}` : 'Ready for your first edition';
  $('#refresh-time').textContent = disconnected ? (hosted ? 'Edition unavailable' : 'Local app unavailable') : running ? 'A fresh edition is coming' : lastUpdated;
  $('#refresh-time').title = fullDate(refreshedAt);
  const notice = $('#notice');
  let text = '';
  let error = false;
  if (shuttingDown) text = 'Morning Signal has stopped. Your reading is saved. Use the launch shortcut to start it again.';
  else if (disconnected) {
    if (hosted) {
      text = model.stories.length ? 'Showing the copy saved in this browser. The latest edition could not be loaded.' : 'The edition could not be loaded. Check your connection and try again.';
    } else {
      text = model.stories.length ? 'Showing your last saved edition. Launch Morning Signal again to refresh or save changes.' : 'Morning Signal isn’t running. Use its launch shortcut, then refresh this page.';
    }
    error = true;
  } else if (refresh.error && !running) {
    text = `The latest refresh hit a problem. ${model.stories.length ? 'Your last edition is still here. ' : ''}${String(refresh.error).slice(0, 220)}`;
    error = true;
  }
  notice.hidden = !text;
  notice.textContent = text;
  notice.classList.toggle('is-error', error);
  const enabledSources = model.sources.filter(source => source.enabled !== false);
  const failed = enabledSources.filter(source => source.error || ['error', 'failed', 'unavailable'].includes(source.status));
  const indicator = $('#source-health');
  indicator.classList.toggle('warning', Boolean(failed.length));
  indicator.classList.toggle('error', enabledSources.length > 0 && failed.length === enabledSources.length);
  $('#sources-button').title = `${enabledSources.length} sources enabled${failed.length ? `, ${failed.length} need attention` : ''}`;
}

function render() {
  // Remove expired unsaved items from the browser's offline copy too.
  const currentStories = model.stories.filter(storyIsCurrent);
  if (currentStories.length !== model.stories.length) {
    model.stories = currentStories;
    cacheState();
  }
  renderHeading();
  renderCounts();
  renderRefresh();
  const matches = filteredStories();
  const unreadOnly = $('#unread-only').checked;
  const stories = unreadOnly ? matches.filter(story => !story.read) : matches;
  const frontPage = hosted && view === 'today' && category === 'all' && !query && !unreadOnly && stories.length > 0;
  const grid = $('#stories');
  grid.classList.toggle('edition-front', frontPage);
  grid.setAttribute('aria-busy', String(!loaded));
  if (!loaded && !model.stories.length) {
    grid.replaceChildren(...Array.from({ length: 6 }, () => {
      const skeleton = node('div', 'skeleton');
      skeleton.setAttribute('aria-hidden', 'true');
      skeleton.append(...Array.from({ length: 6 }, () => node('span')));
      return skeleton;
    }));
  } else if (frontPage) {
    grid.replaceChildren(...websiteDigest(stories));
  } else {
    const cards = stories.map((story, index) => createStoryCard(story, index, !hosted && view === 'today' && index === 0));
    grid.replaceChildren(...(cards.length ? cards : [renderEmpty(matches.length > 0)]));
  }
  $('#result-count').textContent = !loaded ? 'Gathering stories…' : stories.length ? `${stories.length} ${stories.length === 1 ? 'story' : 'stories'}${view === 'today' ? ' · picked for a little variety' : view === 'all' ? ' · collected across refreshes' : ''}` : '0 stories';
  if ($('#sources-dialog').open) renderSources();
}

function changeView(next) {
  view = next;
  category = 'all';
  query = '';
  $('#search').value = '';
  history.replaceState(null, '', `#${view}`);
  render();
  if (window.scrollY > 160) window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function refreshFeeds() {
  if (model.refresh.running && !disconnected) return;
  if (hosted) {
    if (fetching || reloadingEdition) return;
    reloadingEdition = true;
    renderRefresh();
  }
  $('#refresh-button').disabled = true;
  try {
    const data = await api('/api/refresh', {});
    model.refresh = data.refresh || data;
    disconnected = false;
    renderRefresh();
    await loadState();
  } catch (error) {
    toast(hosted ? 'Could not load the latest edition. Please try again.' : 'Could not start a refresh. Make sure the local app is running.');
    disconnected = true;
    renderRefresh();
  } finally {
    if (hosted) {
      reloadingEdition = false;
      renderRefresh();
    }
  }
}

async function updateStory(story, field, value, quietly = false) {
  if (pendingStories.has(story.id)) return;
  if ((!hosted && disconnected) || shuttingDown) { if (!quietly) toast('Start the local app again to save changes.'); return; }
  pendingStories.add(story.id);
  try {
    const result = await api('/api/story', { id: story.id, [field]: value });
    const index = model.stories.findIndex(item => item.id === story.id);
    if (index !== -1) model.stories[index] = { ...model.stories[index], [field]: value, ...(result.story || {}) };
    cacheState();
    const restoreReadFocus = hosted && field === 'read' && !quietly &&
      document.activeElement?.matches('.read-action') && document.activeElement.dataset.storyId === story.id;
    render();
    if (restoreReadFocus) {
      const readButton = $(`.read-action[data-story-id="${CSS.escape(story.id)}"]`);
      if (readButton) readButton.focus({ preventScroll: true });
      else $('#unread-only').focus();
    }
    if (!quietly) toast(field === 'saved' ? value ? 'Kept for a quieter moment.' : 'Removed from your saved stories.' : value ? 'Marked as read.' : 'Marked as unread.');
  } catch (error) {
    if (!quietly) toast(hosted ? error.message : 'That change could not be saved. Please try again.');
  } finally { pendingStories.delete(story.id); }
}

function markRead(story, value, quietly = false) {
  if (Boolean(story.read) === value) return;
  return updateStory(story, 'read', value, quietly);
}

function showDialog(dialog, trigger) {
  lastDialogTrigger = trigger || document.activeElement;
  dialog.showModal();
}

function closeDialog(dialog) {
  dialog.close();
  if (lastDialogTrigger && document.contains(lastDialogTrigger)) lastDialogTrigger.focus();
}

function setSelectValue(selector, value) {
  const select = $(selector);
  if (!$$('option', select).some(option => option.value === String(value))) select.append(new Option(String(value), String(value)));
  select.value = String(value);
}

function openSettings(focusWatchlist = false) {
  $('#watchlist-input').value = (model.settings.watchlist || []).join(', ');
  $('#muted-input').value = (model.settings.muted_keywords || []).join(', ');
  setSelectValue('#digest-size', model.settings.digest_size || 15);
  setSelectValue('#refresh-minutes', model.settings.refresh_minutes || 60);
  setSelectValue('#retention-days', model.settings.retention_days || 30);
  $('#settings-error').hidden = true;
  $('#backup-error').hidden = true;
  const sourceSettings = $('#source-settings');
  sourceSettings.replaceChildren();
  for (const source of model.sources) {
    const label = node('label', 'source-setting');
    const input = node('input');
    input.type = 'checkbox';
    input.value = source.id;
    input.checked = source.enabled !== false;
    input.name = 'enabled-source';
    const text = node('span', 'source-setting-text');
    text.append(node('span', 'source-setting-name', source.name), node('span', 'source-setting-category', (CATEGORIES[source.category] || CATEGORIES.tech).label));
    label.append(input, text);
    sourceSettings.append(label);
  }
  if (!model.sources.length) sourceSettings.append(node('p', 'field-help', hosted ? 'Sources will appear when the edition loads.' : 'Sources will appear when the local app connects.'));
  showDialog($('#settings-dialog'));
  if (focusWatchlist) $('#watchlist-input').focus();
}

function parsePhrases(value) {
  const seen = new Set();
  return value.split(/[,\n]/).map(item => item.trim()).filter(item => {
    if (!item || seen.has(item.toLocaleLowerCase())) return false;
    seen.add(item.toLocaleLowerCase());
    return true;
  }).slice(0, 100);
}

async function saveSettings(event) {
  event.preventDefault();
  const button = $('#save-settings');
  button.disabled = true;
  button.textContent = 'Saving…';
  $('#settings-error').hidden = true;
  try {
    const data = await api('/api/settings', {
      watchlist: parsePhrases($('#watchlist-input').value),
      muted_keywords: parsePhrases($('#muted-input').value),
      digest_size: Number($('#digest-size').value),
      refresh_minutes: Number($('#refresh-minutes').value),
      retention_days: Number($('#retention-days').value),
      enabled_sources: $$('input[name="enabled-source"]:checked').map(input => input.value),
    });
    model.settings = data.settings || model.settings;
    const enabled = new Set(model.settings.enabled_sources || []);
    model.sources.forEach(source => { source.enabled = enabled.has(source.id); });
    cacheState();
    closeDialog($('#settings-dialog'));
    render();
    toast('Your reading room, a little more you.');
    loadState();
  } catch (error) {
    const fallback = hosted ? 'Check your browser’s site storage settings.' : 'Please make sure the local app is running.';
    $('#settings-error').textContent = `Preferences could not be saved. ${error.message || fallback}`;
    $('#settings-error').hidden = false;
  } finally {
    button.disabled = false;
    button.textContent = 'Save preferences';
  }
}

function showBackupError(message) {
  const notice = $('#backup-error');
  notice.textContent = message;
  notice.hidden = false;
}

async function downloadBackup() {
  $('#backup-error').hidden = true;
  try {
    const backup = await api('/api/backup');
    const file = new Blob([JSON.stringify(backup)], { type: 'application/json' });
    const url = URL.createObjectURL(file);
    const link = node('a');
    link.href = url;
    link.download = 'morning-signal-backup.json';
    $('#backup-settings').append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    showBackupError(`Could not export your backup. ${error.message}`);
  }
}

async function restoreBackup(event) {
  const input = event.target;
  const file = input.files[0];
  input.value = '';
  if (!file) return;
  const button = $('#import-backup');
  button.disabled = true;
  $('#backup-error').hidden = true;
  try {
    if (file.size > 16 * 1024 * 1024) throw new Error('Choose a backup up to 16 MB.');
    let backup;
    try { backup = JSON.parse(await file.text()); }
    catch { throw new Error('Choose a readable JSON backup exported from Morning Signal.'); }
    model = normalizeState(await api('/api/backup', backup));
    loaded = true;
    cacheState();
    closeDialog($('#settings-dialog'));
    render();
    toast('Bookmarks and preferences imported.');
  } catch (error) {
    showBackupError(`Could not import your backup. ${error.message}`);
  } finally {
    button.disabled = false;
  }
}

function sourceStatus(source) {
  if (source.enabled === false) return ['Paused', ''];
  if (source.error || ['error', 'failed', 'unavailable'].includes(source.status)) return ['Needs attention', 'warning'];
  if (['fetching', 'running', 'loading'].includes(source.status)) return ['Checking…', ''];
  if (source.last_success_at) return ['Connected', ''];
  return ['Waiting for first refresh', 'warning'];
}

function renderSources() {
  const enabled = model.sources.filter(source => source.enabled !== false);
  const failed = enabled.filter(source => source.error || ['error', 'failed', 'unavailable'].includes(source.status));
  $('#sources-summary').textContent = `${enabled.length} sources enabled · ${failed.length ? `${failed.length} need attention` : 'Your source desk is ready'} · ${model.stories.length} stories in your library`;
  const list = $('#source-status-list');
  list.replaceChildren();
  for (const source of model.sources) {
    const row = node('div', 'source-status-row');
    const [status, kind] = sourceStatus(source);
    const dot = node('span', `health-dot ${kind}`);
    dot.setAttribute('aria-hidden', 'true');
    if (source.enabled === false) dot.style.background = '#b8bcae';
    const info = node('div', 'source-status-info');
    const title = node('div', 'source-status-title');
    title.append(linkTo(source.url, source.name || source.id), node('span', '', status));
    const detail = node('div', 'source-status-detail');
    detail.textContent = `${(CATEGORIES[source.category] || CATEGORIES.tech).label} · ${Number(source.item_count) || 0} stories${source.last_success_at ? ` · Last success ${relativeTime(source.last_success_at).toLocaleLowerCase()}` : ''}`;
    info.append(title, detail);
    if (source.error && source.enabled !== false) info.append(node('div', 'source-status-detail source-status-error', String(source.error).slice(0, 250)));
    row.append(dot, info);
    list.append(row);
  }
  if (!model.sources.length) list.append(node('p', 'dialog-intro', hosted ? 'Sources will appear when the edition loads.' : 'Connect to the local app to see your available sources.'));
}

function openSources() {
  renderSources();
  showDialog($('#sources-dialog'));
}

for (const [key, value] of Object.entries(CATEGORIES)) {
  const button = node('button', 'category-filter', hosted && key === 'all' ? 'All topics' : value.label);
  button.dataset.category = key;
  button.type = 'button';
  button.setAttribute('aria-pressed', String(key === category));
  button.addEventListener('click', () => { category = key; render(); });
  $('#category-filters').append(button);
}

$$('[data-view]').forEach(button => button.addEventListener('click', () => changeView(button.dataset.view)));
$('.brand').addEventListener('click', event => { event.preventDefault(); changeView('today'); });
$('#refresh-button').addEventListener('click', refreshFeeds);
$('#unread-only').addEventListener('change', render);
$('#search').addEventListener('input', event => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { query = event.target.value.trim(); render(); }, 150);
});
$('#settings-button').addEventListener('click', () => openSettings());
$('#mobile-settings-button').addEventListener('click', () => openSettings());
$('#edit-watchlist').addEventListener('click', () => openSettings(true));
$('#settings-form').addEventListener('submit', saveSettings);
$('#sources-button').addEventListener('click', openSources);
$('#footer-sources').addEventListener('click', openSources);
$('#manage-sources').addEventListener('click', () => { closeDialog($('#sources-dialog')); openSettings(); });
$$('.dialog-close').forEach(button => button.addEventListener('click', () => closeDialog(button.closest('dialog'))));
$$('dialog').forEach(dialog => {
  dialog.addEventListener('click', event => {
    if (event.target === dialog) {
      const rect = dialog.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeDialog(dialog);
    }
  });
  dialog.addEventListener('cancel', () => { if (lastDialogTrigger && document.contains(lastDialogTrigger)) lastDialogTrigger.focus(); });
});

if (hosted) {
  $('.sidebar').before($('.topbar'));
  $('.topbar-actions').append($('.sidebar-bottom'));
  $('.brand').replaceChildren(icon('sunrise'), document.createTextNode('Morning Signal'));
  $('[data-view="saved"] > span:nth-child(2)').textContent = 'Saved';
  $('.main-nav').after($('.search-field'));
  $('#search').placeholder = 'Search stories';
  $('.page-heading').append($('#result-count'));
  $('.section-heading').classList.add('sr-only');
  $('#backup-settings').hidden = false;
  $('#export-backup').addEventListener('click', downloadBackup);
  $('#import-backup').addEventListener('click', () => $('#backup-file').click());
  $('#backup-file').addEventListener('change', restoreBackup);
  $('#shutdown-button').closest('.shutdown-section').hidden = true;
  const interval = $('#refresh-minutes').parentElement;
  interval.hidden = true;
  interval.parentElement.classList.remove('settings-columns');
  interval.parentElement.nextElementSibling.textContent = 'Reload edition checks for the latest published digest.';
  $('#settings-dialog .dialog-intro').textContent = 'Your bookmarks and preferences are saved in this browser.';
  $('#muted-help').textContent = 'Hide stories whose headlines contain these phrases.';
  $('#retention-help').nextElementSibling.textContent = 'Use the bookmark icon to keep a story’s headline and link in Saved. Bookmarked stories do not expire.';
  $('#source-settings').previousElementSibling.textContent = 'Switch sources on or off to shape your edition.';
  $('.page-footer p span').textContent = 'Headlines belong to their publishers. Follow a story to read the original.';
}

if (!hosted) $('#shutdown-button').addEventListener('click', async () => {
  const button = $('#shutdown-button');
  button.disabled = true;
  try {
    await api('/api/shutdown', {});
    shuttingDown = true;
    clearTimeout(pollTimer);
    closeDialog($('#settings-dialog'));
    renderRefresh();
    toast('Morning Signal stopped. See you at the next edition.');
  } catch { toast('The app could not stop. You can close its server window instead.'); }
  finally { button.disabled = false; }
});

document.addEventListener('keydown', event => {
  const activeTag = document.activeElement?.tagName;
  if (event.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(activeTag) && !$$('dialog').some(dialog => dialog.open)) {
    event.preventDefault();
    $('#search').focus();
  }
  if (event.key === 'Escape' && document.activeElement === $('#search')) {
    $('#search').value = '';
    query = '';
    $('#search').blur();
    render();
  }
});
window.addEventListener('online', loadState);
window.addEventListener('hashchange', () => {
  const next = location.hash.slice(1);
  if (['today', 'all', 'watchlist', 'saved'].includes(next) && next !== view) changeView(next);
});
document.addEventListener('visibilitychange', () => { if (!document.hidden) loadState(); });

$('#edition-date').textContent = new Intl.DateTimeFormat('en-GB', {
  weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Asia/Kuala_Lumpur',
}).format(new Date());

try {
  const cached = localStorage.getItem('morning-signal-state');
  if (cached) {
    model = normalizeState(hosted ? window.morningSignalHosted.restore() : JSON.parse(cached));
    loaded = true;
  }
} catch { /* Continue without a cached edition. */ }
render();
loadState();
