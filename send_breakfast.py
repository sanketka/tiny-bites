#!/usr/bin/env python3
"""
Baby Breakfast Bot
Generates a daily breakfast recipe for a 15-month-old and sends it via Telegram.
"""

import json
import os
from datetime import date, timedelta

import anthropic
import requests


RECIPE_LOG_PATH = os.path.join(os.path.dirname(__file__), "recipe_log.json")
MAX_LOG_SIZE = 7


def load_pantry() -> str:
    pantry_path = os.path.join(os.path.dirname(__file__), "pantry.txt")
    with open(pantry_path) as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return "\n".join(lines)


def load_cuisine_mode() -> str:
    config_path = os.path.join(os.path.dirname(__file__), "config.txt")
    with open(config_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("CUISINE_MODE="):
                return line.split("=", 1)[1].strip().lower()
    return "mixed"


def load_recent_recipes() -> list[str]:
    if not os.path.exists(RECIPE_LOG_PATH):
        return []
    with open(RECIPE_LOG_PATH) as f:
        return json.load(f)


def save_recipe_to_log(recipe_name: str) -> None:
    recent = load_recent_recipes()
    recent.append(recipe_name)
    with open(RECIPE_LOG_PATH, "w") as f:
        json.dump(recent[-MAX_LOG_SIZE:], f, indent=2)


def extract_recipe_name(recipe: str) -> str:
    return recipe.split("\n")[0].strip()


SYSTEM_PROMPT = """You are a pediatric nutritionist helping a parent feed their 15-month-old a healthy, wholesome breakfast.

Hard rules:
- ONLY use ingredients from the pantry list provided. No exceptions.
- Recipes must be safe for a 15-month-old: soft or mashable textures, no honey, no choking hazards (grapes must be quartered, raw carrots are out), low sodium.
- Each recipe must deliver a meaningful amount of protein — this is the top priority, alongside fiber.
- Keep prep under 10 minutes. This is a weekday morning.
- No exotic, random, or store-specific ingredients.
- Do NOT repeat any recipe from the "Recent recipes" list provided.

Recipe style:
- {cuisine_instruction}
- Indian options include: poha, upma, soft idli, moong dal chilla, daliya khichdi, rava uttapam, etc.
- Indian dishes must still hit the protein requirement — add dal, egg, yogurt, or tofu where needed.
- Use ghee for Indian recipes instead of butter where appropriate.

Format your response exactly like this (use plain text, no markdown bold or headers):

[Recipe Name]

Prep: [X] min

Nutrition (estimated for one toddler serving):
- Calories: [X] kcal
- Protein: [X] g
- Carbs: [X] g
- Fiber: [X] g
- Fat: [X] g

Ingredients:
- [ingredient + amount]

Steps:
1. [step]
2. [step]

Tip: [One practical texture or serving tip for a 15-month-old]
"""


def generate_recipe() -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    tomorrow = (date.today() + timedelta(days=1)).strftime("%A, %B %d")
    recent = load_recent_recipes()
    recent_block = (
        "Recent recipes (do not repeat these):\n- " + "\n- ".join(recent)
        if recent
        else "No recent recipes yet."
    )

    cuisine_mode = load_cuisine_mode()
    if cuisine_mode == "western":
        cuisine_instruction = "Only suggest Western breakfasts (eggs, oats, yogurt bowls, toast-based, etc.). No Indian recipes."
    elif cuisine_mode == "indian":
        cuisine_instruction = "Only suggest Indian breakfasts (poha, upma, idli, chilla, khichdi, etc.). No Western recipes."
    else:
        cuisine_instruction = "Mix it up — rotate between Western and Indian breakfasts across the week."

    system = SYSTEM_PROMPT.replace("{cuisine_instruction}", cuisine_instruction)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=system,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Give me one breakfast idea for my 15-month-old for tomorrow, {tomorrow}.\n\n"
                    f"Pantry:\n{load_pantry()}\n\n"
                    f"{recent_block}"
                ),
            }
        ],
    )

    return message.content[0].text.strip()


PANTRY_SUGGESTIONS_PROMPT = """You are a nutritionist and local food expert helping a parent in San Francisco, CA find seasonal ingredients for their 15-month-old's breakfasts.

Suggest ingredients that:
- Are currently in season in the San Francisco Bay Area
- Are NOT on the pantry list provided
- Make excellent, nutritious breakfast options for a 15-month-old
- Are easy to find at local grocery stores or farmers markets in SF

For each suggestion, provide:
- Ingredient name
- Benefit: why it's in season now and what it adds nutritionally
- Try it in: a sample recipe name and one-sentence description

Format each suggestion like this (plain text, no markdown):

[Ingredient Name]
Benefit: [seasonal + nutritional benefit]
Try it in: [Recipe Name] — [one sentence description]

Only suggest what's genuinely in season. Fewer strong picks beats a long list of mediocre ones.
"""


def is_friday() -> bool:
    return date.today().weekday() == 4


def generate_pantry_suggestions() -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today = date.today().strftime("%B %d, %Y")

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=PANTRY_SUGGESTIONS_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Today is {today}. I'm in San Francisco, CA.\n\n"
                    f"Current pantry (do NOT suggest these):\n{load_pantry()}\n\n"
                    f"What seasonal ingredients should I pick up this weekend for my 15-month-old's breakfasts?"
                ),
            }
        ],
    )

    return message.content[0].text.strip()


def send_pantry_suggestions_telegram(suggestions: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    text = f"Weekend Pantry Picks — what's in season in SF right now\n\n{suggestions}"

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    response.raise_for_status()


def send_telegram(recipe: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    tomorrow = (date.today() + timedelta(days=1)).strftime("%A, %B %d")
    text = f"Tomorrow's baby breakfast — {tomorrow}\n\n{recipe}"

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    response.raise_for_status()


if __name__ == "__main__":
    recipe = generate_recipe()
    name = extract_recipe_name(recipe)
    save_recipe_to_log(name)
    send_telegram(recipe)

    if is_friday():
        suggestions = generate_pantry_suggestions()
        send_pantry_suggestions_telegram(suggestions)
