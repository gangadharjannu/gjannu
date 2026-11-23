# Gangadhar Jannu (గంగాధర్ జన్ను)

This repository makes a static website for the [gangadhar jannu](https://www.youtube.com/@gjannu) YouTube channel. The site shows each Telugu padyam, shloka and song with its full text. It also shows the film, the poet, the singers and the composer. The site has a Telugu version (`/te/`) and an English version (`/en/`).

The site has no server and no database. A Python script makes plain HTML files. Any static host can serve these files.

## Features

| Feature | Description |
|---|---|
| Library | A list of all videos. The filters are form, decade, year, film, singer, poet or lyricist and composer. Other filters are source text, theme and format (Shorts or videos). |
| Search | Search in Telugu script or in Roman script. The search also finds a line of verse. Different Roman spellings match (example: "dhorakadu" and "dorakadu"). |
| Timeline | A bar chart of the videos by film year. Click a year to filter the library. |
| Song page | The video, the credits and the full text. The reader can show the text in Telugu script, in Roman script or in both. |
| Film pages | One page for each film, play or album. The films index is in decade order. |
| Artist pages | One page for each singer, poet, lyricist and composer. |
| Two languages | Each page has a Telugu version and an English version. The site keeps the selected language. |
| Light and dark | The site uses the colour mode of the system. The reader can change it. |

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
4. The job reads the RSS feed. The feed can be some minutes late. If the video is not in the feed, the job tries again each minute for 10 minutes.
5. The job saves the video in `data/videos/` and commits the change.
6. The job builds the site and publishes it.

The site shows the new video a few minutes after the upload. If a notification is lost, the weekly job (Monday, 01:30 UTC) adds the video. To publish immediately, run the workflow from the **Actions** tab.

A description can have a name that is not in `data/names.json`. The site then shows that name in an automatic Roman form. The job summary lists these names. Add each name to `data/names.json` to set the correct English name.

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
| A name has the wrong English form | Change `en` for that name in `data/names.json`. |
| Two forms of one name show as two people | Add the second form to `aliases` of the first person in `data/names.json`. |
| A film has no year | Add `year` to the film in `data/names.json`. |
| A video has the wrong form, film or title | Add an entry for the video ID in `data/overrides.json`. |
| A video must not show | Add the video ID to `hidden` in `data/overrides.json`. |

Push the change. The workflow builds and publishes the site again.

## Move to another site framework

`build/content.json` has all the parsed data. It does not depend on `build.py`. To use a framework such as Astro, keep `fetch.py` and `parse.py`, and read `build/content.json` in the framework.
