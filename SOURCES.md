# Morning Signal sources

Reviewed and directly probed on 8 November 2026, Malaysia time. The **13-source briefing** replaces the overlapping starter feeds with world affairs, business and logistics, engineering, science, nature, cars, and gaming. It affects both editions. No subscription, API key, paid feed, or paid service is required by the reader. Individual publishers control their linked pages; access and terms can change.

## Configured feeds

Every configured endpoint returned RSS/Atom and parsed with the actual `news_engine.parse_feed` parser. The counts below are dated items in those responses, not a promise of daily output. [source_report.json](source_report.json) records each probe's actual time, response and policy-review status without copying articles.

| ID | Source | Category | Dated items | Purpose |
| --- | --- | --- | ---: | --- |
| bbcworld | [BBC News - World](https://feeds.bbci.co.uk/news/world/rss.xml) | world | 25 | Major international developments |
| bbcasia | [BBC News - Asia](https://feeds.bbci.co.uk/news/world/asia/rss.xml) | world | 17 | Regional context, including client markets |
| bbcbusiness | [BBC News - Business](https://feeds.bbci.co.uk/news/business/rss.xml) | business | 43 | Companies, trade and economic changes |
| loadstar | [The Loadstar News](https://theloadstar.com/category/news/feed/) | business | 10 | Freight, ports, carriers and supply chains |
| ars | [Ars Technica](https://feeds.arstechnica.com/arstechnica/index) | tech | 20 | Technology, security and engineering context |
| ieeespectrum | [IEEE Spectrum](https://spectrum.ieee.org/feeds/feed.rss) | tech | 30 | Chips, energy, robotics and engineering |
| physnews | [Phys.org Research Highlights](https://phys.org/rss-feed/breaking/) | science | 30 | Broad scientific research |
| nasanews | [NASA](https://www.nasa.gov/feed/) | science | 10 | Space, Earth science and mission updates |
| techcars | [TechXplore.com Automotive](https://techxplore.com/rss-feed/automotive-news/) | cars | 30 | Car engineering and automotive industry |
| mongabay | [Mongabay](https://news.mongabay.com/feed/) | animals | 32 | Wildlife, forests and conservation |
| physanimals | [Phys.org Plants & Animals](https://phys.org/rss-feed/biology-news/plants-animals/) | animals | 30 | Animal and plant research |
| eurogamer | [Eurogamer](https://www.eurogamer.net/feed) | gaming | 100 | Gaming companies, releases and industry |
| wololo | [Wololo](https://wololo.net/feed/) | gaming | 20 | Homebrew and console developments |

BBC's sections share one publisher; they are not independent corroboration. Phys.org and Tech Xplore also share a publisher. Some research coverage originates from institutions' announcements: a headline saying “breakthrough” is not independent confirmation. Wololo can be quiet; old releases must retain their original dates.

Cars currently has an engineering/industry feed. Enthusiast histories, older Porsches, tuning, aquarium and vivarium guides belong in the reader's direct reading shelf as well. There is **no dedicated general-Malaysia feed** in this set: major regional developments can arrive through BBC Asia. This is a coverage limitation, not a claim to cover every important local event.

## Access, attribution and reuse

Public feed availability and permission to republish complete articles are different. The website publishes original headline links, dates and source credit, with its own category illustrations; it does not publish article bodies or publisher pictures. The Windows reader can retain short feed excerpts where supported. Keep original article links and prominent publisher credit; do not imply endorsement or verification.

- [BBC's content terms](https://www.bbc.co.uk/usingthebbc/terms/can-i-use-bbc-content/) permit personal website RSS use with feed integrity, attribution and links. Business use has separate terms. This remains a personal, non-commercial reader.
- [Phys.org](https://phys.org/feeds/) and [Tech Xplore](https://techxplore.com/feeds/) expressly offer website feeds without a fee, requiring unchanged headlines/links and source credit.
- [The Loadstar's current copyright policy](https://theloadstar.com/licencing-and-copyright/) allows RSS links. `headlines_only: true` suppresses its Windows excerpts too; `exclude_feed_categories: ["premium"]` rejects paid-category entries before storage. Its **News** feed contained no Premium-tagged entries; the general feed contained five in ten and is not configured. Do not use the older about page's more generous copying wording.
- [NASA's usage guidance](https://www.nasa.gov/nasa-brand-center/images-and-media/) permits factual informational use with acknowledgement, subject to third-party material and branding restrictions. No publisher images are imported.
- [Mongabay's FAQ](https://mongabay.com/faq/) provides RSS and distinguishes excerpts from extended republication. [Ars's feed directory](https://arstechnica.com/rss-feeds/) separates ordinary feeds from subscriber full-text feeds; only the public feed is configured.
- IEEE Spectrum, Ars, Eurogamer and Wololo are ordinary public RSS sources used for credited headline links on the website. A blanket public-republication licence was **not established** for them. This review does not grant permission to copy their articles, images or subscriber material. IEEE's linked terms page returned an empty response during this check.

No article scraping, paywall bypass, AI rewriting or paid integration is used. If a publisher introduces access restrictions, remove or replace that source rather than bypassing them.

## Candidates not configured

- **CNA:** its [RSS terms](https://www.channelnewsasia.com/rss/rssterms) explicitly prohibit transferring feeds to third parties. Read CNA directly.
- **Paul Tan, Malay Mail, Free Malaysia Today, Silodrome and Motor1:** feeds may work, but reviewed terms reserve reproduction/public display; no applicable public-feed permission was established. Keep direct reading links instead. See the report for policy URLs.
- **Quanta:** free to read, but [terms](https://www.quantamagazine.org/terms-conditions/) reserve republication; use as a direct longer-read destination. Phys.org supplies the science feed.
- **PistonHeads and Top Gear:** tested candidate feed paths returned 404. **Hagerty:** tested US/UK feeds returned 403. These results do not prove every possible feed is unavailable; none was added or bypassed.
- **Bernama:** the tested general RSS returned items without publication dates, so it cannot supply this dated website edition reliably.
- **AP:** no official free consumer RSS endpoint was established in this review; BBC supplies the world feed.

The narrower set removes meme/entertainment feeds, F1-only feeds and overlapping general technology/gaming outlets. Retained source IDs stay unchanged. Saved stories and personal settings must be preserved by the preference migration described in the development guide.
