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
    os.environ.get("ENV") == "dev"
    or os.environ.get("FLASK_ENV") == "development"
    or not os.environ.get("FRONTEND_ORIGIN") # Assume dev if this is missing
)

# IMPORTANT: In production, you should set FRONTEND_ORIGIN in Render:
# FRONTEND_ORIGIN=https://cipherers.github.io
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN")
if not FRONTEND_ORIGIN:
    if IS_DEV:
        FRONTEND_ORIGIN = "http://localhost:5000"  # Default for local dev
    else:
        raise RuntimeError("FRONTEND_ORIGIN environment variable must be set in production!")

CORS(app, supports_credentials=True, origins=[FRONTEND_ORIGIN], 
     allow_headers=["Content-Type", "Authorization", "X-Proxy-Secret"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])


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
# In production on Render, memory:// resets on restart and isn't shared.
# For now, we continue with memory:// as requested, but noted the limitation.
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
    SESSION_COOKIE_HTTPONLY=True,   # not readable by JS
)

if not IS_DEV:
    app.config.update(
        SESSION_COOKIE_SECURE=True,     # only over HTTPS
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


# --- API Routes ---

@app.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    user = User.query.filter_by(username=username).first()
    
    # Simple auto-register if user doesn't exist (as per frontend hint)
    if not user:
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    
    if user.check_password(password):
        session['user_id'] = user.id
        session.permanent = True
        return jsonify({"message": "Logged in successfully", "user": username}), 200
    
    return jsonify({"error": "Invalid credentials"}), 401


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return jsonify({"message": "Logged out successfully"}), 200


@app.route('/api/check-auth')
def check_auth():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            return jsonify({"logged_in": True, "user": user.username}), 200
    return jsonify({"logged_in": False}), 200


@app.route('/get-races')
def get_races():
    races = Race.query.all()
    return jsonify([{"id": r.id, "name": r.name} for r in races])


@app.route('/get-classes')
def get_classes():
    classes = Class.query.all()
    return jsonify([{"id": c.id, "name": c.name} for c in classes])


@app.route('/get-backgrounds')
def get_backgrounds():
    backgrounds = Background.query.all()
    return jsonify([{"id": b.id, "name": b.name} for b in backgrounds])


@app.route('/get-feats')
def get_feats():
    feats = Feat.query.all()
    return jsonify([{"id": f.id, "name": f.name} for f in feats])


@app.route('/get-spells')
def get_spells():
    spells = Spell.query.all()
    return jsonify([{"id": s.id, "name": s.name} for s in spells])


@app.route('/get-class-details/<int:class_id>')
def get_class_details(class_id):
    cls = Class.query.get_or_404(class_id)
    # This is a bit simplified, usually you'd have a mapping table
    # For now, we fetch all skills/equip just to populate the UI as seen in frontend
    skills = Skill.query.all()
    equipment = Equipment.query.all()
    return jsonify({
        "id": cls.id,
        "name": cls.name,
        "skills": [{"id": s.id, "name": s.name} for s in skills],
        "equipment": [{"id": e.id, "name": e.name} for e in equipment]
    })


@app.route('/create-character', methods=['POST'])
@limiter.limit("5 per minute")
def create_character():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.form
    user = User.query.get(session['user_id'])
    
    race = Race.query.get(data.get('race'))
    char_class = Class.query.get(data.get('class'))
    background = Background.query.get(data.get('background'))
    
    if not race or not char_class:
        return jsonify({"error": "Invalid race or class"}), 400

    # Basic char creation
    new_char = Character(
        name=data.get('name'),
        age=int(data.get('age', 0)),
        alignment=data.get('alignment'),
        hp=10, # default/starting
        strength=int(data.get('strength', 10)),
        dexterity=int(data.get('dexterity', 10)),
        constitution=int(data.get('constitution', 10)),
        intelligence=int(data.get('intelligence', 10)),
        wisdom=int(data.get('wisdom', 10)),
        charisma=int(data.get('charisma', 10)),
        race=race,
        character_class=char_class,
        level=int(data.get('level', 1)),
        background=background,
        user=user
    )

    if data.get('roll_scores') == 'true':
        new_char.roll_ability_scores()

    # Handle skills/equipment if provided (comma separated or multi-form)
    skill_ids = request.form.getlist('skills')
    for sid in skill_ids:
        s = Skill.query.get(sid)
        if s: new_char.proficiencies.append(s)
        
    equip_ids = request.form.getlist('equipment')
    for eid in equip_ids:
        e = Equipment.query.get(eid)
        if e: new_char.inventory.append(e)

    db.session.add(new_char)
    db.session.commit()
    
    return jsonify({"message": "Character created", "id": new_char.id}), 201


@app.route('/api/dashboard')
def dashboard():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = User.query.get(session['user_id'])
    chars = [{
        "id": c.id,
        "name": c.name,
        "race": c.race.name,
        "class": c.character_class.name,
        "level": c.level,
        "image_path": c.image_path
    } for c in user.characters]
    
    return jsonify({"characters": chars})


@app.route('/api/get-character/<int:char_id>')
def get_character(char_id):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    char = Character.query.get_or_404(char_id)
    if char.user_id != session['user_id']:
        return jsonify({"error": "Forbidden"}), 403
    
    return jsonify({
        "id": char.id,
        "name": char.name,
        "age": char.age,
        "level": char.level,
        "alignment": char.alignment,
        "race": char.race.name,
        "class": char.character_class.name,
        "background": char.background.name if char.background else "None",
        "strength": char.strength,
        "dexterity": char.dexterity,
        "constitution": char.constitution,
        "intelligence": char.intelligence,
        "wisdom": char.wisdom,
        "charisma": char.charisma,
        "image_path": char.image_path,
        "gold_pieces": char.gold_pieces,
        "silver_pieces": char.silver_pieces,
        "copper_pieces": char.copper_pieces,
        "skills": [s.id for s in char.proficiencies],
        "inventory": [{"id": i.id, "name": i.name} for i in char.inventory],
        "available_skills": [{"id": s.id, "name": s.name} for s in Skill.query.all()]
    })


@app.route('/api/delete-character/<int:char_id>', methods=['DELETE'])
def delete_character(char_id):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    char = Character.query.get_or_404(char_id)
    if char.user_id != session['user_id']:
        return jsonify({"error": "Forbidden"}), 403
    
    db.session.delete(char)
    db.session.commit()
    return jsonify({"message": "Character deleted"}), 200


@app.route('/update-character-currency', methods=['POST'])
def update_currency():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    char = Character.query.get_or_404(data.get('character_id'))
    if char.user_id != session['user_id']:
        return jsonify({"error": "Forbidden"}), 403
    
    ctype = data.get('currency_type')
    val = data.get('value', 0)
    
    if ctype == 'gold_pieces': char.gold_pieces = val
    elif ctype == 'silver_pieces': char.silver_pieces = val
    elif ctype == 'copper_pieces': char.copper_pieces = val
    
    db.session.commit()
    return jsonify({"message": "Currency updated"}), 200


@app.route('/add-dnd-info', methods=['POST'])
@limiter.limit("5 per minute")
def add_dnd_info():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.form
    itype = data.get('type')
    name = data.get('name')
    desc = data.get('description')

    if itype == 'race':
        new_item = Race(
            name=name, description=desc,
            strength_bonus=int(data.get('strength_bonus', 0)),
            dexterity_bonus=int(data.get('dexterity_bonus', 0)),
            constitution_bonus=int(data.get('constitution_bonus', 0)),
            intelligence_bonus=int(data.get('intelligence_bonus', 0)),
            wisdom_bonus=int(data.get('wisdom_bonus', 0)),
            charisma_bonus=int(data.get('charisma_bonus', 0))
        )
    elif itype == 'class':
        new_item = Class(name=name, description=desc, hit_die=int(data.get('hit_die', 8)))
    elif itype == 'background':
        new_item = Background(name=name, description=desc)
    elif itype == 'ability':
        new_item = Skill(name=name, description=desc, associated_attribute=data.get('associated_attribute'))
    elif itype == 'equipment':
        new_item = Equipment(
            name=name, description=desc, item_type=data.get('item_type'),
            damage_dice=data.get('damage_dice'), damage_type=data.get('damage_type'),
            ac=int(data.get('ac', 0)) if data.get('ac') else None
        )
    else:
        return jsonify({"error": "Invalid type"}), 400

    db.session.add(new_item)
    db.session.commit()
    return jsonify({"message": f"Added {name} to {itype}"}), 201


@app.route('/download-character-pdf/<int:char_id>')
def download_character_pdf(char_id):
    char = Character.query.get_or_404(char_id)
    # Basic PDF generation logic
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.drawString(100, 750, f"Character Sheet: {char.name}")
    p.drawString(100, 730, f"Race: {char.race.name} | Class: {char.character_class.name} | Level: {char.level}")
    p.drawString(100, 710, f"STR: {char.strength} | DEX: {char.dexterity} | CON: {char.constitution}")
    p.drawString(100, 690, f"INT: {char.intelligence} | WIS: {char.wisdom} | CHA: {char.charisma}")
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"{char.name}.pdf", mimetype='application/pdf')


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


if __name__ == "__main__":
    seed_database()
    # In development, we run on port 5000 as requested.
    app.run(host="0.0.0.0", port=5000, debug=True)
