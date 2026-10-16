# ChordFlow

Chords, keys, bass, piano voicings and guitar shapes for worship musicians. Load a song, or hold your phone up to one, and see the progression.

## What is in here
| Folder | What it is |
|---|---|
| `docs/` | The finished web app (`index.html`), installable on a phone (PWA). GitHub Pages serves this folder. |
| `web/src/` | The source of the web app. Edit here, then run `python web/build.py` to rebuild `docs/index.html`. |
| `server/`, `db/` | The catalog API: recordings, one official chart each, version history, a moderated suggestion queue. |
| `worker/` | `analyze.py` (Demucs + Basic Pitch on your own computer), `publish.py` (send a chart to the catalog), `run.py` (optional queue worker). |
| `eval/` | `evaluate.py`: measures chord accuracy against reference charts. |
| `tests/` | API and logic tests, plus browser tests for YouTube play-along and live listening. |
| `mobile/` | Capacitor project for real iOS and Android apps. |
| `.github/workflows/` | Runs the tests on every push, and builds an Android test app on demand. |

## Put it online (all free)
1. **Page:** repo Settings > Pages > Deploy from a branch > `main` and folder `/docs`. In a minute you get `https://<you>.github.io/chordflow/`. Open it on your phone and use Share > Add to Home Screen.
2. **API (only needed for the shared catalog):** Render > New > Blueprint > this repo (`render.yaml`). Add the environment variables it asks for. Use a free Supabase PostgreSQL database for `DATABASE_URL`.
3. **Sign-in:** Supabase Auth with Google. Copy its JWT secret into `SUPABASE_JWT_SECRET`. Make yourself a moderator by setting your user's `app_metadata` to `{"role":"moderator"}`.
4. Never put passwords or keys in the repo. They go in the hosting sites' settings pages (`.env.example` lists the names).

## Run it on your computer
```
pip install -r requirements.txt
python tests/test_logic.py && python tests/test_api.py      # API: 40 checks
python web/build.py                                         # rebuild docs/index.html
python worker/analyze.py "My Song.mp3"                      # needs: pip install demucs basic-pitch librosa music21
```
Browser tests need `pip install playwright` and a Chromium install, then `python tests/make_synth.py && python tests/livetest.py /tmp/synth.wav 40`.

## The flow
1. Open the site. 2. Search a song (MusicBrainz, via your API). 3. Tap it: the chart loads from the catalog and its YouTube video appears in the official player. 4. Play: the chords follow the video. 5. "Use your own audio file" and "Listen to a song" sit below as the secondary ways in.
If a song has no chart yet, the page shows "Ask for this chart" (needs sign-in). You see the most-requested uncharted songs at `/api/moderation/requests` and make them with `worker/analyze.py` + `worker/publish.py --youtube <link>`.
If a chart has no video yet, the page lists YouTube candidates (needs `YOUTUBE_API_KEY` on the server), or you can paste a link. "Save this video and timing for everyone" sends it to moderators.

## Adding songs without Python
Open the site, choose "Use your own audio file", wait ~10 seconds for the analysis, then open "Add this chart to the catalog": search the recording, paste its YouTube link, and publish. Sign in as a moderator, or paste the `WORKER_TOKEN` from Render's Environment tab into the admin-key box (it is cleared after each publish and never saved). Only chords and beat times are sent. A recording that already has a chart receives yours as a "candidate", never overwriting the official one.

## What you still have to set up (once)
| What | Where | Goes in |
|---|---|---|
| API online | Render > New > Blueprint > this repo | `render.yaml` does the rest |
| Database | Supabase (free) | `DATABASE_URL` in Render |
| Google sign-in | Supabase > Authentication > Providers > Google (needs a Google Cloud OAuth client) | `SUPABASE_JWT_SECRET` in Render; project URL and anon key in `docs/config.js` |
| Video search | Google Cloud > YouTube Data API v3 > API key | `YOUTUBE_API_KEY` in Render |
| MusicBrainz contact | your email | `MB_CONTACT` in Render |
| Page address of the API | after Render is live | `api` in `docs/config.js`, then push |
Keys that must stay secret (database, JWT secret, YouTube key, worker token) go only in Render's settings. `docs/config.js` is public by design: only the API address, the Supabase URL and the Supabase anon key belong there.

## What works and what has not been tested
Tested here: the web app in a headless browser (chords, editor, Keys and Guitar tabs, the whole search > chart > video > play flow against a real API server with a simulated YouTube player, live listening on synthetic audio), and the API end to end on SQLite (54 checks).

Not tested: a real YouTube video, the live YouTube Data API, Google sign-in through Supabase, the Demucs + Basic Pitch pipeline, PostgreSQL and Supabase sign-in, the live MusicBrainz call, any real phone (iPhone or Android), the GitHub Actions workflows, and the app shells in `mobile/`.

Live listening, honestly: on clean, simple audio it reads the loop correctly. On a full studio recording it gets the shape of the loop but is often wrong on individual chords (it read B over D# as D#m, and matched the offline chart on only about half of the individual chord roots on the one real song I tried). Treat it as a fast sketch of the progression, and use "Make a full chart" for the accurate version.

Not built yet: the page does not yet send chord/voicing/sync corrections to the API (they still use the earlier in-page suggestion box), the Modal GPU worker, and Shazam-style song naming.

## Rights and notices
The code is published to be read, not reused: see `LICENSE` (all rights reserved). ChordFlow is not affiliated with, endorsed by or connected to YouTube, Google, Chordify, Shazam, Apple or any record label or publisher. All song, artist and recording names belong to their owners and are used only to identify what a chart describes.

This repository contains no recordings, lyrics or copyrighted charts. Audio is never stored: uploaded files are deleted after analysis, and the catalog keeps only chords and timing. Lyrics are not shared. Whether you may analyze and share charts of other people's recordings is a legal question; get advice before opening this to the public.
