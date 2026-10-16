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

## What works and what has not been tested
Tested here: the web app in a headless browser (chords, editor, suggestions and moderation with a mock backend, Keys and Guitar tabs, YouTube play-along with a simulated player, live listening on synthetic audio), and the API end to end on SQLite.

Not tested: a real YouTube video, the Demucs + Basic Pitch pipeline, PostgreSQL and Supabase sign-in, the live MusicBrainz call, any real phone (iPhone or Android), the GitHub Actions workflows, and the app shells in `mobile/`.

Live listening, honestly: on clean, simple audio it reads the loop correctly. On a full studio recording it gets the shape of the loop but is often wrong on individual chords (it read B over D# as D#m, and matched the offline chart on only about half of the individual chord roots on the one real song I tried). Treat it as a fast sketch of the progression, and use "Make a full chart" for the accurate version.

Not built yet: search and the shared catalog inside the page (the API exists, the page does not call it yet), the Modal GPU worker, and Shazam-style song naming.

## Rights and notices
The code is published to be read, not reused: see `LICENSE` (all rights reserved). ChordFlow is not affiliated with, endorsed by or connected to YouTube, Google, Chordify, Shazam, Apple or any record label or publisher. All song, artist and recording names belong to their owners and are used only to identify what a chart describes.

This repository contains no recordings, lyrics or copyrighted charts. Audio is never stored: uploaded files are deleted after analysis, and the catalog keeps only chords and timing. Lyrics are not shared. Whether you may analyze and share charts of other people's recordings is a legal question; get advice before opening this to the public.
