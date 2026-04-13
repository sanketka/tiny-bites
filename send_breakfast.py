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
- Mix it up — rotate between Western and Indian breakfasts across the week.
- Indian options are strongly encouraged: poha, upma, soft idli, moong dal chilla, daliya khichdi, rava uttapam, etc.
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

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=SYSTEM_PROMPT,
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
