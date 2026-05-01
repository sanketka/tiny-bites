# tiny-bites

Know what's for breakfast before you go to bed. Daily AI-generated recipes for your toddler, based on your pantry and your child's age.

The bot reads your pantry, generates a safe and nutritious recipe using Claude, and sends it to your phone every evening. Safety rules (textures, choking hazards, portions) automatically adjust as your child grows.

![Telegram recipe message](https://github.com/user-attachments/assets/89ab2890-f0c4-47bc-aca5-e17ec6c62bb3)

## Quick Start

1. Fork this repo and clone your fork
2. Make sure you have Python 3.9+ installed
3. Install dependencies and run the guided setup:

```bash
pip install -r requirements.txt
python setup_bot.py
```

The setup walks you through everything: Anthropic API key, Telegram bot, your child's details, delivery schedule, and preferences. At the end it runs a live test (a real recipe gets sent to your Telegram), sets your GitHub secrets automatically, and commits and pushes for you.

That's it. You'll get your first recipe at the time you chose during setup.

![Setup flow](https://github.com/user-attachments/assets/5d229d2c-273d-4335-a7fe-dd155897eda6)

## Prerequisites

- **Python 3.9+**
- **GitHub CLI (`gh`)** — recommended. The setup script uses it to set your repo secrets automatically. Install with `brew install gh`, then run `gh auth login`. [Other platforms](https://cli.github.com/manual/installation). If you skip this, you'll set the three secrets manually in GitHub.
- **Telegram account** and a bot — see [Setting up Telegram](#setting-up-telegram) below
- **Anthropic API key** from [console.anthropic.com](https://console.anthropic.com) (Claude Haiku costs fractions of a cent per recipe)
- **GitHub account** (GitHub Actions runs the bot on schedule, free for public repos)

## What Setup Does

`python setup_bot.py` handles the full onboarding in one flow:

1. **Prerequisites** — checks gh CLI, walks you through getting an Anthropic API key and creating a Telegram bot, auto-detects your chat ID
2. **Your child** — name, birthday (age is calculated automatically from this)
3. **Location** — city (for seasonal pantry suggestions) and timezone
4. **Preferences** — cuisine style (Western, Indian, or mixed), allergies
5. **Schedule** — what time to receive recipes, which day to get pantry suggestions
6. **Pantry** — option to open `pantry.txt` in your editor before continuing
7. **Live test** — runs `send_breakfast.py` right now so you can confirm a recipe arrives in Telegram before going live
8. **GitHub secrets** — sets `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID` in your repo via gh CLI (or prints instructions to do it manually)
9. **Commit and push** — commits your config and the generated GitHub Actions workflow, then pushes

## Setting up Telegram

You need two things: a **bot token** and your **chat ID**.

**Create your bot:**

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Pick a display name (e.g. "Breakfast Bot")
4. Pick a username — must end in `bot` (e.g. `my_breakfast_bot`)
5. BotFather replies with your **bot token** — it looks like `123456789:ABCdefGhIjKlmNoPQRsTUVwXyz`. Save it.

The setup script auto-detects your chat ID after you paste your token and send your bot any message. You only need to look it up manually if auto-detection fails.

## How It Works

Every day at your chosen time, a GitHub Action:

1. Reads your pantry (`pantry.txt`) and preferences (`config.toml`)
2. Sends them to Claude Haiku with safety rules for your child's age
3. Gets back a recipe with nutrition info, ingredients, and steps
4. Sends it to your Telegram
5. Logs the recipe name to avoid repeats

On your chosen day of the week, it also suggests seasonal ingredients available near you.

![Pantry suggestions message](https://github.com/user-attachments/assets/dc15411d-8a0a-4e0c-bd2b-1d7dbc21d3e6)

## Configuration

All settings live in `config.toml`. Edit it directly or re-run `python setup_bot.py`.

| Section | What it controls |
|---------|-----------------|
| `[child]` | Name and birthday (age is calculated automatically) |
| `[location]` | City (for seasonal suggestions) and timezone |
| `[preferences]` | Cuisine style, nutrition priorities, allergies |
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
