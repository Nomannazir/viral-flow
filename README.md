# ViralFlow — Automated DIY Viral Video Pipeline

ViralFlow is a fully automated pipeline that discovers trending DIY topics, generates a step-by-step video storyboard with Claude AI, fetches real stock footage from Pexels, assembles a polished short-form video with bold text overlays, and uploads it to YouTube Shorts — all with one command.

```
Trending topic → Claude storyboard → FLUX before/after images
     → Pexels stock clips → FFmpeg assembly → YouTube upload
```

---

## How It Works

1. **Trend Fetch** — pulls trending DIY topics from YouTube Shorts, Reddit (r/DIY, r/lifehacks, etc.), and a built-in evergreen fallback list
2. **Score** — Claude Haiku scores each topic 1–10 for virality (transformation potential, cost appeal, beginner-friendliness)
3. **Storyboard** — Claude Sonnet/Haiku generates a full video plan: hook text, 5 steps with on-screen labels and Pexels search keywords, before/after image prompts, reveal text, CTA
4. **Images** — FLUX Pro generates photorealistic before/after images for the hook and reveal segments
5. **Stock Clips** — Pexels API fetches one real portrait video clip per step (free, no AI artifacts)
6. **Assemble** — FFmpeg trims clips, Pillow burns bold text overlays (step labels + instructions) onto every segment, then concatenates with optional voiceover and/or background music
7. **Publish** — uploads the final video and thumbnail to YouTube Shorts via OAuth

---

## Project Structure

```
viral_flow/
├── orchestrator.py          # Main entry point — runs the full pipeline
├── config.py                # All settings loaded from environment variables
├── requirements.txt
├── music/                   # Drop royalty-free MP3s here for background music
├── output/                  # Generated videos saved here (git-ignored)
├── pipeline/
│   ├── trends.py            # Trend fetching (YouTube, Reddit, fallback list)
│   ├── scorer.py            # Claude Haiku topic scoring
│   ├── scripter.py          # Claude storyboard generation
│   ├── visuals.py           # Pexels stock clips + FLUX AI images
│   ├── assembler.py         # FFmpeg + Pillow video assembly
│   ├── voice.py             # ElevenLabs / Kokoro TTS (optional)
│   └── publisher.py         # YouTube upload
└── db/
    ├── client.py            # Supabase client (optional)
    └── schema.sql           # Database schema
```

---

## Prerequisites

### Required on all platforms

| Tool | Purpose | Notes |
|------|---------|-------|
| Python 3.9+ | Runtime | python.org |
| FFmpeg + FFprobe | Video assembly | FFprobe is included with FFmpeg |

### API Keys

