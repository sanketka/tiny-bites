# Tiny Bites – The Baby Breakfast Bot

Know what's for breakfast before you go to bed. Daily AI-generated recipes for your toddler, based on your pantry and your child's age.

The bot reads your pantry, generates a safe and nutritious recipe using Claude, and sends it to your phone every evening. Safety rules (textures, choking hazards, portions) automatically adjust as your child grows.

## Quick Start

1. Fork this repo and clone your fork
2. Make sure you have Python 3.9+ installed
3. Run the setup:

```bash
pip install -r requirements.txt
python setup_bot.py
```

4. Follow the prompts (takes about 5 minutes)
5. Commit and push:

```bash
git add -A && git commit -m "Configure breakfast bot" && git push
```

That's it. You'll get your first recipe at the time you chose during setup.

## Prerequisites

- **Python 3.9+**
- **Telegram account** and a bot — see [Setting up Telegram](#setting-up-telegram) below
- **Anthropic API key** from [console.anthropic.com](https://console.anthropic.com) (Claude Haiku costs fractions of a cent per recipe)
- **GitHub account** (GitHub Actions runs the bot on schedule, free for public repos)

## Setting up Telegram

You need two things: a **bot token** and your **chat ID**.

**Create your bot:**

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Pick a display name (e.g. "Breakfast Bot")
4. Pick a username — must end in `bot` (e.g. `my_breakfast_bot`)
5. BotFather replies with your **bot token** — it looks like `123456789:ABCdefGhIjKlmNoPQRsTUVwXyz`. Save it.

**Find your chat ID:**

1. Send any message to your new bot in Telegram
2. Open this URL in your browser (replace `TOKEN` with your bot token):
   ```
   https://api.telegram.org/botTOKEN/getUpdates
   ```
3. Look for `"chat":{"id":XXXXXXXXX}` — that number is your chat ID

The setup script handles step 2 automatically after you paste your token. You only need to look it up manually if auto-detection fails.

## How It Works

Every day at your chosen time, a GitHub Action:

1. Reads your pantry (`pantry.txt`) and preferences (`config.toml`)
2. Sends them to Claude Haiku with safety rules for your child's age
3. Gets back a recipe with nutrition info, ingredients, and steps
4. Sends it to your Telegram
5. Logs the recipe name to avoid repeats

On your chosen day of the week, it also suggests seasonal ingredients available near you.

## Configuration

All settings live in `config.toml`. Edit it directly or re-run `python setup_bot.py`.

| Section | What it controls |
|---------|-----------------|
| `[child]` | Name and birthday (age is calculated automatically) |
| `[location]` | City (for seasonal suggestions) and timezone |
| `[preferences]` | Cuisine style, prep time, nutrition priorities, allergies |
| `[schedule]` | Delivery time and pantry suggestions day |

## Updating Your Pantry

Edit `pantry.txt` whenever you go grocery shopping. The bot only suggests recipes using ingredients listed there, so keep it current.

```
Proteins: Eggs, Yogurt, Tofu
Carbs: Oats, Whole Wheat Bread
Produce: Bananas, Blueberries, Spinach
```

Commit and push after editing. The bot picks up changes on the next run.

## Schedule and Daylight Saving

GitHub Actions cron runs in UTC. The setup script calculates the correct UTC time from your timezone, but it doesn't auto-adjust for daylight saving transitions.

After clocks change (spring/fall), run:

```bash
python setup_bot.py --update-schedule
```

Then commit and push the updated workflow.

## Running Locally

For testing, set the required environment variables and run:

```bash
export ANTHROPIC_API_KEY="your-key"
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"
python send_breakfast.py
```

Or trigger the GitHub Action manually:

```bash
gh workflow run daily_breakfast.yml
```

## License

MIT
