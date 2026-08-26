# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.2] — 2026-08-22

### Fixed — fresh-clone first run on new Python versions
- `python-libtorrent` is not a real PyPI package and `libtorrent` has no wheel for brand-new Pythons (e.g. 3.14), which aborted the entire first-run install. libtorrent is now installed **best-effort** after the core dependencies: when no wheel exists, PDM prints one notice and runs fully except torrent support (engine degrades gracefully).
- Verified end-to-end on a simulated fresh clone with system Python 3.14: auto-install → venv fallback path → **Application ready**.

### Changed — repo slimmed to ship-ready
- Removed developer-only tooling from the repo: brand/screenshot generators (`tools/`), packaging scripts (`packaging/`), placeholder `translations/`, and the unwired browser-extension + native-host scaffolding. Generated assets (icons, splash, banner, screenshots) remain - they are the shipped product.
- README development section updated to match.

### Changed — silent console + fresh-clone ready
- `python3 pdm.py` on a fresh clone just works: missing dependencies auto-install (direct pip, with automatic `.venv` fallback on externally-managed systems like Ubuntu/Debian/Kali), then the app starts.
- Console is now completely silent by default: C++/Qt/Chromium warnings (WebEngine profile release, GPU command buffer, Vulkan/Dawn, propagateSizeHints) are filtered at the file-descriptor level; `PDM_VERBOSE=1` restores full output.
- Ctrl+C exits cleanly ("PDM closed.") instead of dumping a KeyboardInterrupt traceback.
- `.gitignore` hardened: `database/cookies/` (sessions), WAL/SHM files, logs - nothing sensitive can be committed.
- Windows venv path supported in the bootstrap re-exec.

### Fixed — screenshots rendered broken/transparent
- Offscreen grabs were clipped by the platform's tiny backing store, leaving large transparent (or dead) regions - most visible on the Home and Statistics shots.
- The generator now paints the widget tree directly into a full-size opaque canvas (`QWidget.render`), compositing over the theme background; all six screenshots verified full-bleed.
- Also fixed a real UI bug the investigation surfaced: `UrlCard` attached two layouts to one widget (Qt layout conflict warning on every launch).