| Service | Used for | Cost |
|---------|---------|------|
| [Anthropic](https://console.anthropic.com) | Topic scoring + storyboard | ~$0.01–0.05 per video |
| [fal.ai](https://fal.ai) | FLUX image generation | ~$0.04 per image |
| [Pexels](https://www.pexels.com/api/) | Stock video clips | Free (200 req/hour) |
| [Google Cloud](https://console.cloud.google.com) | YouTube upload | Free quota |

### Optional

| Service | Used for |
|---------|---------|
| [ElevenLabs](https://elevenlabs.io) | High-quality voiceover (falls back to Kokoro if not set) |
| [Reddit](https://www.reddit.com/prefs/apps) | Additional trend data |
| [Supabase](https://supabase.com) | Persistent video history database |

---

## Installation

### macOS

```bash
# 1. Install FFmpeg
brew install ffmpeg

# 2. Clone the repo
git clone https://github.com/Nomannazir/viral-flow.git
cd viral-flow

# 3. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment variables
cp .env.example .env
# Open .env in any editor and fill in your keys
```

### Windows

```powershell
# 1. Install FFmpeg
# Download from https://ffmpeg.org/download.html (Windows builds by BtbN or gyan.dev)
# Extract the zip, then add the bin\ folder to your system PATH:
#   System Properties → Environment Variables → Path → New → paste the bin\ path
# Verify in a new terminal: ffmpeg -version

# 2. Clone the repo
git clone https://github.com/Nomannazir/viral-flow.git
cd viral-flow

# 3. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment variables
copy .env.example .env
# Open .env in Notepad or VS Code and fill in your keys
```

---

## Configuration

Create a `.env` file in the project root. Never commit this file.

```env
# ── Required ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...
FAL_KEY=...
PEXELS_API_KEY=...

# ── YouTube (required for publishing) ─────────────────────────────────────────
# Path to the OAuth credentials JSON downloaded from Google Cloud Console
YOUTUBE_CREDENTIALS_FILE=credentials.json

# ── Optional: higher quality voiceover ────────────────────────────────────────
ELEVEN_API_KEY=...
ELEVEN_VOICE_ID=...              # e.g. 21m00Tcm4TlvDq8ikWAM

# ── Optional: Reddit trend source ─────────────────────────────────────────────
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...

# ── Optional: database persistence ────────────────────────────────────────────
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=...

# ── Pipeline settings (defaults shown) ────────────────────────────────────────
NICHE=diy
PLATFORM=youtube
VIDEOS_PER_RUN=3                 # videos to produce per run
VIDEO_DURATION=45                # target video length in seconds
USE_VOICEOVER=true               # false = music only, no narration
MUSIC_DIR=music                  # folder containing background MP3 files
OUTPUT_DIR=./output
MAX_DAILY_FAL_SPEND=8.0          # safety spend cap in USD
TTS_SCORE_THRESHOLD=8            # min virality score to use ElevenLabs
```

### How to Get Each API Key

**Anthropic**
1. Sign up at [console.anthropic.com](https://console.anthropic.com)
2. Go to **API Keys** → **Create Key**

**fal.ai**
1. Sign up at [fal.ai](https://fal.ai)
2. Go to **Dashboard** → **API Keys** → **Add Key**

**Pexels**
1. Go to [pexels.com/api](https://www.pexels.com/api/)
2. Click **Get Started** — approval is instant

**YouTube / Google Cloud**
1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a project
2. Go to **APIs & Services** → **Enable APIs** → search for and enable **YouTube Data API v3**
3. Go to **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
4. Choose **Desktop App**, give it a name, click **Create**
5. Click **Download JSON** and save the file as `credentials.json` in the project root
6. On the **first run**, a browser window opens for you to log in and authorize the app. The token is saved as `youtube_token.pickle` for all future runs.

**ElevenLabs** *(optional)*
1. Sign up at [elevenlabs.io](https://elevenlabs.io)
2. Go to **Profile** → copy your **API Key**
3. Browse **Voice Library**, open a voice, and copy the **Voice ID** from its settings page

**Reddit** *(optional)*
1. Go to [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
2. Click **Create App** → choose **script** type
3. Copy the **client ID** (under the app name) and the **secret**

---

## Running the Pipeline

Activate your virtual environment first:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### Commands

```bash
# Preview only — score topics and print storyboard, no images or video generated
python orchestrator.py --dry-run

# Test a specific topic (skips trend fetching)
python orchestrator.py --dry-run --topic "Pantry makeover with dollar store bins"

# Produce 1 video, save locally without uploading
python orchestrator.py --videos 1 --no-publish

# Produce and publish to YouTube (full run)
python orchestrator.py

# Produce 3 videos and publish
python orchestrator.py --videos 3
```

### All CLI Flags

| Flag | Description |
|------|-------------|
| `--dry-run` | Print storyboard only — no image/video generation, no API spend on media |
| `--topic "..."` | Skip trend fetch and use this exact topic |
| `--videos N` | Number of videos to produce this run (overrides `VIDEOS_PER_RUN`) |
| `--no-publish` | Assemble video but skip YouTube upload |

---

## Background Music

Create a `music/` folder and drop any royalty-free MP3 files inside:

```bash
mkdir music
# copy your MP3 files here
```

The pipeline picks one track at random per video and mixes it at 15% volume under the voiceover. If the folder is empty or missing, videos are produced without background music.

Recommended free sources:
- [YouTube Audio Library](https://studio.youtube.com/channel/music) — free for any use
- [Pixabay Music](https://pixabay.com/music/) — no attribution needed
- [Bensound](https://www.bensound.com) — attribution required on free tier

---

## Output Files

Each video run creates a timestamped folder under `output/`:

```
output/
└── a1b2c3d4/
    ├── before.jpg          # FLUX "before" hook image
    ├── after.jpg           # FLUX "after" reveal image
    ├── thumbnail.jpg       # YouTube thumbnail
    ├── voice.mp3           # Voiceover audio (if enabled)
    ├── clips/              # Pexels stock clips, one per step
    ├── segments/           # Per-segment videos with text overlays burned in
    ├── silent.mp4          # Concatenated video before audio mix
    ├── final.mp4           # Finished video ready for upload
    └── metadata.json       # Topic, title, YouTube URL, created_at timestamp
```

---

## Cost per Video (approximate)

| Item | Cost |
|------|------|
| Claude Haiku — scoring | ~$0.001 |
| Claude Sonnet — storyboard (score ≥ 8) | ~$0.01 |
| 2× FLUX images (before + after) | ~$0.08 |
| 1× FLUX thumbnail | ~$0.04 |
| 5× Pexels stock clips | Free |
| Kokoro TTS voiceover (default) | ~$0.02 |
| ElevenLabs TTS (optional, score ≥ 8) | ~$0.05 |
| **Total per video** | **~$0.15 – $0.20** |

---

## Troubleshooting

**`ffmpeg: command not found`**
- macOS: `brew install ffmpeg`
- Windows: make sure the FFmpeg `bin\` folder is added to your system PATH (see Installation above)

**`PEXELS_API_KEY not set`**
- Add the key to your `.env` file and restart your terminal

**`YouTube credentials file not found: credentials.json`**
- Download the OAuth JSON from Google Cloud Console and save it as `credentials.json` in the project root
- Make sure `YOUTUBE_CREDENTIALS_FILE=credentials.json` is set in `.env`

**YouTube browser window does not open on first run**
- Run the script in a terminal that has a display (not SSH without X forwarding)
- On Windows, ensure the terminal can open a browser

**`Anthropic API credit balance is zero`**
- Add credits at [console.anthropic.com → Plans & Billing](https://console.anthropic.com)
- The pipeline automatically falls back to keyword-based scoring when Claude is unavailable

**`No Pexels results for keyword`**
- Run with `--dry-run` first to inspect the `visual_keyword` fields in the generated storyboard
- If a step clip fails, the pipeline reuses the previous step's clip so the video still assembles

**Text overlays not appearing**
- Install Pillow: `pip install Pillow`
- Without Pillow the video still assembles but without text overlays

**YouTube quota exceeded**
- YouTube Data API v3 free quota is 10,000 units/day; each upload costs ~1,600 units (~6 uploads/day)
- Apply for a quota increase in Google Cloud Console under **APIs & Services → Quotas**

---

## Scheduling Automatic Runs

**macOS / Linux — cron**
```bash
crontab -e
# Add this line to run at 8am every day:
0 8 * * * cd /path/to/viral-flow && .venv/bin/python orchestrator.py >> logs/run.log 2>&1
```

**Windows — Task Scheduler**
1. Open **Task Scheduler** → **Create Basic Task**
2. Set the trigger to **Daily**
3. Action: **Start a Program**
   - Program: `C:\path\to\viral-flow\.venv\Scripts\python.exe`
   - Arguments: `orchestrator.py`
   - Start in: `C:\path\to\viral-flow`

---

## Extending the Pipeline

- **New niche** — update the fallback topic list in `pipeline/trends.py` and the prompts in `pipeline/scorer.py` and `pipeline/scripter.py`
- **New platform** — add a publisher in `pipeline/` (TikTok, Instagram Reels) and wire it into `orchestrator.py`
- **Analytics feedback** — after 48h, fetch YouTube view counts and store against each video in Supabase to learn which topics perform best
