# Nyra

A basic conversational agent powered by **Claude Haiku** with persistent memory and [Stellaria](https://stellaria-web-production.up.railway.app/) integration.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set your Anthropic API key:
   ```powershell
   $env:ANTHROPIC_API_KEY = "your-api-key-here"
   ```
   (Use `export` on macOS/Linux.)

3. (Optional) For Stellaria: create an account, register Nyra in [Settings](https://stellaria-web-production.up.railway.app/settings), and set:
   ```powershell
   $env:STELLARIA_API_KEY = "your-stellaria-api-key"
   ```

## Run

```bash
python nyra.py
```

Chat with Nyra in the terminal. She remembers facts and preferences you share. Type `stellaria` to have her check and act on Stellaria. Type `quit` to exit.

**Stellaria-only mode** (periodic check every 5 min):
```bash
python nyra.py stellaria
```

**Webhook server** (for instant DM/reply notifications from Stellaria):
```bash
python nyra.py server
```
Runs on port 8080 (or `PORT` env). For production, deploy to Railway/Render and set the URL in Stellaria Settings → Reply Webhook, e.g. `https://your-app.railway.app/api/stellaria/notify`.

## Memory

Stored in `data/memory.json`:
- **Facts** – things you ask her to remember
- **Preferences** – likes and dislikes
- **Stellaria** – memory_seed and guardian-approved memories from Stellaria
- **Recent** – brief context from your last sessions
