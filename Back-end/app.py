from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sys
import os

# Ensure the Back-end directory is in the Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from sqlalchemy import text
import random
import json
import io
from flask import send_file
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests

# Make sure all your model definitions are in a file named 'models.py'
from models import db, Character, Race, Class, Background, Skill, Equipment, User, Spell, Feat, Trait


# --- Paths / Uploads ---
UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '../Front-end/static/uploads'
)
UPLOAD_FOLDER = os.path.abspath(UPLOAD_FOLDER)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# --- Flask App / CORS ---
app = Flask(__name__, template_folder='../Front-end', static_folder='../Front-end/static')
app.url_map.strict_slashes = False

IS_DEV = (
    app.debug
    or os.environ.get("ENV") == "dev"
    or os.environ.get("FLASK_ENV") == "development"
)

# IMPORTANT: In production, you should set FRONTEND_ORIGIN in Render:
# FRONTEND_ORIGIN=https://cipherers.github.io
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN")
if not FRONTEND_ORIGIN:
    if IS_DEV:
        FRONTEND_ORIGIN = "*"  # Allow all in development
    else:
        # Fail closed instead of silently allowing the wrong origin
        raise RuntimeError("FRONTEND_ORIGIN environment variable must be set in production!")

CORS(app, supports_credentials=True, origins=[FRONTEND_ORIGIN])


# --- Proxy Support ---
# Tell Flask it's behind a proxy to correctly handle HTTPS and IP addresses.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


# --- Security: Require Cloudflare Worker Proxy Secret ---
# Set this in Render AND as a Secret in Worker settings: PROXY_SECRET
PROXY_SECRET = os.environ.get("PROXY_SECRET")

@app.before_request
def require_proxy_secret():
    """
    Blocks direct calls to Render by requiring the Worker to send X-Proxy-Secret.
    Enable in production only. In dev, we skip this.
    """
    if IS_DEV:
        return None

    # Optional: allow health checks without the secret
    if request.path == "/health":
        return None

    # If you want the root route public, allow it (optional):
    # if request.path == "/":
    #     return None

    if not PROXY_SECRET:
        return jsonify({"error": "Server misconfigured: PROXY_SECRET missing"}), 500

    sent = request.headers.get("X-Proxy-Secret")
    if sent != PROXY_SECRET:
        return jsonify({"error": "Forbidden"}), 403

    return None


# --- Security: Enforce HTTPS ---
@app.before_request
def enforce_https():
    if not app.debug and request.headers.get('X-Forwarded-Proto', 'http') == 'http':
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)


@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'message': 'DnD Character Creator API is up and running'}), 200


# --- Security: Rate Limiting ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)


# --- DB Config ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# --- Security: Secret Key ---
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if IS_DEV:
        SECRET_KEY = "dev_only_change_me_unsecure"
        print("WARNING: Using default SECRET_KEY in development mode.")
    else:
        raise RuntimeError("SECRET_KEY environment variable is not set in production!")

app.config['SECRET_KEY'] = SECRET_KEY
app.config.update(
    SESSION_COOKIE_SECURE=True,     # only over HTTPS
    SESSION_COOKIE_HTTPONLY=True,   # not readable by JS
    SESSION_COOKIE_SAMESITE="None", # for cross-site cookies
)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2MB max upload


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Initialize SQLAlchemy with app
db.init_app(app)


def get_class_skill_map():
    """Return a dict mapping Class.name -> list of allowed Skill IDs."""
    rules = {
        'fighter': ['Athletics', 'Survival', 'Intimidation'],
        'wizard': ['Stealth'],
        'rogue': ['Stealth', 'Acrobatics', 'Deception'],
        'cleric': ['History', 'Insight', 'Medicine'],
        'ranger': ['Survival', 'Nature', 'Perception'],
        'paladin': ['Religion', 'Intimidation', 'Persuasion'],
        'bard': ['Performance', 'Persuasion', 'Deception'],
        'druid': ['Animal Handling', 'Nature', 'Survival'],
        'monk': ['Acrobatics', 'Stealth', 'Athletics'],
        'barbarian': ['Athletics', 'Intimidation', 'Survival'],
        'sorcerer': ['Arcana', 'Deception', 'Persuasion'],
        'warlock': ['Arcana', 'Deception', 'Intimidation'],
        'artificer': ['Arcana', 'History', 'Investigation'],
    }
    skills = {s.name.lower(): s.id for s in Skill.query.all()}
    mapping = {}
    for cls in Class.query.all():
        allowed_names = rules.get(cls.name.lower(), None)
        if allowed_names is None:
            mapping[cls.name] = [s.id for s in Skill.query.all()]
        else:
            mapped_ids = []
            for name in allowed_names:
                skill_id = skills.get(name.lower())
                if skill_id:
                    mapped_ids.append(skill_id)
            mapping[cls.name] = mapped_ids
    return mapping


