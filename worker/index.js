/**
 * Baby Breakfast Bot — Cloudflare Worker
 * Handles Telegram commands: /new, /indian, /western
 */

const PANTRY = `
Proteins: Eggs, Yogurt, Cottage Cheese, Almond Butter / Peanut Butter, Tofu, Moong Dal, Chana Dal, Toor Dal
Carbs: Whole Wheat Bread, Rolled Oats, Poha (flattened rice), Semolina (rava/sooji), Idli/Dosa batter (store-bought), Broken Wheat (daliya)
Produce: Seasonal fruits, Berries (blueberries, strawberries, raspberries), Avocado, Spinach, Carrots, Sweet Potato, Tomatoes, Peas (frozen)
Dairy: A2 Whole Milk, Butter, Ghee
Pantry Staples: Olive Oil, Maple Syrup, Cinnamon, Vanilla Extract, Turmeric, Cumin Seeds, Mustard Seeds, Hing (asafoetida), Curry Leaves
`.trim();

const SYSTEM_PROMPT = `You are a pediatric nutritionist helping a parent feed their 15-month-old a healthy, wholesome breakfast.

Hard rules:
- ONLY use ingredients from the pantry list provided. No exceptions.
- Recipes must be safe for a 15-month-old: soft or mashable textures, no honey, no choking hazards (grapes must be quartered, raw carrots are out), low sodium.
- Each recipe must deliver a meaningful amount of protein — this is the top priority, alongside fiber.
- Keep prep under 10 minutes. This is a weekday morning.
- No exotic, random, or store-specific ingredients.

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

Tip: [One practical texture or serving tip for a 15-month-old]`;


async function generateRecipe(apiKey, cuisine) {
  const cuisineInstruction = cuisine
    ? `Give me one ${cuisine} breakfast idea for my 15-month-old.`
    : "Give me one breakfast idea for my 15-month-old.";

  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 600,
      system: SYSTEM_PROMPT,
      messages: [
        {
          role: "user",
          content: `${cuisineInstruction}\n\nPantry:\n${PANTRY}`,
        },
      ],
    }),
  });

  if (!response.ok) {
    throw new Error(`Claude API error: ${response.status}`);
  }

  const data = await response.json();
  return data.content[0].text.trim();
}


async function sendTelegram(token, chatId, text) {
  const response = await fetch(
    `https://api.telegram.org/bot${token}/sendMessage`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text }),
    }
  );

  if (!response.ok) {
    throw new Error(`Telegram API error: ${response.status}`);
  }
}


export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("Baby Breakfast Bot is running.", { status: 200 });
    }

    let update;
    try {
      update = await request.json();
    } catch {
      return new Response("Bad request", { status: 400 });
    }

    const message = update?.message;
    if (!message?.text) {
      return new Response("OK", { status: 200 });
    }

    const text = message.text.toLowerCase().trim();
    const chatId = message.chat.id;

    let cuisine = null;
    let shouldRespond = false;

    if (text === "/new") {
      shouldRespond = true;
    } else if (text === "/indian") {
      cuisine = "Indian";
      shouldRespond = true;
    } else if (text === "/western") {
      cuisine = "Western";
      shouldRespond = true;
    }

    if (!shouldRespond) {
      return new Response("OK", { status: 200 });
    }

    try {
      await sendTelegram(
        env.TELEGRAM_BOT_TOKEN,
        chatId,
        "Generating recipe..."
      );

      const recipe = await generateRecipe(env.ANTHROPIC_API_KEY, cuisine);
      await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, recipe);
    } catch (err) {
      await sendTelegram(
        env.TELEGRAM_BOT_TOKEN,
        chatId,
        "Something went wrong. Try again."
      );
    }

    return new Response("OK", { status: 200 });
  },
};
