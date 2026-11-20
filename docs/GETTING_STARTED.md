# Getting started

Twelve steps from a new Mac to HomeFix running offline. Back to the [README](../README.md).

HomeFix runs on **macOS on Apple Silicon** only (M1 or newer). Speech uses `mlx-whisper`, which needs
Apple Silicon, and Ollama must run natively to use the GPU. The first setup takes about 30 to 60
minutes, most of it downloading models (about 14 GB on `full`, 5 GB on `lite`).

## Step 1. Check your Mac and Homebrew

```bash
uname -m            # must print arm64
brew --version      # any version
git --version       # any version
```

If `brew` is missing, install it from <https://brew.sh>. The setup script installs everything else.

## Step 2. Get the code

```bash
git clone https://github.com/meghana2108/Homefix.git
cd Homefix
```

Run every remaining command from inside this `Homefix` folder unless the step says otherwise.

## Step 3. Install everything

```bash
bash scripts/setup_mac.sh
```

This installs what is missing: ffmpeg, the Ollama app, uv, Python 3.11 (through uv), Node 20, the
Python packages (about 1.5 GB, most of it torch) and the web packages. It is safe to run again. It also
creates `.env` from `.env.example`.

If it says `node -v` is not v20, run the `export PATH=...` line it prints, then open a new terminal.

## Step 4. Pick a profile

Open `.env` and set `PROFILE`:

| Your Mac | `PROFILE` | Models |
| --- | --- | --- |
| 16 GB or more | `full` | `qwen3-vl:8b-instruct` (vision), `qwen2.5-coder:7b` (code), Whisper large-v3-turbo |
| 8 GB | `lite` | `qwen3-vl:2b-instruct`, `qwen2.5-coder:3b`, Whisper small.en, one LLM loaded at a time |

Both profiles use CLAP (`laion/clap-htsat-unfused`) for sounds and `bge-small-en-v1.5` for long
documents. `PRACTICE_PACK_DIR` is only needed for the eval (see [Tests and checks](DEVELOPMENT.md#tests-and-checks)).

## Step 5. Download the models

Open the Ollama app (it shows an icon in the menu bar), then:

```bash
bash scripts/pull_models.sh full --final     # or: lite --final
```

`--final` downloads only the models the profile uses. Without it, the script also downloads the
models we compared against (about 23 GB on `full`, 10 GB on `lite`).

## Step 6. Make the example files and sample manuals

```bash
uv run python scripts/make_samples.py           # our drawn photos, sounds, voice notes, clips and guides
uv run python scripts/fetch_real_samples.py     # real photos, a smoke alarm chirp and public guides; needs the network, slow
```

The first script works offline. It writes the gallery files to `frontend/public/samples/` and the
sample manuals to `data/manuals/` (including the Unit 4B apartment guide the demo uses). Both folders
are gitignored, so every Mac runs these once.

## Step 7. Check the machine

```bash
uv run python scripts/go_no_go.py
```

It runs one question through each model and prints a table with `GO` or `NO-GO` for each one, with
times and memory. Fix any `NO-GO` before going on (see [Troubleshooting](DEVELOPMENT.md#troubleshooting)).

## Step 8. Start the backend

Terminal 1:

```bash
uv run uvicorn app.api.main:app --port 8000
```

`PROFILE` comes from `.env`. Every model starts loading in the background as soon as the API starts.
Leave this terminal open.

## Step 9. Start the web app

Terminal 2:

```bash
cd frontend && npm run dev
```

Leave this terminal open too. When it prints a `Local:` address on port 5173, go to the next step.

## Step 10. Open it in your browser

Go to **<http://localhost:5173>**.

- **Open HomeFix** (top right) opens the app. The header says "Getting ready: Speech (2 of 5)" while
  the models load, then shows the profile. On the M2 this takes about 29 s from a cold start.
- **Ask about something at home** plays the demo (`#/demo`): eight short scenes with answers recorded
  on the M4. See [The demo](../README.md#the-demo).

To try the app, pick an example from **Try an example** (a washer error code, a smoke alarm chirp, a
lease question, a video, a coding task), or type a question and drop in a photo, sound, video or file.

## Step 11. Go offline and check

Turn Wi-Fi off, then, with the backend running:

```bash
bash scripts/offline_check.sh full     # or: lite
```

It checks that the network is unreachable, that every model is on disk, runs the go/no-go test and
asks the API for its health. It must end with `OFFLINE CHECK PASSED`.

## Step 12. Stop the app

Press **Ctrl+C** in both terminals. To free the model's memory too, run
`ollama stop qwen3-vl:8b-instruct` (or `qwen3-vl:2b-instruct` on `lite`).

## Running it again later

Open Ollama, then steps 8 to 10:

```bash
cd Homefix
uv run uvicorn app.api.main:app --port 8000     # terminal 1
cd frontend && npm run dev                      # terminal 2
```

## Without the browser (optional)

Run one question from the terminal through the same code the API uses:

```bash
uv run python -m app.cli "What should I do?" --file frontend/public/samples/washer_display_e21.jpg \
  --manual apartment_guide_unit_4b
```

It prints each step as it happens (`[status]`, `[citation]`, the answer). `--json` prints the raw
events, and `--profile lite` overrides `.env`.

## On a phone (optional)

Camera and microphone need HTTPS. With the backend running and the phone on the same network:

```bash
brew install mkcert                 # once, needs the network
bash scripts/https_dev.sh
```

Open the address it prints on the phone. With Wi-Fi off there is no network between phone and
laptop, so this only works on a local network. See [docs/DEMO.md](DEMO.md).

If something goes wrong, see [Troubleshooting](DEVELOPMENT.md#troubleshooting).
