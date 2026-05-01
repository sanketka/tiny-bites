#!/usr/bin/env python3
"""
tiny-bites — Interactive Setup

Run this script after forking/cloning the repo to configure
the bot for your child. It walks you through each setting and
generates the files the bot needs to run.

Usage:
    python setup_bot.py                   # Full guided setup
    python setup_bot.py --update-schedule # Recalculate cron after DST change
"""

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCRIPT_DIR = Path(__file__).parent

COMMON_TIMEZONES = [
    ("America/New_York",    "US Eastern"),
    ("America/Chicago",     "US Central"),
    ("America/Denver",      "US Mountain"),
    ("America/Los_Angeles", "US Pacific"),
    ("America/Phoenix",     "US Arizona (no DST)"),
    ("Europe/London",       "UK"),
    ("Europe/Berlin",       "Central Europe"),
    ("Asia/Kolkata",        "India"),
    ("Asia/Tokyo",          "Japan"),
    ("Australia/Sydney",    "Australia Eastern"),
]


# ── Style ─────────────────────────────────────────────────────

_USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

def bold(t: str) -> str:   return _c("1", t)
def dim(t: str) -> str:    return _c("2", t)
def green(t: str) -> str:  return _c("32", t)
def red(t: str) -> str:    return _c("31", t)
def cyan(t: str) -> str:   return _c("36", t)
def yellow(t: str) -> str: return _c("33", t)

def ok(msg: str = "") -> str:  return green(f"✓{' ' + msg if msg else ''}")
def err(msg: str = "") -> str: return red(f"✗{' ' + msg if msg else ''}")


# ── Layout ────────────────────────────────────────────────────

def section(title: str) -> None:
    pad = 44 - len(title)
    print(f"\n  {cyan(bold(title))} {dim('─' * max(pad, 2))}\n")


def ask(label: str, default: str = "") -> str:
    """Single-line prompt. Returns stripped input or default."""
    suffix = f"  {dim('(' + default + ')')}" if default else ""
    line = f"  {bold(label)}{suffix}  "
    if default:
        val = input(line).strip()
        return val if val else default
    else:
        while True:
            val = input(line).strip()
            if val:
                return val
            print(f"  {red('Required.')}")


def choose(label: str, options: list, default: int = 1) -> int:
    """Show numbered options, return 1-based index."""
    print(f"  {bold(label)}")
    for i, opt in enumerate(options, 1):
        tag = dim("  ← default") if i == default else ""
        print(f"    {dim(str(i) + ')')} {opt}{tag}")
    while True:
        raw = input(f"  {dim('›')} [{default}]: ").strip()
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw)
        print(f"  {red('Enter a number 1–' + str(len(options)) + '.')}")


# ── Core helpers ──────────────────────────────────────────────

def validate_timezone(tz: str) -> bool:
    try:
        ZoneInfo(tz)
        return True
    except (ZoneInfoNotFoundError, KeyError):
        return False


def compute_utc_cron(hour: int, minute: int, timezone: str) -> str:
    tz = ZoneInfo(timezone)
    local = datetime.now(tz).replace(hour=hour, minute=minute, second=0, microsecond=0)
    utc = local.astimezone(ZoneInfo("UTC"))
    return f"{utc.minute} {utc.hour} * * *"


def validate_telegram_token(token: str) -> str:
    """Returns bot username if token is valid, empty string if not."""
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("ok"):
            return data["result"].get("username", "")
    except Exception:
        pass
    return ""


def fetch_chat_id(token: str) -> tuple:
    """Returns (chat_id, error). chat_id is '' on failure; error is 'no_messages' or a description."""
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("ok"):
            if data.get("result"):
                return str(data["result"][-1]["message"]["chat"]["id"]), ""
            return "", "no_messages"
        return "", data.get("description", "unknown error")
    except Exception as e:
        return "", str(e)


def check_anthropic_key(key: str) -> bool:
    """Validate key against the models endpoint — no tokens consumed."""
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


