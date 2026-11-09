'use strict';

// Pure selection rules shared by the reader and its regression checks.
// The declarative policy arrives with the edition, including the offline copy.
globalThis.MorningBriefing = (() => {
  function matches(story, watchlist, titleOnly = false) {
    const text = `${story.title || ''} ${titleOnly ? '' : story.excerpt || ''}`;
    return (watchlist || []).filter(phrase => {
      const escaped = String(phrase).trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      return escaped && new RegExp(`(^|[^\\p{L}\\p{N}_])${escaped}(?=$|[^\\p{L}\\p{N}_])`, 'iu').test(text);
    });
  }

  function anyPattern(title, patterns) {
    return (patterns || []).some(pattern => new RegExp(pattern, 'i').test(title));
  }

  function score(story, now, watchlist, policy) {
    const age = Math.max(0, (now - Date.parse(story.published_at)) / 3600000);
    const rules = policy.digest;
    return Math.max(0, 100 - age * 1.8) +
      (matches(story, watchlist, true).length ? rules.watch_bonus : 0) +
      (['world', 'business'].includes(story.category) && anyPattern(story.title, rules.region_patterns) ? rules.region_bonus || 0 : 0);
  }

  function select(stories, settings, policy, now) {
    const max = Number(settings.digest_size) || 9;
    // A pre-upgrade offline edition has no policy yet. Keep a short, stable
    // selection visible until a new edition supplies the current rules.
    if (!policy?.digest) return [...stories].filter(story => {
      const published = Date.parse(story.published_at);
      return Number.isFinite(published) && published <= now && published >= now - 48 * 3600000;
    }).sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at) ||
      (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)).slice(0, Math.min(max, 9));
    const rules = policy.digest;
    const scale = Math.max(1, max / policy.defaults.digest_size);
    const pool = stories.filter(story => {
      const published = Date.parse(story.published_at);
      return policy.categories.includes(story.category) && Number.isFinite(published) &&
        published <= now && published >= now - rules.max_age_hours * 3600000 &&
        !anyPattern(story.title, rules.exclude_patterns) &&
        (story.category !== 'local' || anyPattern(story.title, rules.local_patterns));
    }).map(story => ({ story, score: score(story, now, settings.watchlist, policy) }))
      .sort((a, b) => b.score - a.score || Date.parse(b.story.published_at) - Date.parse(a.story.published_at) ||
        (a.story.id < b.story.id ? -1 : a.story.id > b.story.id ? 1 : 0))
      .map(item => item.story);
    const chosen = new Set();
    const categories = {};
    const sources = {};
    function available(story) {
      const source = story.source_id || story.source || story.id;
      return !chosen.has(story.id) &&
        (categories[story.category] || 0) < Math.ceil((rules.category_caps[story.category] || 0) * scale) &&
        (sources[source] || 0) < Math.ceil(rules.source_cap * scale);
    }
    function add(story) {
      chosen.add(story.id);
      categories[story.category] = (categories[story.category] || 0) + 1;
      const source = story.source_id || story.source || story.id;
      sources[source] = (sources[source] || 0) + 1;
    }
    for (const slot of rules.slot_categories) {
      if (chosen.size >= max) break;
      const candidate = pool.find(story => slot.includes(story.category) && available(story));
      if (candidate) add(candidate);
    }
    for (const story of pool) {
      if (chosen.size >= max) break;
      if (available(story)) add(story);
    }
    return pool.filter(story => chosen.has(story.id));
  }

  function migrate(profile, policy, sources) {
    if (!policy?.version) return false;
    const before = JSON.stringify(profile);
    const settings = profile.settings = { ...profile.settings };
    if ((profile.briefing_version || 0) < policy.version) {
      if (JSON.stringify(settings.watchlist) === JSON.stringify(policy.legacy.watchlist)) {
        settings.watchlist = [...policy.defaults.watchlist];
      }
      if (settings.digest_size === policy.legacy.digest_size) settings.digest_size = policy.defaults.digest_size;
    }
    const ids = sources.map(source => source.id);
    if (Array.isArray(settings.enabled_sources)) {
      const known = new Set(profile.known_source_ids || policy.legacy.source_ids);
      const enabled = new Set(settings.enabled_sources);
      const addNew = enabled.size > 0;
      settings.enabled_sources = ids.filter(id => enabled.has(id) || (addNew && !known.has(id)));
    }
    profile.known_source_ids = ids;
    profile.briefing_version = policy.version;
    return before !== JSON.stringify(profile);
  }

  return { matches, score, select, migrate };
})();
