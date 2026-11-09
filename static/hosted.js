'use strict';

(() => {
  const PROFILE_KEY = 'morning-signal-hosted-profile';
  const CACHE_KEY = 'morning-signal-state';
  const BACKUP_FORMAT = 'morning-signal-backup';
  const BACKUP_VERSION = 1;
  const BOOKMARK_FIELDS = ['id', 'title', 'url', 'source_id', 'source', 'category', 'published_at', 'discovered_at'];
  const DAY = 86400000;
  let pendingEdition;
  let refreshedEdition;
  let latestEdition;

  function readStorage(key) {
    try {
      return JSON.parse(localStorage.getItem(key)) || {};
    } catch {
      return {};
    }
  }

  function readProfile() {
    const profile = readStorage(PROFILE_KEY);
    return {
      settings: profile.settings || {},
      bookmarks: Array.isArray(profile.bookmarks) ? profile.bookmarks : [],
      read: Array.isArray(profile.read) ? profile.read : [],
      briefing_version: profile.briefing_version || 0,
      known_source_ids: Array.isArray(profile.known_source_ids) ? profile.known_source_ids : undefined,
    };
  }

  function writeProfile(profile) {
    try {
      localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    } catch {
      throw new Error('This browser could not store your changes. Check its site storage settings.');
    }
  }

  function getEdition() {
    if (!pendingEdition) {
      pendingEdition = fetch('/edition.json', { cache: 'no-cache', signal: AbortSignal.timeout(15000) })
        .then(async response => {
          if (!response.ok) throw new Error('Could not load the latest edition.');
          const edition = await response.json();
          if (!Array.isArray(edition.stories) || !Array.isArray(edition.sources) || !edition.settings) {
            throw new Error('The latest edition is incomplete.');
          }
          latestEdition = edition;
          return edition;
        })
        .finally(() => { pendingEdition = undefined; });
    }
    return pendingEdition;
  }

  function publicationTime(story) {
    const time = Date.parse(story.published_at);
    return Number.isNaN(time) ? Date.parse(story.discovered_at) : time;
  }

  function snapshot(edition, profile) {
    const previous = readStorage(CACHE_KEY);
    const base = edition || previous;
    const sources = base.sources || [];
    MorningBriefing.migrate(profile, base.briefing, sources);
    const settings = {
      watchlist: [],
      muted_keywords: [],
      digest_size: 9,
      retention_days: 30,
      enabled_sources: sources.map(source => source.id),
      ...base.settings,
      ...profile.settings,
    };
    const enabled = new Set(settings.enabled_sources);
    const bookmarked = new Set(profile.bookmarks.map(story => story.id));
    const read = new Set(profile.read);
    const stories = new Map();
    const categories = new Map(sources.map(source => [source.id, source.category]));
    for (const row of [...profile.bookmarks, ...(previous.stories || []), ...(edition?.stories || [])]) {
      // Scores and visibility are recalculated from this browser's preferences.
      const { saved, read: wasRead, watch_matches, muted, score, enabled: wasEnabled, ...story } = row;
      const original = stories.get(story.id);
      stories.set(story.id, {
        ...story,
        category: categories.get(story.source_id) || story.category,
        // Keep the original date even if a feed omits dates on later builds.
        published_at: original?.published_at || story.published_at,
        discovered_at: original?.discovered_at || story.discovered_at,
        saved: bookmarked.has(story.id),
        read: read.has(story.id),
      });
    }
    const cutoff = Date.now() - settings.retention_days * DAY;
    const unsaved = [...stories.values()]
      .filter(story => !story.saved && publicationTime(story) >= cutoff)
      .sort((left, right) => publicationTime(right) - publicationTime(left))
      .slice(0, 600);
    return {
      ...base,
      stories: [...stories.values()].filter(story => story.saved).concat(unsaved),
      sources: sources.map(source => ({ ...source, enabled: enabled.has(source.id) })),
      settings,
      digest_ids: null,
      refresh: { ...base.refresh, running: false },
    };
  }

  function updateStory(body, profile, state) {
    const story = state.stories.find(item => item.id === body.id);
    if (!story) throw new Error('This story is no longer available.');
    if (typeof body.saved === 'boolean') {
      profile.bookmarks = profile.bookmarks.filter(item => item.id !== story.id);
      if (body.saved) profile.bookmarks.push(story);
      writeProfile(profile);
      return { story: { id: story.id, saved: body.saved } };
    }
    if (typeof body.read === 'boolean') {
      const availableIds = new Set(state.stories.map(item => item.id));
      profile.read = profile.read.filter(id => id !== story.id && availableIds.has(id));
      if (body.read) profile.read.push(story.id);
      writeProfile(profile);
      return { story: { id: story.id, read: body.read } };
    }
    throw new Error('Choose whether to save or mark the story read.');
  }

  function validatedSettings(body) {
    if (!body || typeof body !== 'object' || Array.isArray(body)) {
      throw new Error('Choose valid reading preferences.');
    }
    const settings = {};
    for (const key of ['watchlist', 'muted_keywords']) {
      if (!Object.hasOwn(body, key)) continue;
      if (!Array.isArray(body[key]) || body[key].some(item => typeof item !== 'string')) {
        throw new Error('Enter your topics as text.');
      }
      settings[key] = [...new Set(body[key].slice(0, 50).map(item => item.trim().slice(0, 80)).filter(Boolean))];
    }
    for (const [key, minimum, maximum] of [['digest_size', 5, 30], ['retention_days', 1, 30]]) {
      if (!Object.hasOwn(body, key)) continue;
      const value = body[key];
      if (!Number.isInteger(value) || value < minimum || value > maximum) {
        throw new Error('Choose a valid digest size and retention period.');
      }
      settings[key] = value;
    }
    if (Object.hasOwn(body, 'enabled_sources')) {
      if (!Array.isArray(body.enabled_sources) || body.enabled_sources.some(id => typeof id !== 'string' || !id)) {
        throw new Error('Choose valid news sources.');
      }
      settings.enabled_sources = [...new Set(body.enabled_sources)];
    }
    return settings;
  }

  function updateSettings(body, profile, state) {
    const settings = validatedSettings(body);
    const sourceIds = new Set(state.sources.map(source => source.id));
    if (!settings.enabled_sources || settings.enabled_sources.some(id => !sourceIds.has(id))) {
      throw new Error('Choose from the available news sources.');
    }
    if (!sourceIds.size) delete settings.enabled_sources;
    profile.settings = { ...profile.settings, ...settings };
    writeProfile(profile);
    return { settings: { ...state.settings, ...profile.settings } };
  }

  function isArticleUrl(value) {
    if (typeof value !== 'string') return false;
    try {
      const url = new URL(value);
      return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password;
    } catch { return false; }
  }

  function backupBookmark(story) {
    if (!story || BOOKMARK_FIELDS.some(key => typeof story[key] !== 'string' || !story[key].trim()) ||
        !isArticleUrl(story.url) || !Number.isFinite(publicationTime(story))) {
      throw new Error('This backup contains an invalid bookmark.');
    }
    const bookmark = Object.fromEntries(BOOKMARK_FIELDS.map(key => [key, story[key]]));
    const related = Array.isArray(story.related_sources) ? story.related_sources : [];
    bookmark.related_sources = related
      .filter(source => source && typeof source.source_id === 'string' && typeof source.source === 'string' && isArticleUrl(source.url))
      .slice(0, 3)
      .map(({ source_id, source, url }) => ({ source_id, source, url }));
    return bookmark;
  }

  function exportBackup() {
    const profile = readProfile();
    return {
      format: BACKUP_FORMAT,
      version: BACKUP_VERSION,
      settings: validatedSettings(profile.settings),
      bookmarks: profile.bookmarks.map(backupBookmark),
      briefing_version: profile.briefing_version,
      known_source_ids: profile.known_source_ids,
    };
  }

  function importBackup(backup) {
    if (backup?.format !== BACKUP_FORMAT || backup.version !== BACKUP_VERSION || !Array.isArray(backup.bookmarks)) {
      throw new Error('Choose a compatible backup exported from Morning Signal.');
    }
    const settings = validatedSettings(backup.settings);
    const imported = backup.bookmarks.map(backupBookmark);
    if (backup.briefing_version !== undefined && (!Number.isInteger(backup.briefing_version) || backup.briefing_version < 0)) {
      throw new Error('This backup contains invalid reading preferences.');
    }
    if (backup.known_source_ids !== undefined && (!Array.isArray(backup.known_source_ids) || backup.known_source_ids.some(id => typeof id !== 'string'))) {
      throw new Error('This backup contains invalid source preferences.');
    }
    const profile = readProfile();
    const bookmarks = new Map(profile.bookmarks.map(story => [story.id, story]));
    for (const story of imported) {
      if (!bookmarks.has(story.id)) bookmarks.set(story.id, story);
    }
    const restored = { ...profile, settings, bookmarks: [...bookmarks.values()],
      briefing_version: backup.briefing_version || 0, known_source_ids: backup.known_source_ids };
    const state = snapshot(latestEdition, restored);
    writeProfile(restored);
    return state;
  }

  window.morningSignalHosted = async function (path, body) {
    if (path === '/api/state' && body === undefined) {
      const edition = refreshedEdition || await getEdition();
      refreshedEdition = undefined;
      const profile = readProfile();
      const before = JSON.stringify(profile);
      const state = snapshot(edition, profile);
      // Reading remains available even when browser storage is full or disabled.
      if (before !== JSON.stringify(profile)) {
        try { writeProfile(profile); } catch { /* Explicit saves still report storage errors. */ }
      }
      return state;
    }
    if (path === '/api/refresh' && body) {
      refreshedEdition = await getEdition();
      return { ...refreshedEdition.refresh, running: false };
    }
    if (path === '/api/backup') return body === undefined ? exportBackup() : importBackup(body);
    if (body && (path === '/api/story' || path === '/api/settings')) {
      const profile = readProfile();
      const state = snapshot(latestEdition, profile);
      return path === '/api/story' ? updateStory(body, profile, state) : updateSettings(body, profile, state);
    }
    throw new Error('This action is not available in the hosted reader.');
  };
  window.morningSignalHosted.restore = () => snapshot(null, readProfile());
})();
