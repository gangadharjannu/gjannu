# Gangadhar Jannu (గంగాధర్ జన్ను)

This repository makes a static website for the [gangadhar jannu](https://www.youtube.com/@gjannu) YouTube channel. The site shows each Telugu padyam, shloka and song with its full text, its film, its poet, its singers and its composer. The site has a Telugu version (`/te/`) and an English version (`/en/`).

The site has no server and no database. A Python script makes plain HTML files. Any static host can serve these files.

## Features

| Feature | Description |
|---|---|
| Library | A list of all videos with filters: form, decade, year, film, singer, poet or lyricist, composer, source text, theme and format (Shorts or videos). |
| Search | Search in Telugu script or in Roman script. The search also finds a line of verse. Different Roman spellings match (example: "dhorakadu" and "dorakadu"). |
| Timeline | A bar chart of the videos by film year. Click a year to filter the library. |
| Song page | The video, the credits and the full text. The reader can show the text in Telugu script, in Roman script or in both. |
| Film pages | One page for each film, play or album. The films index is in decade order. |
| Artist pages | One page for each singer, poet, lyricist and composer. |
| Two languages | Each page has a Telugu version and an English version. The site keeps the selected language. |
| Light and dark | The site follows the system colour setting. The reader can change it. |

## Architecture

```
YouTube channel ──upload──► Google WebSub hub ──POST──► Cloudflare Worker (notify/)
   │                                                        │ repository_dispatch
   │  fetch.py  (source: rss, api or ytdlp)  ◄──────────────┘ (or the weekly schedule)
   ▼
data/videos/<id>.json   data/playlists.json   data/names.json   data/overrides.json
   │  parse.py
   ▼
build/content.json      (one content file; it does not depend on a site framework)
   │  build.py
   ▼
dist/                   (static HTML, CSS, JS and JSON)
   │  GitHub Actions
   ▼
GitHub Pages
```

| Part | File | Function |
|---|---|---|
| Fetch | `scripts/fetch.py` | Gets the video data from YouTube. Adds new videos. Updates the title, the description and the statistics. |
| Parse | `scripts/parse.py` | Reads the credit lines in each description (చిత్రం, రచన, సంగీతం, గానం, మూలం). Splits the text into verse and meaning. Joins the different spellings of one name. |
| Transliterate | `scripts/translit.py` | Changes Telugu script into Roman script. Makes the search keys. |
| Render | `scripts/build.py` | Writes all pages in Telugu and in English. Writes the sitemap and the search index. |
| Front end | `site/assets/` | The stylesheet, the script and the icon. The script has no dependencies. |
| Notifier | `notify/worker.js` | A Cloudflare Worker. Receives the YouTube upload notification. Starts the update job. Renews the subscription every 2 days. |
| Update job | `.github/workflows/update.yml` | Runs the fetch and the build. Publishes the site. The notifier starts it. It also runs every week. |

### The fetch sources

| Source | Key necessary | Videos | Use |
|---|---|---|---|
| `rss` | No | The 15 latest | The usual update. This is the default when there is no API key. |
| `api` | Yes (`YT_API_KEY`) | All | Updates the statistics of all videos and the playlists. |
| `ytdlp` | No | All | The first full fetch on your computer. YouTube often blocks yt-dlp on GitHub servers. |

### The data files

| File | Content | Who changes it |
|---|---|---|
| `data/videos/<id>.json` | The title, the description, the date and the statistics of one video. | The fetch script |
| `data/playlists.json` | The channel playlists that contain channel videos. | The fetch script |
| `data/names.json` | The Telugu name, the English name and the other spellings of each person, film and source text. The film years. The theme rules. | You |
| `data/overrides.json` | Corrections for one video. A list of hidden videos. | You |
| `site.config.json` | The site name, the site URL and the channel details. | You |

## Run the site on your computer

Python 3.10 or later is necessary. No packages are necessary.

1. Build the site:
   ```
   python3 scripts/build.py --base /
   ```
2. Start a local web server:
   ```
   python3 -m http.server 8765 --directory dist
   ```
3. Open `http://localhost:8765/` in a browser.

## Publish the site on GitHub Pages

1. Make a public GitHub repository. Push this folder to the `main` branch.
2. In the repository, open **Settings > Pages**.
3. Set **Source** to **GitHub Actions**.
4. Open the **Actions** tab. Select **Update and deploy**. Click **Run workflow**.
5. Open the URL that the `deploy` job shows.

NOTE: The workflow sets the site path and the site URL automatically. If you use a custom domain, set it in **Settings > Pages**.

### Optional: add a YouTube Data API key

With an API key, the update job updates the view counts of all videos and the playlists. Without a key, the job updates only the 15 latest videos.

1. In the Google Cloud console, make a project.
2. Enable the **YouTube Data API v3**.
3. Make an API key. Limit the key to the YouTube Data API v3.
4. In the GitHub repository, open **Settings > Secrets and variables > Actions**.
5. Add a secret with the name `YT_API_KEY` and the key as the value.

## Set up the upload notifier

The notifier is a small Cloudflare Worker. YouTube tells the Worker about each new upload. The Worker then starts the update job. With the notifier, a new video shows on the site in a few minutes.

Without the notifier, the weekly job still adds new videos. The notifier is optional.

### What you need

| Item | Where | Cost |
|---|---|---|
| The GitHub repository of this site, with GitHub Pages on | GitHub | No charge for a public repository |
| A Cloudflare account | <https://dash.cloudflare.com/sign-up> | No charge on the Workers Free plan |
| Node.js 18 or later on your computer | <https://nodejs.org> | No charge |

### Procedure

1. Make a GitHub token for the Worker:
   1. On GitHub, open **Settings > Developer settings > Personal access tokens > Fine-grained tokens**.
   2. Click **Generate new token**.
   3. Set **Repository access** to **Only select repositories**. Select the repository of this site.
   4. Under **Repository permissions**, set **Contents** to **Read and write**.
   5. Click **Generate token**. Copy the token.

   CAUTION: Do not put the token in a file or in the repository. Keep it only in the Worker secret.

2. Open a terminal in the `notify` folder:
   ```
   cd notify
   ```
3. Log in to Cloudflare. A browser window opens.
   ```
   npx wrangler login
   ```
4. Deploy the Worker:
   ```
   npx wrangler deploy
   ```
   The command shows the Worker URL. Example: `https://gjannu-notify.<your-name>.workers.dev`.
5. Add the GitHub token as a secret. Paste the token when the command asks for it.
   ```
   npx wrangler secret put GITHUB_TOKEN
   ```
6. Add the repository name as a secret. Type it in the form `owner/repository`.
   ```
   npx wrangler secret put GITHUB_REPO
   ```
7. Make a random shared secret and add it:
   ```
   openssl rand -hex 24 | npx wrangler secret put HUB_SECRET
   ```
8. In `notify/wrangler.toml`, set `WORKER_URL` to the Worker URL from step 4.
9. Deploy the Worker again:
   ```
   npx wrangler deploy
   ```
10. Open the Worker URL in a browser. Make sure that the page shows "Ready".
11. Open `<Worker URL>/subscribe` in a browser. Make sure that the page shows "Subscription request accepted".

The cron trigger renews the subscription every 2 days. You do not have to open `/subscribe` again.

### Test the notifier

1. Upload a video, or change the description of a video.
2. In the GitHub repository, open the **Actions** tab.
3. Make sure that a run of **Update and deploy** starts. The trigger is `repository_dispatch`.

To see the Worker log, run `npx wrangler tail` in the `notify` folder.

### Stop the notifier

1. Delete the Worker in the Cloudflare dashboard.
2. Delete the GitHub token.

The weekly job continues to add new videos.

## How a new video gets to the site

1. The owner uploads a video. The description uses the usual format: the credit lines, then the text.
2. YouTube sends a notification to the Worker through the Google WebSub hub.
3. The Worker checks the signature of the notification. It starts the update job.
4. The job reads the RSS feed. If the feed does not show the video yet, the job tries again each minute, for a maximum of 10 minutes.
5. The job saves the video in `data/videos/` and commits the change.
6. The job builds the site and publishes it.

The site shows the new video a few minutes after the upload. If a notification is lost, the weekly job (Monday, 01:30 UTC) adds the video. To publish immediately, run the workflow from the **Actions** tab.

If the description has a name that is not in `data/names.json`, the site shows the name with an automatic Roman spelling. The job summary lists these names. Add each name to `data/names.json` to set the correct English name.

### Description format

The parser reads these credit lines. Each line has the form `key : value`.

| Key | Meaning |
|---|---|
| `చిత్రం` or `సినిమా` | The film. Put the year in brackets: `భీష్మ (1962)`. |
| `నాటకము` | A play. |
| `సంపుటి` | An album. |
| `రచన` or `సాహిత్యం` | The poet or the lyricist. |
| `సంగీతం` | The composer. |
| `గానం` | The singers. Use a comma between two names. |
| `మూలం` | The source text (example: `భగవద్గీత`). |

A line with only `పద్యం`, `శ్లోకం`, `పాట`, `కీర్తన` or `స్తోత్రం` sets the form. A line `భావము:` or `తాత్పర్యం:` starts the meaning.

## Correct the data

| Problem | Action |
|---|---|
| A name has the wrong English spelling | Change `en` for that name in `data/names.json`. |
| Two spellings show as two people | Add the second spelling to `aliases` of the first person in `data/names.json`. |
| A film has no year | Add `year` to the film in `data/names.json`. |
| A video has the wrong form, film or title | Add an entry for the video ID in `data/overrides.json`. |
| A video must not show | Add the video ID to `hidden` in `data/overrides.json`. |

Push the change. The workflow builds and publishes the site again.

## Move to another site framework

`build/content.json` has all the parsed data. It does not depend on `build.py`. To use a framework such as Astro, keep `fetch.py` and `parse.py`, and read `build/content.json` in the framework.

## Cost estimate

### Basis

| Item | Value |
|---|---|
| Price sources | [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits), [YouTube Data API quota](https://developers.google.com/youtube/data/determine_quota_cost), [Cloudflare Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/), [Cloudflare Workers limits](https://developers.cloudflare.com/workers/platform/limits/) |
| Date of the check | 23 November 2026 |
| Region | Global (GitHub-hosted; no region choice) |
| Currency | USD |
| Exclusions | A custom domain name. Your own computer time. The time of the person who maintains `names.json`. |

### Unit prices

| Service | Unit price | Status |
|---|---|---|
| GitHub Pages, public repository | USD 0. Limits: 1 GB site size and a soft limit of 100 GB bandwidth each month. | Verified |
| GitHub Actions, standard runner, public repository | USD 0. No usage limit. | Verified |
| GitHub Actions, standard Linux runner, private repository | USD 0.006 each minute, after the plan's included amount (USD 12 each month on GitHub Free) | Verified |
| YouTube RSS feed | USD 0. No key. | Not verified (no price page) |
| YouTube WebSub hub (push notifications) | USD 0 | Not verified (no price page) |
| Cloudflare Workers Free plan | USD 0. Limits: 100,000 requests each day and 5 cron triggers for each account. | Verified |
| Cloudflare Workers Paid plan (not necessary) | Minimum USD 5 each month for each account | Verified |
| YouTube Data API v3 | 10,000 quota units each day by default. Most read calls cost 1 unit. | Quota verified. Price not verified. |
| Custom domain (optional) | Depends on the registrar | Not verified |

### Fixed cost and usage cost (public repository)

| Cost type | Item | Monthly cost |
|---|---|---|
| Fixed | Hosting on GitHub Pages | USD 0 |
| Fixed | Cloudflare Worker on the Workers Free plan | USD 0 |
| Usage | About 4 weekly jobs and about 10 notification jobs each month, of about 2 minutes each, on a standard runner | USD 0 |
| Usage | About 15 cron runs and 20 hub requests each month on the Worker (limit: 100,000 requests each day) | USD 0 |
| Usage | YouTube Data API: about 10 units each job, so about 150 units each month | USD 0 (inside the free quota) |
| **Total** | | **USD 0** |

### Cost of one unit of work

| Unit | Calculation | Cost |
|---|---|---|
| One new video (notification, Worker request, update job), public repository | 2 minutes × USD 0 + 1 Worker request × USD 0 | USD 0 |
| One update job, private repository after the included amount | 2 minutes × USD 0.006 (the job can wait up to 10 minutes for the feed) | USD 0.012 to USD 0.06 |
| One page view | Static file from GitHub Pages. The page is about 50 KB, plus the thumbnails from YouTube. | USD 0 |

### Scenarios

| Scenario | Assumption | Monthly cost |
|---|---|---|
| Demonstration | Local preview only | USD 0 |
| Pilot | Public repository, GitHub Pages, weekly RSS update, no notifier | USD 0 |
| Production | Public repository, notifier on Workers Free, API key, custom domain | USD 0, plus the domain fee (not verified) |
| Private repository | 14 jobs of 2 minutes = 28 minutes = USD 0.17, inside the USD 12 included amount | USD 0. GitHub Pages from a private repository needs a paid GitHub plan (not priced here). |

### Cost controls

1. Keep the repository public. Then GitHub Actions standard runners and GitHub Pages have no charge.
2. Keep the schedule at one run each week. The notifier starts a run for each new video.
3. Stay on the Cloudflare Workers Free plan. The notifier uses far less than the daily limit. If the Worker goes above the limit, Cloudflare blocks requests. It does not charge.
4. Limit the API key to the YouTube Data API v3. Do not enable billing on the Google Cloud project.
5. Keep the site below 1 GB. The site is about 7 MB now. The images come from YouTube, not from the repository.

### Items that you must verify

1. The current GitHub Actions and GitHub Pages terms, if you use a private repository.
2. That the YouTube Data API has no charge in your Google Cloud project, and that billing is off.
3. The domain fee, if you use a custom domain.
4. That the site traffic stays below the 100 GB monthly soft limit of GitHub Pages.
5. That your Cloudflare account stays on the Workers Free plan.