# ── Prerequisites ─────────────────────────────────────────────

def prereq_gh_cli() -> None:
    """Check for gh CLI — soft gate, warns but does not block."""
    section("GitHub CLI  (1 of 3)")
    print(f"  {dim('The GitHub CLI sets your repo secrets automatically.')}")
    print(f"  {dim('Optional — you can paste secrets manually in GitHub if you skip this.')}\n")

    gh = shutil.which("gh")
    if not gh:
        print(f"  {yellow('gh CLI not found.')}\n")
        print(f"  To install it:")
        print(f"    Mac:   {bold('brew install gh')}")
        print(f"    Other: {cyan('cli.github.com/manual/installation')}\n")
        print(f"  Once installed, run {bold('gh auth login')} to connect it to GitHub.\n")
        print(f"  {dim('Continuing without it — you will set secrets manually after setup.')}")
        input(f"\n  {dim('Press Enter to continue')}  ")
        return

    result = subprocess.run([gh, "auth", "status"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  {yellow('gh CLI is installed but not authenticated.')}\n")
        print(f"  Fix it in a new terminal window:")
        print(f"    {bold('gh auth login')}\n")
        print(f"  Then re-run this setup, or press Enter to continue and set secrets manually.")
        input(f"\n  {dim('Press Enter to continue')}  ")
        return

    print(f"  {ok('gh CLI is installed and authenticated')}")


def prereq_anthropic_key() -> str:
    """Walk the user through getting and validating their Anthropic API key."""
    section("Anthropic API Key  (2 of 3)")
    print(f"  {dim('The bot uses Claude to generate recipes.')}")
    print(f"  {dim('Cost: roughly $1/year at daily use — effectively free.')}\n")

    print(f"  {bold('How to get your API key:')}")
    print(f"    1) Go to {cyan('console.anthropic.com/settings/api-keys')}")
    print(f"    2) Click {bold('+ Create Key')}")
    print(f"    3) Name it anything (e.g. {dim('tiny-bites')})")
    print(f"    4) Copy the key — it starts with {dim('sk-ant-')}\n")

    while True:
        key = input(f"  {bold('Paste API key')}  ").strip()
        if not key.startswith("sk-ant-"):
            print(f"  {red('Looks wrong — Anthropic keys start with sk-ant-')}\n")
            continue
        print(f"  Validating...", end="", flush=True)
        if check_anthropic_key(key):
            print(f"\r  {ok('API key is valid')}         ")
            return key
        print(f"\r  {err('Rejected by Anthropic.')} Double-check the key and try again.\n")


def prereq_telegram() -> tuple:
    """Walk the user through creating a Telegram bot and getting their chat ID."""
    section("Telegram  (3 of 3)")
    print(f"  {dim('The bot sends recipes via Telegram.')}")
    print(f"  {dim('You need two things: a bot token and your personal chat ID.')}\n")

    print(f"  {bold('Step 1 — Create a Telegram bot:')}")
    print(f"    1) Open Telegram and search for {cyan('@BotFather')}")
    print(f"    2) Tap Start, then send {bold('/newbot')}")
    print(f"    3) Pick a display name — e.g. {dim('Ayan Breakfast Bot')}")
    print(f"    4) Pick a username — must end in {bold('bot')} — e.g. {dim('ayan_breakfast_bot')}")
    print(f"    5) BotFather replies with a token — copy it\n")

    while True:
        token = input(f"  {bold('Paste bot token')}  ").strip()
        if not re.match(r"^\d+:[A-Za-z0-9_-]+$", token):
            print(f"  {red('Looks wrong — should be like: 123456789:ABCdefGhijkl...')}\n")
            continue
        print(f"  Validating token...", end="", flush=True)
        bot_username = validate_telegram_token(token)
        if bot_username:
            print(f"\r  {ok('Connected to @' + bot_username)}         ")
            break
        print(f"\r  {err('Token rejected by Telegram.')} Double-check and try again.\n")

    print(f"\n  {bold('Step 2 — Get your chat ID:')}")
    print(f"    1) Find @{bot_username} in Telegram")
    print(f"    2) Send it any message — e.g. {dim('hello')}")
    print(f"    3) Press Enter below — we will auto-detect your chat ID\n")

    while True:
        input(f"  {dim('Press Enter once you have sent a message to your bot')}  ")
        print(f"  Looking up your chat ID...", end="", flush=True)
        chat_id, error = fetch_chat_id(token)

        if chat_id:
            print(f"\r  {ok('Chat ID: ' + chat_id)}         ")
            break
        elif error == "no_messages":
            print(f"\r  {yellow('No messages found.')} Make sure you sent a message to @{bot_username}, then press Enter to try again.\n")
        else:
            print(f"\r  {yellow('Could not auto-detect your chat ID.')}\n")
            print(f"  Find it manually:")
            print(f"    1) Open this URL in your browser:")
            print(f"       {dim('https://api.telegram.org/bot' + token + '/getUpdates')}")
            print(f"    2) Look for {bold('result[0].message.chat.id')} in the response")
            print(f"    3) Paste that number below\n")
            while True:
                chat_id = input(f"  {bold('Chat ID')}  ").strip()
                if chat_id.lstrip("-").isdigit():
                    print(f"  {ok('Chat ID: ' + chat_id)}")
                    break
                print(f"  {red('Should be a number — e.g. 123456789.')}\n")
            break

    return token, chat_id


def collect_prerequisites() -> dict:
    prereq_gh_cli()
    anthropic_key = prereq_anthropic_key()
    telegram_token, telegram_chat_id = prereq_telegram()
    return {
        "anthropic_key": anthropic_key,
        "telegram_token": telegram_token,
        "telegram_chat_id": telegram_chat_id,
    }


# ── Collectors ────────────────────────────────────────────────

def collect_child_info() -> dict:
    section("Your child")
    name = ask("Name", default="Baby")

    while True:
        raw = ask("Birthday (MM/DD/YYYY)")
        try:
            bday = datetime.strptime(raw, "%m/%d/%Y").date()
            today = datetime.now().date()
            months = (today.year - bday.year) * 12 + (today.month - bday.month)
            if months < 0:
                print(f"  {red('That date is in the future.')}")
            elif months > 60:
                print(f"  {red('That is over 5 years ago — double-check.')}")
            else:
                print(f"  {ok(name + ' · ' + str(months) + ' months old')}")
                break
        except ValueError:
            print(f"  {red('Use MM/DD/YYYY — e.g. 06/15/2024')}")

    return {"name": name, "birthday": bday.strftime("%Y-%m-%d")}


def collect_location() -> dict:
    section("Location")
    city = ask("City", default="San Francisco, CA")

    print(f"\n  {bold('Timezone')}")
    for i, (tz, label) in enumerate(COMMON_TIMEZONES, 1):
        tag = dim("  ← default") if i == 4 else ""
        print(f"    {dim(str(i) + ')')} {label:<26}{dim('(' + tz + ')')}{tag}")
    print(f"    {dim(str(len(COMMON_TIMEZONES) + 1) + ')')} Other")

    while True:
        raw = input(f"  {dim('›')} [4]: ").strip()
        if not raw:
            timezone = "America/Los_Angeles"
            break
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(COMMON_TIMEZONES):
                timezone = COMMON_TIMEZONES[idx - 1][0]
                break
            elif idx == len(COMMON_TIMEZONES) + 1:
                while True:
                    tz_input = input(f"  {bold('IANA timezone')}  ").strip()
                    if validate_timezone(tz_input):
                        timezone = tz_input
                        break
                    print(f"  {red('Invalid. Example: Asia/Singapore')}")
                break
            else:
                print(f"  {red('Enter 1–' + str(len(COMMON_TIMEZONES) + 1) + '.')}")
        elif validate_timezone(raw):
            timezone = raw
            break
        else:
            print(f"  {red('Not a valid selection.')}")

    print(f"  {ok(timezone)}")
    return {"city": city, "timezone": timezone}


def collect_preferences() -> dict:
    section("Preferences")

    cuisine_idx = choose(
        "Cuisine style",
        ["Western   (eggs, oats, toast, yogurt)",
         "Indian    (poha, upma, idli, chilla)",
         "Mixed     (rotate between both)"],
        default=3,
    )
    cuisine = ["western", "indian", "mixed"][cuisine_idx - 1]

    raw_allergies = ask("Allergies — comma-separated, or Enter for none", default="none")
    if raw_allergies.lower() == "none":
        allergies = []
        print(f"  {ok('No allergies')}")
    else:
        allergies = [a.strip() for a in raw_allergies.split(",") if a.strip()]
        print(f"  {ok('Avoiding: ' + ', '.join(allergies))}")

    return {
        "cuisine": cuisine,
        "nutrition_priority": ["protein", "fiber"],
        "allergies": allergies,
    }


def collect_schedule(timezone: str) -> dict:
    section("Schedule")
    print(f"  {dim('Recipes are sent the evening before so you can plan ahead.')}\n")

    while True:
        raw = ask("Delivery time (HH:MM, 24h)", default="20:00")
        match = re.match(r"^(\d{1,2}):(\d{2})$", raw)
        if match:
            hour, minute = int(match.group(1)), int(match.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                ampm = "AM" if hour < 12 else "PM"
                display_hour = hour % 12 or 12
                print(f"  {ok(f'Recipes at {display_hour}:{minute:02d} {ampm} ({timezone})')}")
                break
        print(f"  {red('Use 24h format — e.g. 20:00 for 8 PM, 07:30 for 7:30 AM.')}")

    day_idx = choose(
        "Pantry suggestions day",
        ["Monday", "Tuesday", "Wednesday", "Thursday",
         "Friday", "Saturday", "Sunday", "None (disable)"],
        default=5,
    )
    if day_idx == 8:
        pantry_day = "none"
        print(f"  {dim('Pantry suggestions disabled.')}")
    else:
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        pantry_day = days[day_idx - 1]
        print(f"  {ok('Pantry tips every ' + pantry_day.title())}")

    return {"send_hour": hour, "send_minute": minute, "pantry_suggestions_day": pantry_day}


def setup_pantry() -> None:
    section("Pantry")
    print(f"  {dim('The bot only suggests recipes using ingredients you have.')}")
    print(f"  {dim('A default pantry is included — edit pantry.txt anytime.')}\n")

    choice = choose(
        "Open pantry.txt in your editor now?",
        ["No, use the default (edit later)",
         "Yes, open now"],
        default=1,
    )

    if choice == 2:
        pantry_path = SCRIPT_DIR / "pantry.txt"
        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", ""))
        if editor:
            print(f"  Opening in {editor}. Save and close when done.\n")
            subprocess.run([editor, str(pantry_path)])
        else:
            print(f"  {yellow('No $EDITOR set.')} Edit pantry.txt manually after setup.")
    else:
        print(f"  {dim('Using default pantry.')}")


# ── File Writers ──────────────────────────────────────────────

def write_config_toml(child: dict, location: dict, preferences: dict, schedule: dict) -> None:
    allergies_str = ", ".join(f'"{a}"' for a in preferences["allergies"])
    priorities_str = ", ".join(f'"{p}"' for p in preferences["nutrition_priority"])

    content = f"""# tiny-bites — edit these settings, then commit and push.
# To re-run guided setup: python setup_bot.py

[child]
name     = "{child['name']}"
birthday = "{child['birthday']}"  # YYYY-MM-DD; age is auto-calculated

[location]
city     = "{location['city']}"
timezone = "{location['timezone']}"  # IANA format — controls delivery time

[preferences]
cuisine            = "{preferences['cuisine']}"  # western | indian | mixed
nutrition_priority = [{priorities_str}]
allergies          = [{allergies_str}]                  # e.g. ["peanuts", "dairy"]

[schedule]
send_hour              = {schedule['send_hour']}        # 20 = 8 PM; recipes arrive the evening before
send_minute            = {schedule['send_minute']}
pantry_suggestions_day = "{schedule['pantry_suggestions_day']}"  # monday-sunday, or "none" to disable
"""

    path = SCRIPT_DIR / "config.toml"
    path.write_text(content)
    print(f"  {ok('config.toml')}")


def write_workflow(schedule: dict, timezone: str) -> None:
    cron = compute_utc_cron(schedule["send_hour"], schedule["send_minute"], timezone)
    ampm = "AM" if schedule["send_hour"] < 12 else "PM"
    display_hour = schedule["send_hour"] % 12 or 12
    local_time = f"{display_hour}:{schedule['send_minute']:02d} {ampm}"

    content = f"""# ============================================================
# tiny-bites — Daily Schedule
# ============================================================
# This workflow runs once a day to generate a breakfast recipe
# and send it to your Telegram.
#
# The cron below is in UTC. It was calculated from your config:
#   Local time: {local_time} ({timezone})
#   UTC cron:   {cron}
#
# After a daylight saving change, recalculate with:
#   python setup_bot.py --update-schedule
# ============================================================

name: Daily Baby Breakfast

on:
  schedule:
    - cron: "{cron}"
  workflow_dispatch: # allows manual trigger from GitHub UI

jobs:
  send-breakfast:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Send breakfast recipe
        env:
          ANTHROPIC_API_KEY: ${{{{ secrets.ANTHROPIC_API_KEY }}}}
          TELEGRAM_BOT_TOKEN: ${{{{ secrets.TELEGRAM_BOT_TOKEN }}}}
          TELEGRAM_CHAT_ID: ${{{{ secrets.TELEGRAM_CHAT_ID }}}}
        run: python send_breakfast.py

      - name: Commit updated recipe log
        run: |
          git config user.name "breakfast-bot"
          git config user.email "bot@noreply.github.com"
          git add recipe_log.json
          git diff --staged --quiet || git commit -m "log: $(date +%Y-%m-%d)"
          git push
"""

    workflow_dir = SCRIPT_DIR / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    path = workflow_dir / "daily_breakfast.yml"
    path.write_text(content)
    print(f"  {ok('.github/workflows/daily_breakfast.yml')}")


# ── GitHub Secrets ────────────────────────────────────────────

def setup_github_secrets(anthropic_key: str, telegram_token: str, telegram_chat_id: str) -> None:
    section("GitHub Secrets")
    print(f"  {dim('Saving credentials as repo secrets so GitHub Actions can use them.')}\n")

    gh = shutil.which("gh")
    if not gh:
        print(f"  {yellow('gh CLI not available.')} Add these three secrets manually:\n")
        print(f"    Repo → Settings → Secrets and variables → Actions → New repository secret\n")
        print(f"    {bold('ANTHROPIC_API_KEY')}   your Anthropic key")
        print(f"    {bold('TELEGRAM_BOT_TOKEN')}  {dim(telegram_token)}")
        print(f"    {bold('TELEGRAM_CHAT_ID')}    {dim(telegram_chat_id)}")
        input(f"\n  {dim('Press Enter to continue')}  ")
        return

    result = subprocess.run([gh, "auth", "status"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  {yellow('gh CLI not authenticated.')} Add these three secrets manually:\n")
        print(f"    Repo → Settings → Secrets and variables → Actions → New repository secret\n")
        print(f"    {bold('ANTHROPIC_API_KEY')}   your Anthropic key")
        print(f"    {bold('TELEGRAM_BOT_TOKEN')}  {dim(telegram_token)}")
        print(f"    {bold('TELEGRAM_CHAT_ID')}    {dim(telegram_chat_id)}")
        input(f"\n  {dim('Press Enter to continue')}  ")
        return

    choice = choose(
        "Set secrets via gh CLI now?",
        ["Yes", "No, I'll do it manually"],
        default=1,
    )
    if choice == 2:
        print(f"  {dim('Add them in Settings → Secrets → Actions when ready.')}")
        return

    print()
    for name, value in [
        ("ANTHROPIC_API_KEY",  anthropic_key),
        ("TELEGRAM_BOT_TOKEN", telegram_token),
        ("TELEGRAM_CHAT_ID",   telegram_chat_id),
    ]:
        result = subprocess.run(
            [gh, "secret", "set", name, "--body", value],
            capture_output=True, text=True,
        )
        print(f"  {ok(name + ' saved') if result.returncode == 0 else err('Failed to save ' + name)}")


# ── Update Schedule ───────────────────────────────────────────

def update_schedule() -> None:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib

    config_path = SCRIPT_DIR / "config.toml"
    if not config_path.exists():
        print(f"{red('Error:')} config.toml not found. Run 'python setup_bot.py' first.")
        sys.exit(1)

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    tz = config["location"]["timezone"]
    schedule = config["schedule"]
    old_cron = ""

    workflow_path = SCRIPT_DIR / ".github" / "workflows" / "daily_breakfast.yml"
    if workflow_path.exists():
        for line in workflow_path.read_text().splitlines():
            if "cron:" in line:
                match = re.search(r'"(.+)"', line)
                if match:
                    old_cron = match.group(1)
                break

    write_workflow(schedule, tz)
    new_cron = compute_utc_cron(schedule["send_hour"], schedule["send_minute"], tz)

    if old_cron:
        print(f"  Previous  {dim(old_cron)}")
    print(f"  New       {bold(new_cron)}")
    print(f"  Timezone  {tz}")
    cmd = 'git add -A && git commit -m "Update schedule" && git push'
    print(f"\n  {dim('Commit and push to apply: ' + cmd)}")


# ── Main ──────────────────────────────────────────────────────

def main() -> None:
    if sys.version_info < (3, 9):
        print(f"{red('Error:')} Python 3.9+ required (you have {sys.version_info.major}.{sys.version_info.minor}).")
        sys.exit(1)

    print()
    print(f"  {cyan(bold('tiny-bites'))}")
    print(f"  {dim('Daily AI-generated breakfast recipes, delivered to Telegram.')}")
    print(f"  {dim('This setup takes about 5 minutes.')}\n")
    print(f"  {bold('What we will cover:')}")
    print(f"    1  {dim('─')}  {bold('Prerequisites')}  GitHub CLI, Anthropic API key, Telegram bot")
    print(f"    2  {dim('─')}  {bold('Your child')}      Name, birthday, food preferences")
    print(f"    3  {dim('─')}  {bold('Schedule')}        When to send, pantry reminder day")
    print(f"    4  {dim('─')}  {bold('Go live')}         Save config, push secrets, send a test\n")
    print(f"  {dim('Press Enter at any prompt to accept the default shown in (parentheses).')}")

    prereqs     = collect_prerequisites()
    child       = collect_child_info()
    location    = collect_location()
    preferences = collect_preferences()
    schedule    = collect_schedule(location["timezone"])
    setup_pantry()

    section("Writing config")
    write_config_toml(child, location, preferences, schedule)
    write_workflow(schedule, location["timezone"])

    # ── Summary ──
    ampm = "AM" if schedule["send_hour"] < 12 else "PM"
    display_hour = schedule["send_hour"] % 12 or 12
    local_time = f"{display_hour}:{schedule['send_minute']:02d} {ampm}"
    summary = f"{child['name']} · {location['city']} · {preferences['cuisine']} · {local_time} daily"
    if preferences["allergies"]:
        summary += f" · avoiding {', '.join(preferences['allergies'])}"

    # ── Step 1: local test ──
    section("Test")
    print(f"  {bold(summary)}\n")
    print(f"  {dim('Before going live, confirm it works by sending a real recipe to your Telegram.')}\n")
    input(f"  {dim('Press Enter to run the test')}  ")

    print()
    env = os.environ.copy()
    env["ANTHROPIC_API_KEY"]  = prereqs["anthropic_key"]
    env["TELEGRAM_BOT_TOKEN"] = prereqs["telegram_token"]
    env["TELEGRAM_CHAT_ID"]   = prereqs["telegram_chat_id"]
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "send_breakfast.py")],
        env=env, cwd=SCRIPT_DIR,
    )
    test_passed = result.returncode == 0

    if test_passed:
        print(f"\n  {ok('Recipe sent — check your Telegram!')}")
    else:
        print(f"\n  {err('send_breakfast.py exited with an error.')}")
        print(f"  {dim('Check the output above, fix the issue, and re-run setup.')}")

    # ── Step 2: GitHub secrets + push ──
    section("Push to GitHub")
    gh = shutil.which("gh")

    if test_passed:
        setup_github_secrets(
            anthropic_key=prereqs["anthropic_key"],
            telegram_token=prereqs["telegram_token"],
            telegram_chat_id=prereqs["telegram_chat_id"],
        )

    if test_passed:
        print(f"  {dim('Secrets saved. Push to go live — GitHub Actions will run the bot on schedule.')}\n")
    else:
        print(f"  {yellow('Test did not pass.')} Fix the issue and re-run setup,")
        print(f"  or push anyway and debug using the GitHub Actions logs.")
        print(f"  {dim('Note: GitHub secrets will need to be set manually if you push now.')}\n")

    options_meta = [
        ("Commit and push", "push",
         "Saves your config to GitHub. The bot will start sending recipes on the cron schedule."),
    ]
    if gh:
        options_meta.append((
            "Commit, push, and trigger a GitHub Actions test", "push_test",
            "Same as above, and immediately fires a one-time run so you can verify it works end-to-end in Actions.",
        ))
    options_meta.append((
        "I'll handle it manually", "manual",
        "Exit now — run git add/commit/push yourself when you're ready.",
    ))

    print(f"  {bold('What next?')}")
    for i, (label, _, description) in enumerate(options_meta, 1):
        default_tag = dim("  ← default") if i == 1 else ""
        print(f"\n    {dim(str(i) + ')')} {label}{default_tag}")
        print(f"       {dim(description)}")
    print()

    while True:
        raw = input(f"  {dim('›')} [1]: ").strip()
        if not raw:
            action = options_meta[0][1]
            break
        if raw.isdigit() and 1 <= int(raw) <= len(options_meta):
            action = options_meta[int(raw) - 1][1]
            break
        print(f"  {red('Enter a number 1–' + str(len(options_meta)) + '.')}")

    if action in ("push", "push_test"):
        print()
        subprocess.run(["git", "add", "-A"], cwd=SCRIPT_DIR)
        result = subprocess.run(
            ["git", "commit", "-m", "Configure breakfast bot"],
            cwd=SCRIPT_DIR, capture_output=True, text=True,
        )
        print(f"  {ok('Committed') if result.returncode == 0 else err('Commit failed: ' + result.stderr.strip())}")

        result = subprocess.run(["git", "push"], cwd=SCRIPT_DIR, capture_output=True, text=True)
        pushed = result.returncode == 0
        print(f"  {ok('Pushed') if pushed else err('Push failed: ' + result.stderr.strip())}")

        if action == "push_test" and gh and pushed:
            result = subprocess.run(
                [gh, "workflow", "run", "daily_breakfast.yml"],
                capture_output=True, text=True, cwd=SCRIPT_DIR,
            )
            print(f"  {ok('Workflow triggered — check Telegram in ~1 minute') if result.returncode == 0 else err('Could not trigger: ' + result.stderr.strip())}")

    else:
        print()
        print(f"  {dim('To go live:')}")
        print(f"    git add -A && git commit -m 'Configure breakfast bot' && git push")
        if gh:
            print(f"\n  {dim('To trigger a test run:')}")
            print(f"    gh workflow run daily_breakfast.yml")

    print()


if __name__ == "__main__":
    if "--update-schedule" in sys.argv:
        update_schedule()
    else:
        main()