### Added — play-and-catch stream capture in the login browser
- The embedded sign-in browser now hooks page network activity (fetch/XHR/video sources) while you browse or play: any **plain** (non-encrypted) `.m3u8` / `.mpd` / `.mp4` the site generates for your session appears in a "Streams caught" panel — double-click or one button sends it straight to the downloader. This is the legitimate half of how commercial downloaders work (observing your own session's traffic); DRM/CDM key extraction remains out of scope by design.
- Screenshots regenerated for the new UI (home dashboard, library, format picker, statistics, settings) and the README gallery restored with the new images; banner re-embedded with the live screenshot.

### Fixed — NRE never worked: wrong CLI arguments (the real download-blocker)
- `--concurrent-download` is a **flag** in N_m3u8DL-RE (no value); thread count is `--thread-count`. PDM passed `--concurrent-download 8`, so NRE exited 1 at argument parse on EVERY download, silently falling back. Verified live: with correct args NRE pulls the full stream (29/29 segments, ~135 MB at 10-20 MB/s).
- Key-gated streams: probe now also checks the **AES-128 KEY URL** - a 401/403 there marks the site sign-in-required (this is Chorki's actual gate: open manifest/segments, locked key server). Live-verified: chorki scan now raises the sign-in prompt.
- Probe bug: segment URLs were resolved against the master manifest instead of the variant playlist; init-section segments are probed too.

### Changed — genuine-stream verification + manual cookie section
- Deep probe per owner spec: harvested manifests are now verified as **genuinely downloadable** - SuperScan parses the m3u8, walks to the first variant, touches the first segment; a 401/403 at ANY level (or an HTML login page posing as a manifest) marks the site sign-in-required. Open streams never trigger the login prompt.
- New **Paste cookies manually** option next to browser sign-in: accepts cookies.txt exports or `name=value; ...` pairs, saved per domain through the same session store.
- Window title shortened to "PDM v1.2" (was repeating the full app name over the sidebar brand).
- `m3u8` package now actually installed (was declared in requirements but missing locally).

### Fixed — sign-in offer now actually appears
- Root cause: the login offer only fired when a scan returned **zero** items. Sign-in sites like Hoichoi/Chorki still returned their *unsigned* CDN streams, so the dialog showed dead entries and never offered login.
- SuperScan now **probes harvested manifests** (first 3 streams): a 401/403 marks the site as sign-in-required while still listing what it found.
- The dialog shows **"Sign in with browser & rescan"** whenever sign-in is needed — even alongside found streams ("Streams found above are locked until you sign in.").
- Removed the Help menu per owner request.

### Added — one-click site login (in-app browser)
- New flow for sign-in sites: paste link → Scan Media → if the site needs a session, a **"Sign in with browser & rescan"** button opens the site inside PDM (QtWebEngine). Log in once, press *Save session & continue* — cookies are captured and stored per domain (`database/cookies/<domain>.cookies.txt`, Netscape format) and persist across restarts.
- Saved sessions are used automatically everywhere: yt-dlp (`cookiefile`) in scanner and worker, `Cookie` header for SuperScan page fetches, N_m3u8DL-RE (`--header Cookie:`) and the native HLS downloader. Referer still honored.
- No-login sites proceed exactly as before; nothing changes when a session isn't needed.
- Splash cleaned: no engine names, tagline "From link to file — in seconds."; banner chips genericized (Video · Music · Torrents · Live streams).
- 6-test login-pipeline suite passing incl. QtWebEngine dialog boot; fixes the Chorki/Bioscope/Hoichoi class of failures (unsigned CDN manifests → 401/ffmpeg-183) by obtaining signed URLs through the saved session.

### Changed — distinctive brand identity + landing rework
- New ownable app mark: monoline "P" with a gradient down-arrow in the bowl counter on a dark tile — replaces the generic gradient-squircle-arrow icon; sidebar brand block now uses it too.
- Splash and GitHub banner rebuilt around the new mark; new tagline "From link to file — in seconds."; banner gained a ghost-mark composition and `./run.sh` command chip.
- Landing page reworked around a single primary action: paste bar with auto engine selection ("What are we grabbing today?"), compact inline stat bar, resume-all strip for paused/failed items, recent activity. Removed the redundant quick-action cards that duplicated the sidebar.

### Added — Home landing page + brand refresh (v1.2)
- New **Home dashboard**: live stat chips (active / completed / library size / torrents), quick-action cards (Paste & Download, Add Torrent, History) and a recent-activity feed; opens by default on launch.
- Upgraded app icon (depth, specular highlight, motion lines), splash screen (v1.2, new engine tagline) and GitHub banner with live app screenshot.
- Regenerated all screenshots including the new Home page; removed the 720px `#card` width cap that squeezed settings/statistics cards on wide windows.
- README rewritten: badges, hero banner, engine-routing table, screenshot gallery, architecture map, honest legal notice.

### Fixed — deep review of download pipeline
- **Critical**: direct downloads with unknown size always crashed (`_fallback_stream` was defined without `self`) - zero-length HEAD responses hit a TypeError instead of streaming.
- **Pause no longer fakes completion**: pausing during segmented, streamed-fallback or native-HLS downloads could mark them Finished with a partial file; all three paths now settle on Paused.
- **Integrity gate**: segmented downloads verify received bytes vs Content-Length (99.9%) before reporting success; truncated files fail over to single-stream download instead of completing silently.
- **NRE cancel cleanup**: leftover `.pdm_tmp_*` working directories are now deleted on cancel/interrupt.
- Fallback stream progress bar never moved (callback was invoked with 0 bytes); now reports real chunk sizes.
- Small-file crash guard: files smaller than the segment count fall back to single stream instead of computing zero-size ranges.
- Referer is now honored for direct HTTP(S) downloads and forwarded to every segment request.
- Cross-thread progress counters protected with a lock (multi-segment lost-count race).
- Regression tests added covering all six paths; live 8 MB multi-segment download verified end-to-end.

### Added — one-command bootstrap + N_m3u8DL-RE
- `run.sh` (Linux) and `run.bat` (Windows): clone → run. Creates the venv, installs all dependencies including PySide6 and a static FFmpeg fallback, auto-downloads N_m3u8DL-RE for the platform, optionally runs `scripts/selftest.py --live`, then launches PDM.
- N_m3u8DL-RE v0.6.0 integration is now live on this machine; Windows binary locations (`%LOCALAPPDATA%\PDM\bin`) added to detection.
- **First-run fix**: default categories (Video/Audio/Documents/…) were never seeded into a fresh database — `ensure_default_categories()` existed but was never called. Now runs automatically on first DB init, so extension→category routing works out of the box.

### Added — automated self-test
- `scripts/selftest.py`: 17 offline checks (imports, DB lifecycle incl. torrent records + WAL, scanner order guarantees, SuperScan harvest/login/DRM, NRE command builder + progress parser, worker routing, engine category/meta plumbing, UI boot + nav + bulk buttons, settings roundtrip, dialog magnet routing, themes) plus 3 live network tests (YouTube scan, public HLS via native engine, full YouTube download through the worker). Run `python3 scripts/selftest.py --live`.
- `PDM_VERBOSE=1` env flag for verbose console during development; default stays silent.

### Added
- **Torrent ↔ History sync** — magnet/torrent adds now create a real History record (friendly name from `dn` when available), renamed on metadata resolution, and marked `Finished` with actual size on completion.
- **Stats bandwidth integration** — torrent transfer rates now feed the live speed graph and status bar via a 1 s poll timer (`aggregate_rate()`).
- **Browse .torrent…** button in Torrents view alongside Add Magnet.
- **Record-only cleanup**: `Clear All` (all records) and `Empty Trash` buttons; neither touches files on disk.

### Changed
- **About dialog** — "Developed By Pintu Kumar Shapno"; card text color fixed for readability in both themes.
- **Sidebar simplified** — Scheduler and Rules removed entirely (UI entries, views, engine, and the `rules.evaluate` gate in `add_download`).

### Fixes
- **Crash on adding downloads** (`NameError: category`) — leftover reference after removing the rules engine; category is now derived from the file extension against saved Categories (Audio/Video/…).
- **Magnet links in New Download dialog** — pasting a `magnet:` link or `.torrent` URL no longer fails "No media found"; it routes straight to the BitTorrent engine and switches to the Torrents view.
- **Torrent list cleanup** — added *Remove Selected*, *Clear All*, and *Clear Finished* now also clears failed entries; all three remove libtorrent handles and their History records (files on disk untouched).
- **About card truncation** — card was squeezed to ~330px so every bullet clipped to one line; fixed at 680px wide with wrapping text, plus the missing "What PDM will not do" heading.
- **Torrent rename signal** — metadata-resolved now emits the old label so the torrent list renames its row correctly.
- **`~/Downloads` not found** — the stored default path could be a literal `~/...`; every reader and the settings save now expand it, and existing values are normalized.
- **libtorrent overflow spam** — progress/finished Qt signals used 32-bit ints, so torrents >2 GB crashed the status loop repeatedly; switched to 64-bit-safe floats.
- **Silent console** — terminal output is now quiet by default (file logging in `logs/` unchanged).
- **Torrent ↔ main view sync** — torrent rows in All Downloads now update live: status, percent, speed and ETA; sizes persist to History every second.
- **Settings download path** — added a *Browse…* folder picker next to the path field.
- **Clear All now reliably wipes Trash too** — SQLite switched to WAL mode with a 4 s busy timeout and retry logic, so concurrent torrent writes can no longer make the delete fail silently; active torrents are paused first, and the UI confirms success.
- **Accessibility log spam silenced** — the repeated `QAccessibleTable::child: Invalid index` console noise from the download table is filtered via Qt logging rules.

- **Worker crash broke ALL downloads** — the NRE routing edit left a dangling `is_direct_media` reference, failing every download (including YouTube) with a NameError. Fixed and covered by regression tests.
- **YouTube/social regression fixed** — SuperScan was hijacking scans before yt-dlp and returning junk HLS entries from page scripts. Order restored per design: yt-dlp always runs first for known/social sites; SuperScan only engages when yt-dlp fails. Verified: a YouTube URL returns yt-dlp results with SuperScan never called.
- **Logging rule syntax** — Qt logging rules must be semicolon-separated; newline form was rejected at startup.

### Added — N_m3u8DL-RE integration
- New `core/nre.py`: binary auto-detection (PATH, `~/.local/bin`, `/usr/local/bin`), command builder (`--save-dir/--save-name/--tmp-dir`, `--concurrent-download`, Referer/User-Agent headers, `-M format=mp4` mux), live progress parsing (% + speed) and stop/pause control.
- Worker routes OTT streams (`.m3u8`/`.mpd` or scan-flagged HLS/DASH) through N_m3u8DL-RE when installed; falls back to PDM's native HLS engine, then yt-dlp.
- Scanner items now carry `referer`; engine threads stream metadata to workers.

Install: grab the linux-x64 build from https://github.com/nilaoda/N_m3u8DL-RE/releases, `chmod +x N_m3u8DL-RE`, drop it in `~/.local/bin/`.

- **Weird torrent percentages (600%, 137%)** — progress is now clamped to 0–100 at every layer (engine signal, DB writes, model), sizes can never go backwards, and adding a magnet replaces any stale record of the same name instead of stacking rows.
- **PDM SuperScan (own OTT engine)** — new `core/ott_superscan.py` hunts pages the way a browser does: fetches HTML with a real UA (+ optional browser cookies), sweeps inline JSON/config and linked app/player scripts for `.m3u8` / `.mpd` / `.mp4`, detects login walls and DRM markers. Runs BEFORE yt-dlp in the scanner; yt-dlp remains only as fallback. Verified: finds HLS/DASH embedded via escaped JSON and linked config JS, classifies login walls and DRM.
- **Torrent section status stuck on "Queued"** — progress signal was no longer connected to the Torrents view after the sync rework; re-wired.
- **Honest scan failures** — scanner no longer swallows extractor errors: cookie-required sites are classified as sign-in needed, and the dialog now says exactly what to do (e.g. "No hoichoi.tv login session found in Firefox…"), including the real reason when nothing is found.
- **Settings path box width** — the row now stretches so the full path is visible.

- **In-dialog sign-in** — New Download dialog now has a SITE SIGN-IN picker: choose your logged-in browser and re-scan; the choice also feeds Settings.
- **Settings text clipping** — download-path row no longer forced to a fixed width, so field + Browse… render fully.
- **About simplified** — the "What PDM will not do" box was removed.
- **Quiet yt-dlp stderr** — raw extractor errors (e.g. `ERROR: [viewlift] …`) no longer print to the terminal.

- **Browser-cookie support (opt-in)** — new *Settings → Network → Browser Cookies* dropdown reuses a logged-in Firefox/Chrome/Chromium/Brave/Edge/Opera/Vivaldi profile for sites that require sign-in (read-only; close the browser while downloading). Boundary wording on About updated accordingly.

## [1.1] — 2026-08-21

### Fixes
- **Theme switching** — the dark stylesheet shipped as `modern.qss`, so switching Dark→Light worked but Light→Dark silently applied nothing. Renamed to `dark.qss`; both directions verified.
- **BitTorrent "Queued forever"** — two libtorrent 2.x incompatibilities: explicit `flags` dropped `auto_managed` (torrents never left the queue), and `torrent_status.is_paused` no longer exists (poll loop crashed silently on every tick). Migrated to `parse_magnet_uri()` + `add_torrent_params`, flag-safe pause checks, and named-state reporting (`Fetching metadata`, `Connecting`). Poll errors are now logged instead of swallowed. Verified live: ~8 MB/s with 50+ peers on a 1.5 GB magnet.


### Critical Download Fix
- **JavaScript runtime auto-detection** (`core/jsruntime.py`) — modern yt-dlp requires deno/node for YouTube challenge solving; without one it silently degrades to throttled URLs that trigger HTTP 403. PDM now detects and passes the first available runtime to every yt-dlp call (worker, scanner, format probe).
- **Workers write status to SQLite directly** in addition to Qt signals — download state is now correct even when the GUI event loop isn't consuming signals.


### Automation & Protocol Expansion
- **Rules engine** (`core/rules.py`) — domain / extension / filename / size conditions with category + folder routing, priority ordering.
- **Categories** (`core/categories.py`) — six defaults (Video, Audio, Documents, Archives, Programs, Images) with extension-based classification and per-category folders.
- **Scheduler** (`core/scheduler.py`) — weekly download windows; queue pauses outside and resumes inside automatically.
- **BitTorrent** (`download/torrent_engine.py`) — libtorrent-powered magnet/.torrent downloads with DHT, sequential mode and a dedicated Torrents view; degrades gracefully when libtorrent is absent.
- **History view** — complete record of every download including trashed items.
- **About view** — product info plus the permanent boundary statement.

### Browser Integration
- Manifest V3 extension (`extension/`) — "Download with PDM" context menus for links, audio/video and pages.
- Native messaging host (`native_host/pdm_native_host.py`) + installer; job hand-off through `database/inbox/` watched by the desktop app. Only the raw URL crosses the bridge.

### Packaging, CI & Ops
- PyInstaller spec, Linux/macOS build script, Debian control file, Inno Setup definition under `packaging/`.
- GitHub Actions CI matrix (Linux/Windows/macOS × Python 3.11/3.12) with an automated boundary scan that fails builds containing cookie/credential code paths.
- Update checker via GitHub releases (opt-out in Settings), Help-menu diagnostic bundle copier, i18n scaffolding under `translations/`.


### Branding & Theming
- Bundled type system: **Rosehot** (display), **Inter Regular/Medium/SemiBold** (body), **JetBrains Mono** (technical fields) — registered via `QFontDatabase` with documented fallback stacks in `ui/theme.py`.
- **Dual themes**: Dark (default) + Light, generated from one semantic palette; instant switching from Settings → Appearance → Theme with no restart (`ui/styles/dark.qss`, `ui/styles/light.qss`).

### Hard Boundary Enforcement
- Removed all cookie-session import machinery (`core/cookie_browser.py`), the embedded sign-in panel (`ui/widgets/browser_auth_panel.py`, `core/browser_auth.py`), raw-cookie input, and username/password plumbing from the scanner, format probe, dialogs and worker. PDM now downloads publicly accessible content only — by construction, not policy.


Complete reconstruction of PDM into a professional, enterprise-grade desktop tool.

### Added
- **Downloads-first interface** (Free Download Manager style): the app opens straight into the download list — no landing page between you and your files.
- **Category sidebar with live counts**: All Files / Downloading / Queued / Paused / Failed / Completed / Trash, each with an auto-updating badge.
- **Status bar** with active/queued counters, aggregate throughput and total library size.
- **Empty Trash** action in the table context menu.
- **Browser-based authentication** with zero password fields: passive detection of sign-in requirements, session reuse from the user's own browser (Chrome, Firefox, Edge, Brave, Opera, Vivaldi, Safari), automatic scan/probe resume after login, optional raw-cookie advanced mode.
- **IDM-style format picker**: per-resolution video selection (with FPS/HDR tags), audio codec/bitrate selection, MP4/MKV container choice, estimated sizes.
- **Automatic smart naming** derived from the actually-downloaded streams: `Title (Year) [2160p60] [AAC 192kbps] [Source].mp4`.
- **Native download core** (`download/native_engine.py`): first-party multi-threaded HLS engine (manifest parsing, parallel segment pool, atomic `.part` resume, FFmpeg remux to MP4/MKV) alongside the segmented HTTP downloader; universal routing with zero site lists — manifests go native, direct media goes native, everything else falls back to generic extraction.
- **Queue engine**: configurable concurrency (1–10) with automatic queueing and slot release; automatic retry with progressive backoff; per-task speed limits.
- **Professional dark theme** applied at application level (custom QSS + Fusion style): redesigned sidebar, toolbar, status badges, gradient progress bars, dialogs, menus and tooltips.
- **Statistics view** with live aggregate bandwidth graph and peak tracking.
- **System tray** integration (minimize-to-tray, background downloads).
- **Trash workflow**: delete-to-trash plus permanent clear.
- **Context menu** on tasks: Open File, Open Containing Folder, Pause/Resume/Retry, Copy URL, Delete.
- **Project infrastructure**: `pyproject.toml` packaging with `pdm-manager` entry point, pinned dependencies, GitHub Actions CI (compile + entry-point smoke check on Python 3.10–3.13), single-source app constants (`core/constants.py`), `python3 pdm.py` as the single canonical launch command.
- **Documentation**: professional README with real rendered screenshots, banner, architecture diagram, CONTRIBUTING, SECURITY and this changelog.

### Changed
- Main window restructured around a three-page content stack: Downloads → Statistics → Settings, with downloads as the opening view.
- Sidebar rebuilt as FDM-style category filters with live per-status counts; the redundant toolbar status filter was removed.
- Toolbar de-duplicated: Clear List replaced by a contextual Empty Trash action; search retained.
- Removed all username/password authentication paths in favor of browser sessions.

### Removed
- Unused modules: scheduler, verifier, file handler, metadata service, plugin manager, HLS engine stub, embedded login-browser dialog.
- All "PRO" branding.

### Security
- DRM-protected media (Widevine/FairPlay/PlayReady) is detected and explicitly refused rather than producing corrupt files.

## [2.0.0] — earlier

Initial Python/PySide6 rewrite with basic download management, media scanning and settings persistence.
