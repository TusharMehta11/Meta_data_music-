# LLm_music

Fixes song metadata **and cover art** for a local folder or an FTP music library.
It searches real music databases (MusicBrainz, YouTube Music, iTunes) and uses a **local LLM** (Ollama) only to
*choose* between the results when the match is unclear. The LLM never invents tags.

Nothing is written to your files until you approve it in the review page.

```
scan  ──►  review (web page)  ──►  apply
 │            │                       │
 │ search 3 sources in parallel        │ backup original first
 │ rank candidates                     │ write tags + 1000px cover
 │ LLM decides unclear cases           │ verify, upload back
 │ download cover                      │
 └─ never touches audio files          └─ only APPROVED rows
```

## Setup (Windows, one time)

1. Install [Ollama](https://ollama.com/download) for Windows (already installed on this PC) and pull the model:
   ```powershell
   ollama pull qwen3:4b
   ```
   `qwen3:4b` (about 3.5 GB) fits a 4 GB GPU such as the RTX 3050 Ti, with part of it running on the CPU. That's about 5–10 s per LLM decision. Ollama runs natively on Windows, so WSL is not needed.
2. Python packages:
   ```powershell
   cd D:\tushar.mehta\projects\LLm_music
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Settings: copy `.env.example` to `.env` and fill in `MUSIC_SOURCE`, `FTP_USER`, `FTP_PASSWORD`.
   `.env` also accepts the PowerShell form `$env:FTP_USER = "..."`. It's ignored by git, so keep passwords only there.
4. Check everything:
   ```powershell
   python main.py doctor
   ```

## Use

```powershell
python main.py scan --limit 20      # try 20 files first; rerun without --limit for the rest
python main.py review               # opens http://127.0.0.1:8765 in your browser
python main.py apply --dry-run      # test the writes on temporary copies
python main.py apply                # write approved tags + covers (backups first)
```

* **Scan is incremental.** Files already scanned are skipped, so new songs added to the server are picked up by running
  `scan` again. Use `--rescan` to redo everything. Ctrl+C is safe, because progress is saved per file.
* **Review page.** Shows the current and proposed cover side by side, the current and proposed tags, and the
  confidence and the LLM's reason. You can edit any field, pick another candidate from the dropdown (this re-fetches its cover),
  untick "replace cover", Approve or Reject. "Approve all shown" approves everything matching the current filters,
  e.g. *min confidence 90*.
* **Apply.** Re-downloads each file, checks it hasn't changed since the scan (SHA-256), backs up the original
  (FTP: `.metadata_autofixer_backups/` beside the file; local: `data/backups/`), writes the tags and cover, checks the
  result and uploads it.
* `python main.py export` writes everything to `data/review.csv` if you want a spreadsheet.

### Scan options

| Option | Meaning |
|---|---|
| `--llm auto` (default) | LLM only for unclear matches. Clear matches (score ≥ 88 and confirmed by 2+ sources) skip it. |
| `--llm all` / `--llm off` | Use the LLM for every file / never (heuristic only; much faster). |
| `--model qwen3:8b` | Bigger model (needs more memory; slower on a 4 GB GPU). |
| `--auto-approve 90` | Pre-approve matches with confidence ≥ 90, 2+ agreeing sources and length within 5 s. You can still un-approve them in the page. |
| `--sources musicbrainz,itunes` | Choose sources. `deezer` is supported but off by default: its API returns empty results from India. |

## What gets written

Title, artist, album, album artist, date, track number, disc number (only non-empty values), and the front cover
(JPEG, max 1000×1000) when "replace cover" is ticked. Formats: MP3, AIFF (ID3), FLAC, Ogg Vorbis, Opus, M4A/MP4, WMA.
Genre and lyrics are not changed.

## How matching works

1. Query = existing title/artist tags, or the cleaned file name (drops "Official Music Video", "| T-Series", quotes…).
2. MusicBrainz, YouTube Music and iTunes are searched in parallel; if MusicBrainz missed, it is searched again with
   the clean title/artist found elsewhere (to get proper album, track and disc data).
3. Every candidate is scored on title/artist overlap, duration and how many other sources list the same song.
   Compilations ("Greatest Hits", "Best of") are slightly penalised and the album most sources agree on wins ties.
4. Unclear cases go to the LLM with the file name, tags, duration and the top 8 candidates. It returns a choice,
   a confidence (0–100) and a one-line reason. If it rejects everything although 2+ sources agree, the best match is
   kept with low confidence so you decide.
5. Missing album/date/track fields are filled from other sources that list the same song on the same album; the cover comes
   from the chosen candidate or, failing that, from an agreeing source. Blank placeholders and video frames are rejected.

## Notes

* Data lives in `data/` (SQLite database with cached web responses, cover images, local backups).
  Delete `data/` to start fresh.
* MusicBrainz allows ~1 request/s and iTunes ~20/min, so the first scan of 1000 songs takes roughly 1–2 hours;
  cached re-scans are fast.
* YouTube Music is accessed through the unofficial `ytmusicapi` library, which is fine for a personal library but
  outside YouTube's terms for commercial use, and may break when YouTube changes.
* Plain FTP sends passwords unencrypted; set `FTP_TLS=1` if your server supports FTPS.