@app.route('/get-all-equipment')
def get_all_equipment():
    equipment = Equipment.query.all()
    return jsonify([{'id': e.id, 'name': e.name, 'item_type': e.item_type, 'description': e.description} for e in equipment])


@app.route('/add-inventory-item', methods=['POST'])
@limiter.limit("20 per minute")
def add_inventory_item():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    character_id = data.get('character_id')
    item_id = data.get('item_id')

    character = Character.query.get(character_id)
    if not character or character.user_id != session['user_id']:
        return jsonify({'error': 'Character not found or unauthorized'}), 404

    item = Equipment.query.get(item_id)
    if not item:
        return jsonify({'error': 'Item not found'}), 404

    if item in character.inventory:
        return jsonify({'error': 'Item already in inventory'}), 400

    character.inventory.append(item)
    db.session.commit()
    return jsonify({'message': 'Item added successfully'})


@app.route('/remove-inventory-item', methods=['POST'])
@limiter.limit("20 per minute")
def remove_inventory_item():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    character_id = data.get('character_id')
    item_id = data.get('item_id')

    character = Character.query.get(character_id)
    if not character or character.user_id != session['user_id']:
        return jsonify({'error': 'Character not found or unauthorized'}), 404

    item = Equipment.query.get(item_id)
    if not item:
        return jsonify({'error': 'Item not found'}), 404

    if item in character.inventory:
        character.inventory.remove(item)
        db.session.commit()
        return jsonify({'message': 'Item removed successfully'})
    else:
        return jsonify({'error': 'Item not in inventory'}), 400


