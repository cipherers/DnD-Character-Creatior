# DnD-Character-Creatior

D&D character randomizer / archive.

## 1. Overview
Small Flask + SQLite app to:
- Register/login users
- Store D&D reference data (Races, Classes, Equipment, Abilities/Skills)
- Create characters with ability scores (including racial bonuses)
- Extend the ruleset by adding new data through an admin-style form

## 2. Tech Stack
- Python / Flask
- Flask-SQLAlchemy
- SQLite (file: site.db)
- HTML (Jinja2 templates), Tailwind CDN
- JavaScript (vanilla fetch for POSTs)

## 3. Core Concepts
| Concept | Description |
|--------|-------------|
| User | Auth + ownership of Characters |
| Race | Stores per-ability bonuses (strength_bonus … charisma_bonus) |
| Class | Stores hit_die (and future class data) |
| Equipment | Weapons / armor basics |
| Skill / Ability | Placeholder for expandable features |
| Character | Rolled stats + applied race bonuses |
| CharacterPortrait uploads| Uploads may reset periodically on free hosting |

## 4. Ability Score Flow
1. Race is created via Add DND Info (type=race) with six numeric bonuses (0–2).
2. When a character is created, base scores are rolled (4d6 drop lowest per ability).
3. Race bonuses are added before final save.
4. Stored fields: strength, dexterity, constitution, intelligence, wisdom, charisma.

## 5. Adding DND Data
Route: POST /add-dnd-info  
Form fields vary by type:
- race: name, description, six *_bonus fields
- class: hit_dice
- ability: ability_type, effect (mapped to Skill model)
- weapon: weapon_type, damage (mapped to Equipment)

Race bonus fields MUST be integers (0–2). Backend casts with int(..., default 0).

## 6. Project Structure (simplified)
```
Back-end/
  app.py          # Flask app + routes
  models.py       # SQLAlchemy models
  fix_db.py       # Helper to patch DB column issues
Front-end/
  index.html      # Character creation (ability scores)
  login.html
  dashboard.html
  add_dnd_info.html
site.db           # SQLite database (generated)
```

## 7. Setup (Windows)
```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt   (create one if missing)
py
>>> from Back-end.app import db, app
>>> with app.app_context(): db.create_all()
```

If models change: delete site.db (dev only) and re-run create_all().

## 8. Running
```
set FLASK_APP=Back-end.app
set FLASK_ENV=development
flask run
```
Navigate: http://127.0.0.1:5000

## 9. Models (key fields)
- Race: name, description, strength_bonus … charisma_bonus (ints)
- Class: name, description, hit_die
- Equipment: name, item_type, damage_dice, damage_type, ac
- Skill: name, description, associated_attribute
- Character: FK to user, race, class + final ability scores

## 10. Important Route (example)
```
POST /add-dnd-info
Body (race):
type=race
name=High Elf
description=Keen senses
strength_bonus=0
dexterity_bonus=2
constitution_bonus=0
intelligence_bonus=1
wisdom_bonus=0
charisma_bonus=0
```
Response: { "message": "DND information added successfully" }

## 11. Common Pitfalls
| Issue | Cause | Fix |
|-------|-------|-----|
| TemplateNotFound | Wrong template_folder | Check app = Flask(..., template_folder='../Front-end') |
| Race bonuses all 0 | Missing form field names | Ensure *_bonus inputs exist |
| No console logs | Script tag empty / not loaded | Verify add_dnd_info.html script section |

## 12. Extending
- Add feats: new model + branch in /add-dnd-info
- Add authentication hardening (Flask-Login)
- Add migrations (Flask-Migrate) for production
- Add test suite (pytest + temp SQLite)

## 13. Testing Ideas
- Create race with mixed bonuses; create character; verify sums.
- Attempt invalid bonus (e.g. 5) → should coerce or reject (add validation).
- Add equipment and ensure no race logic breaks.

## 14. Deployment (Render)
When deploying to Render, ensure the following environment variables are set in the Dashboard:
- `SECRET_KEY`: A long, random string (e.g., generated via `openssl rand -hex 32`).
- `FLASK_ENV`: set to `production`.
- `TURNSTILE_SITE_KEY`: (Optional) Your Cloudflare Turnstile site key.
- `TURNSTILE_SECRET_KEY`: (Optional) Your Cloudflare Turnstile secret key.

## 15. Security Notes (basic)
- `SECRET_KEY` MUST be set in the environment in production.
- `SESSION_COOKIE_SECURE=True` is enabled, requiring HTTPS.
- Rate limiting is active on sensitive endpoints.
- No CSRF protection yet (add Flask-WTF or custom token if needed).
- No password rules enforced (improve).

## 15. Contributing (internal)
1. Create feature branch
2. Keep functions small
3. Avoid hardcoding paths
4. Write docstring for each model change

## 16. Quick Reference (Race Form Fields)
| Field | Name Attribute |
|-------|----------------|
| Strength Bonus | strength_bonus |
| Dexterity Bonus | dexterity_bonus |
| Constitution Bonus | constitution_bonus |
| Intelligence Bonus | intelligence_bonus |
| Wisdom Bonus | wisdom_bonus |
| Charisma Bonus | charisma_bonus |

## 17. Future Improvements
- Export to JSON
- Dice roll history panel
- UI polish (Tailwind components)

## 18. License
Add a license file if public.

---

(History)
(08/11/2025): Creation of necessary files  
(08/11/2025): Start of development
