'use strict';

(() => {
  const PROFILE_KEY = 'morning-signal-hosted-profile';
  const CACHE_KEY = 'morning-signal-state';
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
    const settings = {
      watchlist: [],
      muted_keywords: [],
      digest_size: 15,
      retention_days: 30,
      enabled_sources: sources.map(source => source.id),
      ...base.settings,
      ...profile.settings,
    };
    const enabled = new Set(settings.enabled_sources);
    const bookmarked = new Set(profile.bookmarks.map(story => story.id));
    const read = new Set(profile.read);
    const stories = new Map();
    for (const row of [...profile.bookmarks, ...(previous.stories || []), ...(edition?.stories || [])]) {
      // Scores and visibility are recalculated from this browser's preferences.
      const { saved, read: wasRead, watch_matches, muted, score, enabled: wasEnabled, ...story } = row;
      const original = stories.get(story.id);
      stories.set(story.id, {
        ...story,
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

  function updateSettings(body, profile, state) {
    for (const key of ['watchlist', 'muted_keywords']) {
      if (!Array.isArray(body[key]) || body[key].some(item => typeof item !== 'string')) {
        throw new Error('Enter your topics as text.');
      }
      profile.settings[key] = [...new Set(body[key].slice(0, 50).map(item => item.trim().slice(0, 80)).filter(Boolean))];
    }
    for (const [key, minimum, maximum] of [['digest_size', 5, 30], ['retention_days', 1, 30]]) {
      const value = body[key];
      if (!Number.isInteger(value) || value < minimum || value > maximum) {
        throw new Error('Choose a valid digest size and retention period.');
      }
      profile.settings[key] = value;
    }
    const sourceIds = new Set(state.sources.map(source => source.id));
    if (!Array.isArray(body.enabled_sources) || body.enabled_sources.some(id => !sourceIds.has(id))) {
      throw new Error('Choose from the available news sources.');
    }
    if (sourceIds.size) profile.settings.enabled_sources = [...new Set(body.enabled_sources)];
    writeProfile(profile);
    return { settings: { ...state.settings, ...profile.settings } };
  }

  window.morningSignalHosted = async function (path, body) {
    if (path === '/api/state' && body === undefined) {
      const edition = refreshedEdition || await getEdition();
      refreshedEdition = undefined;
      return snapshot(edition, readProfile());
    }
    if (path === '/api/refresh' && body) {
      refreshedEdition = await getEdition();
      return { ...refreshedEdition.refresh, running: false };
    }
    if (body && (path === '/api/story' || path === '/api/settings')) {
      const profile = readProfile();
      const state = snapshot(latestEdition, profile);
      return path === '/api/story' ? updateStory(body, profile, state) : updateSettings(body, profile, state);
    }
    throw new Error('This action is not available in the hosted reader.');
  };
  window.morningSignalHosted.restore = () => snapshot(null, readProfile());
})();
