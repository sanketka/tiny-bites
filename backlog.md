# Breakfast Bot — Backlog

## To Do
- [ ] On-demand Telegram commands (/new, /indian, /western) via Cloudflare Worker — removed during public release cleanup, rebuild when needed

## Future
- [ ] Expand into a full meal planner — not just baby breakfast, but adults too. Protein and fiber still the priority. Generalize age, dietary preferences, and meal type (breakfast, lunch, dinner).

## Done
- [x] Daily recipe generation via Claude Haiku
- [x] Telegram delivery at 8 PM PT
- [x] Pantry managed via pantry.txt (no code changes needed)
- [x] Recipe log — tracks last 7 recipes to avoid repeats
- [x] Indian breakfast options supported
- [x] Nutritional breakdown in each message
- [x] Production readiness — config.toml, setup_bot.py onboarding, README, .gitignore, LICENSE
