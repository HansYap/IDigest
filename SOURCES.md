# Morning Signal sources

Feed endpoints were requested directly and parsed as RSS/Atom on 15 October 2026. No API keys, accounts, paid services, search scraping, or paywall workarounds were used. The detailed machine-readable evidence is in `source_report.json`.

## Configured starter set (25 feeds)

| ID | Feed | Category | Items in verified response |
|---|---|---|---:|
| ars | [Ars Technica](https://feeds.arstechnica.com/arstechnica/index) | tech | 20 |
| verge | [The Verge](https://www.theverge.com/rss/index.xml) | tech | 10 |
| hackernews | [Hacker News](https://news.ycombinator.com/rss) | tech | 30 |
| hackaday | [Hackaday](https://hackaday.com/blog/feed/) | tech | 7 |
| bleepingcomputer | [BleepingComputer](https://www.bleepingcomputer.com/feed/) | tech | 15 |
| 404media | [404 Media](https://www.404media.co/rss/) | tech | 15 |
| register | [The Register](https://www.theregister.com/headlines.atom) | tech | 50 |
| eurogamer | [Eurogamer](https://www.eurogamer.net/feed) | gaming | 100 |
| rps | [Rock Paper Shotgun](https://www.rockpapershotgun.com/feed) | gaming | 100 |
| gamingonlinux | [GamingOnLinux](https://www.gamingonlinux.com/article_rss.php) | gaming | 50 |
| wololo | [Wololo](https://wololo.net/feed/) | gaming | 20 |
| shadps4 | [shadPS4 Releases](https://github.com/shadps4-emu/shadPS4/releases.atom) | gaming | 10 |
| variety | [Variety](https://variety.com/feed/) | culture | 10 |
| polygon | [Polygon](https://www.polygon.com/rss/index.xml) | culture | 10 |
| kym | [Know Your Meme](https://knowyourmeme.com/newsfeed.rss) | culture | 5 |
| smithsonian | [Smithsonian Science & Nature](https://www.smithsonianmag.com/rss/science-nature/) | science | 15 |
| nasanews | [NASA](https://www.nasa.gov/feed/) | science | 10 |
| sciencealert | [ScienceAlert](https://www.sciencealert.com/feed) | science | 10 |
| mongabay | [Mongabay](https://news.mongabay.com/feed/) | animals | 32 |
| physanimals | [Phys.org Plants & Animals](https://phys.org/rss-feed/biology-news/plants-animals/) | animals | 30 |
| racefans | [RaceFans](https://www.racefans.net/feed/) | motorsport | 20 |
| motorsport | [Motorsport.com F1](https://www.motorsport.com/rss/f1/news/) | motorsport | 50 |
| soyacincau | [SoyaCincau](https://soyacincau.com/feed/) | local | 10 |
| lowyat | [Lowyat.NET](https://www.lowyat.net/feed/) | local | 10 |
| paultan | [Paul Tan](https://paultan.org/feed/) | local | 20 |

All 25 selected feeds parsed successfully. None contained a DTD or entity declaration. Response sizes were approximately 5 KB–348 KB. Independent requests used up to six workers and an eight-second timeout; successful first probes generally took 0.1–3.5 seconds each. Individual publishers can become unavailable later, so the reader must retain the last good cache and expose source errors.

Hacker News supplies community technical-project discovery; linked posts are not independently verified by the reader. Wololo and GitHub releases are specialist feeds: quiet periods are normal. Preserve original dates and do not present old releases as today's news. Mongabay includes conservation and forests; the Phys.org topic also includes plant research. Malaysia coverage starts with local technology and automotive publications, rather than a general politics stream.

## Content handling

- Show the publisher's name, original headline, a short feed-provided excerpt where available, publication date, and a direct original link.
- Treat titles and excerpts as publisher claims, not independently verified facts. Headlines alone cannot establish whether a port is official, a project is complete, or a rumour is confirmed.
- Strip executable HTML and tracking markup from displayed excerpts. Do not fetch full article pages, retain full `content:encoded` articles, download publisher images, or bypass subscriptions.
- Keep the app for personal local reading. Public RSS availability does not grant unrestricted redistribution rights. Any later public hosting, commercial use, or AI rewriting needs a separate publisher-policy review.
- Prefer conditional requests and a refresh interval of at least 30 minutes. Daily launch refreshes are sufficient for the morning digest. One failed source must not block the others.

[Ars Technica's feed directory](https://arstechnica.com/rss-feeds/) confirms its reader feeds and distinguishes subscriber full-text feeds. This app uses the public feed. [Mongabay's FAQ](https://mongabay.com/faq/) distinguishes ordinary linked excerpts from extended/full-article redistribution, which can require permission.

## Excluded candidates and fallbacks

- **ScienceDaily:** Both requested feeds work technically, but its [RSS terms](https://www.sciencedaily.com/terms.htm) restrict altered text, long-term storage, and database entry without permission. They are excluded from the recommended defaults; ScienceAlert, Smithsonian, and Phys.org supply the initial science/animal coverage.
- **PC Gamer:** The general feed exceeded the two-megabyte verification safety cap and was truncated mid-CDATA. A smaller publisher feed could be checked later.
- **The A.V. Club:** The feed had an unbound XML namespace prefix and failed strict parsing.
- **NASA Science:** `science.nasa.gov/feed/` returned non-XML content. The working `www.nasa.gov/feed/` is used instead.
- **Live Science Animals:** The candidate `/feeds/animals` endpoint returned 404.
- **Earth Touch:** The candidate `/rss.xml` endpoint timed out.
- **Working fallbacks:** Phys.org's general feed, Crash F1, Autosport F1, and Malay Mail Malaysia also parsed. They are not in this recommended 25-source set to reduce topic/publisher overlap and broad general news. Exact URLs are recorded in the report.

The initial restricted-shell attempt could not resolve any hostnames. The report was then replaced with actual responses from an approved read-only network probe; DNS sandbox failures are not counted as publisher outages.