# --- Database Seeding Function ---
def seed_database():
    """
    Creates all database tables and populates them with sample data if missing.
    Safe: does not change CORS, sessions, cookies, proxy handling, or auth logic.
    """
    with app.app_context():
        db.create_all()

        # --- Schema Migrations (SQLite simple adds) ---
        # This only adds missing columns; it doesn't change security behavior.
        try:
            info = db.session.execute(text("PRAGMA table_info(characters)")).fetchall()
            col_names = [row[1] for row in info]

            if "user_id" not in col_names:
                print("Adding missing 'user_id' column to characters table...")
                db.session.execute(text("ALTER TABLE characters ADD COLUMN user_id INTEGER"))
                db.session.commit()

            if "image_path" not in col_names:
                print("Adding missing 'image_path' column to characters table...")
                db.session.execute(text("ALTER TABLE characters ADD COLUMN image_path TEXT"))
                db.session.commit()

            # You use this in update_character(); ensure it exists to prevent 500s.
            if "last_updated_level" not in col_names:
                print("Adding missing 'last_updated_level' column to characters table...")
                db.session.execute(text("ALTER TABLE characters ADD COLUMN last_updated_level INTEGER"))
                db.session.commit()

        except Exception as e:
            print(f"Migration check skipped or failed: {e}")

        def get_or_create(model, defaults=None, **kwargs):
            instance = model.query.filter_by(**kwargs).first()
            if instance:
                return instance, False

            params = dict(kwargs)
            if defaults:
                params.update(defaults)

            instance = model(**params)
            db.session.add(instance)
            db.session.commit()
            return instance, True

        print("Checking/Seeding database content...")

        # --------------------
        # 1) RACES
        # --------------------
        races_data = [
            {
                "name": "Human",
                "description": "A versatile and ambitious race.",
                "strength_bonus": 1, "dexterity_bonus": 1, "constitution_bonus": 1,
                "intelligence_bonus": 1, "wisdom_bonus": 1, "charisma_bonus": 1
            },
            {"name": "Elf", "description": "Graceful and long-lived.", "dexterity_bonus": 2, "intelligence_bonus": 1},
            {"name": "Dwarf", "description": "Bold and hardy.", "constitution_bonus": 2},
            {"name": "Halfling", "description": "Small and nimble.", "dexterity_bonus": 2},
        ]
        for r in races_data:
            get_or_create(Race, name=r["name"], defaults=r)

        # --------------------
        # 2) CLASSES  ✅ must be here
        # --------------------
        classes_data = [
            {"name": "Fighter", "description": "A master of combat.", "hit_die": 10},
            {"name": "Wizard", "description": "A student of arcane magic.", "hit_die": 6},
            {"name": "Rogue", "description": "A scoundrel who uses stealth and trickery.", "hit_die": 8},
            {"name": "Cleric", "description": "A priestly champion who wields divine magic.", "hit_die": 8},
        ]
        for c in classes_data:
            get_or_create(Class, name=c["name"], defaults=c)

        # --------------------
        # 3) BACKGROUNDS
        # --------------------
        backgrounds_data = [
            {"name": "Acolyte", "description": "Serving a deity and a temple."},
            {"name": "Soldier", "description": "A trained warrior."},
        ]
        for b in backgrounds_data:
            get_or_create(Background, name=b["name"], defaults=b)

        # --------------------
        # 4) SKILLS
        # --------------------
        skills_data = [
            {"name": "Athletics", "associated_attribute": "Strength"},
            {"name": "Acrobatics", "associated_attribute": "Dexterity"},
            {"name": "Stealth", "associated_attribute": "Dexterity"},
            {"name": "Arcana", "associated_attribute": "Intelligence"},
            {"name": "History", "associated_attribute": "Intelligence"},
            {"name": "Investigation", "associated_attribute": "Intelligence"},
            {"name": "Nature", "associated_attribute": "Intelligence"},
            {"name": "Religion", "associated_attribute": "Intelligence"},
            {"name": "Animal Handling", "associated_attribute": "Wisdom"},
            {"name": "Insight", "associated_attribute": "Wisdom"},
            {"name": "Medicine", "associated_attribute": "Wisdom"},
            {"name": "Perception", "associated_attribute": "Wisdom"},
            {"name": "Survival", "associated_attribute": "Wisdom"},
            {"name": "Deception", "associated_attribute": "Charisma"},
            {"name": "Intimidation", "associated_attribute": "Charisma"},
            {"name": "Performance", "associated_attribute": "Charisma"},
            {"name": "Persuasion", "associated_attribute": "Charisma"},
            {"name": "Sleight of Hand", "associated_attribute": "Dexterity"},
        ]
        for s in skills_data:
            get_or_create(Skill, name=s["name"], defaults={"description": "Standard skill", **s})

        # --------------------
        # 5) EQUIPMENT
        # --------------------
        equipment_data = [
            {"name": "LongSword", "item_type": "Weapon", "description": "1d8 slashing damage"},
            {"name": "ShortSword", "item_type": "Weapon", "description": "1d6 piercing damage"},
            {"name": "Dagger", "item_type": "Weapon", "description": "1d4 piercing damage"},
            {"name": "GreatAxe", "item_type": "Weapon", "description": "1d12 slashing damage"},
            {"name": "Shield", "item_type": "Armor", "description": "+2 AC"},
            {"name": "Leather Armor", "item_type": "Armor", "description": "11 + Dex Modifier AC"},
            {"name": "Chain Mail", "item_type": "Armor", "description": "16 AC"},
            {"name": "Potion of Healing", "item_type": "Potion", "description": "Restores 2d4 + 2 HP"},
            {"name": "Rope (50ft)", "item_type": "Adventuring Gear", "description": "Hempen rope."},
            {"name": "Torch", "item_type": "Adventuring Gear", "description": "Provides light for 1 hour."},
        ]
        for e in equipment_data:
            get_or_create(Equipment, name=e["name"], defaults=e)

        # --------------------
        # 6) SPELLS
        # --------------------
        spells_data = [
            {"name": "Fireball", "level": 3, "school": "Evocation", "casting_time": "1 Action", "range_val": "150 ft",
             "components": "V, S, M", "duration": "Instantaneous", "description": "A bright streak flashes..."},
            {"name": "Cure Wounds", "level": 1, "school": "Evocation", "casting_time": "1 Action", "range_val": "Touch",
             "components": "V, S", "duration": "Instantaneous", "description": "Heals 1d8 + Mod."},
            {"name": "Magic Missile", "level": 1, "school": "Evocation", "casting_time": "1 Action", "range_val": "120 ft",
             "components": "V, S", "duration": "Instantaneous", "description": "3 darts of force."},
            {"name": "Shield", "level": 1, "school": "Abjuration", "casting_time": "1 Reaction", "range_val": "Self",
             "components": "V, S", "duration": "1 Round", "description": "+5 AC."},
            {"name": "Healing Word", "level": 1, "school": "Evocation", "casting_time": "1 Bonus Action", "range_val": "60 ft",
             "components": "V", "duration": "Instantaneous", "description": "Heals 1d4 + Mod."},
        ]
        for sp in spells_data:
            get_or_create(Spell, name=sp["name"], defaults=sp)

        # --------------------
        # 7) FEATS
        # --------------------
        feats_data = [
            {"name": "Alert", "description": "+5 Initiative."},
            {"name": "Mobile", "description": "+10 ft Speed."},
            {"name": "Sharpshooter", "description": "No disadvantage at long range. -5 atk/+10 dmg."},
            {"name": "Great Weapon Master", "description": "Bonus attack on crit/kill; -5 atk/+10 dmg option."},
        ]
        for f in feats_data:
            get_or_create(Feat, name=f["name"], defaults=f)

        # --------------------
        # Seed User (optional) - safe; doesn't grant extra perms
        # --------------------
        user, created = get_or_create(User, username="seed_user")
        if created or not getattr(user, "password_hash", None):
            user.set_password("password")
            db.session.commit()

        print("Database seeding check complete.")
