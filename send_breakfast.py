#!/usr/bin/env python3
"""
Baby Breakfast Bot
Generates a daily breakfast recipe and sends it via Telegram.
"""

import json
import os
from datetime import date, timedelta

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import anthropic
import requests


RECIPE_LOG_PATH = os.path.join(os.path.dirname(__file__), "recipe_log.json")
MAX_LOG_SIZE = 7


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "config.toml")
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def child_age_months(config: dict) -> int:
    birthday = date.fromisoformat(config["child"]["birthday"])
    today = date.today()
    return (today.year - birthday.year) * 12 + (today.month - birthday.month)


def load_pantry() -> str:
    pantry_path = os.path.join(os.path.dirname(__file__), "pantry.txt")
    with open(pantry_path) as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return "\n".join(lines)


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


def build_system_prompt(config: dict) -> str:
    age = child_age_months(config)
    priorities = config["preferences"]["nutrition_priority"]
    allergies = config["preferences"]["allergies"]
    cuisine = config["preferences"]["cuisine"]

    priority_str = " and ".join(priorities) if priorities else "protein and fiber"

    allergy_rule = ""
    if allergies:
        allergy_list = ", ".join(allergies)
        allergy_rule = f"\n- NEVER use these ingredients (allergies): {allergy_list}."

    if cuisine == "western":
        cuisine_instruction = "Only suggest Western breakfasts (eggs, oats, yogurt bowls, toast-based, etc.). No Indian recipes."
    elif cuisine == "indian":
        cuisine_instruction = "Only suggest Indian breakfasts (poha, upma, idli, chilla, khichdi, etc.). No Western recipes."
    else:
        cuisine_instruction = "Mix it up — rotate between Western and Indian breakfasts across the week."

    return f"""You are a pediatric nutritionist helping a parent feed their {age}-month-old a healthy, wholesome breakfast.

Hard rules:
- ONLY use ingredients from the pantry list provided. No exceptions.
- Recipes must be safe for a {age}-month-old: soft or mashable textures, no honey, no choking hazards (grapes must be quartered, raw carrots are out), low sodium.
- Each recipe must deliver a meaningful amount of {priority_str} — this is the top priority.
- Keep prep under 15 minutes. These are busy parents on a weekday morning.
- No exotic, random, or store-specific ingredients.
- Do NOT repeat any recipe from the "Recent recipes" list provided.{allergy_rule}

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

Tip: [One practical texture or serving tip for a {age}-month-old]
"""


def generate_recipe(config: dict) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    age = child_age_months(config)
    tomorrow = (date.today() + timedelta(days=1)).strftime("%A, %B %d")
    recent = load_recent_recipes()
    recent_block = (
        "Recent recipes (do not repeat these):\n- " + "\n- ".join(recent)
        if recent
        else "No recent recipes yet."
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=build_system_prompt(config),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Give me one breakfast idea for my {age}-month-old for tomorrow, {tomorrow}.\n\n"
                    f"Pantry:\n{load_pantry()}\n\n"
                    f"{recent_block}"
                ),
            }
        ],
    )

    return message.content[0].text.strip()


def build_pantry_prompt(config: dict) -> str:
    age = child_age_months(config)
    city = config["location"]["city"]

    return f"""You are a nutritionist and local food expert helping a parent in {city} find seasonal ingredients for their {age}-month-old's breakfasts.

Suggest ingredients that:
- Are currently in season in the {city} area
- Are NOT on the pantry list provided
- Make excellent, nutritious breakfast options for a {age}-month-old
- Are easy to find at local grocery stores or farmers markets

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


def is_target_day(day_name: str) -> bool:
    days = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }
    return date.today().weekday() == days.get(day_name.lower(), -1)


def generate_pantry_suggestions(config: dict) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today = date.today().strftime("%B %d, %Y")
    city = config["location"]["city"]

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=build_pantry_prompt(config),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Today is {today}. I'm in {city}.\n\n"
                    f"Current pantry (do NOT suggest these):\n{load_pantry()}\n\n"
                    f"What seasonal ingredients should I pick up this weekend for my toddler's breakfasts?"
                ),
            }
        ],
    )

    return message.content[0].text.strip()


def send_telegram(recipe: str, config: dict) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    child_name = config["child"]["name"]
    tomorrow = (date.today() + timedelta(days=1)).strftime("%A, %B %d")
    text = f"Tomorrow's breakfast for {child_name} — {tomorrow}\n\n{recipe}"

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    response.raise_for_status()


def send_pantry_suggestions_telegram(suggestions: str, config: dict) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    city = config["location"]["city"]
    text = f"Weekend Pantry Picks — what's in season in {city} right now\n\n{suggestions}"

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    response.raise_for_status()


if __name__ == "__main__":
    config = load_config()
    recipe = generate_recipe(config)
    name = extract_recipe_name(recipe)
    save_recipe_to_log(name)
    send_telegram(recipe, config)

    suggestions_day = config["schedule"].get("pantry_suggestions_day", "friday")
    if suggestions_day != "none" and is_target_day(suggestions_day):
        suggestions = generate_pantry_suggestions(config)
        send_pantry_suggestions_telegram(suggestions, config)
