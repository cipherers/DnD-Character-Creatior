from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import random
from flask import session

# Make sure all your model definitions are in a file named 'models.py'
# and import them here.
from models import db, Character, Race, Class, Background, Skill, Equipment, User
import json
import io
from flask import send_file
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# --- Flask Application Setup ---
# The template_folder is set to 'Front-end' to find index.html
app = Flask(__name__, template_folder='../Front-end')
# Configure the SQLite database. This will create a file called 'site.db'
# in the same directory as this script.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'a_very_secret_key' # Needed for flash messages and sessions

# Initialize the SQLAlchemy object with the Flask app
db.init_app(app)


def get_class_skill_map():
    """Return a dict mapping Class.name -> list of allowed Skill names.

    Uses a small rule set: Fighter -> Athletics, Stealth; Wizard -> Stealth; other classes -> all skills.
    """
    # Define rules by class name (case-insensitive)
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
            # If no specific rules, allow all skills
            mapping[cls.name] = [s.id for s in Skill.query.all()]
        else:
            # Map only the allowed skills
            mapping[cls.name] = [skills[name.lower()] for name in allowed_names if name.lower() in skills]
    return mapping

# --- Database Seeding Function ---
def seed_database():
    """
    Creates all database tables and populates them with sample data.
    This function should be run only once to initialize the database.
    """
    with app.app_context():
        # Create all the tables defined by the models
        db.create_all()

        # Ensure the characters table has the new 'user_id' column (migration for older DBs)
        try:
            info = db.session.execute("PRAGMA table_info(characters)").fetchall()
            col_names = [row[1] for row in info]
            if 'user_id' not in col_names:
                print("Adding missing 'user_id' column to characters table...")
                db.session.execute("ALTER TABLE characters ADD COLUMN user_id INTEGER")
                db.session.commit()
        except Exception as e:
            # If the characters table doesn't exist yet or pragma fails, ignore and continue
            print(f"Migration check skipped or failed: {e}")

        # Check if tables are already populated to prevent duplicates
        if Race.query.first():
            print("Database already seeded. Skipping...")
            return

        print("Seeding database with sample data...")

        # 1. Add some initial data for the foreign key tables
        human = Race(name='Human', description='A versatile and ambitious race.', strength_bonus=1, dexterity_bonus=1, constitution_bonus=1, intelligence_bonus=1, wisdom_bonus=1, charisma_bonus=1)
        elf = Race(name='Elf', description='Graceful and long-lived.', dexterity_bonus=2, intelligence_bonus=1)
        
        class_fighter = Class(name='Fighter', description='A master of combat.', hit_die=10)
        class_wizard = Class(name='Wizard', description='A student of arcane magic.', hit_die=6)

        background_acolyte = Background(name='Acolyte', description='Serving a deity and a temple.')
        
        skill_athletics = Skill(name='Athletics', description='Physical prowess and strength.', associated_attribute='strength')
        skill_stealth = Skill(name='Stealth', description='Hiding and moving quietly.', associated_attribute='dexterity')
        
        equipment_sword = Equipment(name='LongSword', description='A classic one-handed sword.', item_type='Weapon', damage_dice='1d8', damage_type='Slashing')
        equipment_shield = Equipment(name='Shield', description='Provides protection.', item_type='Armor', ac=2)

        db.session.add_all([
            human, elf,
            class_fighter, class_wizard,
            background_acolyte,
            skill_athletics, skill_stealth,
            equipment_sword, equipment_shield
        ])
        # Example debug: print the latest Race entry (remove or change as needed)
        latest = db.session.query(Character).order_by(Character.id.desc()).first()
        if latest:
            print(latest.id)
        db.session.commit()

        # Ensure at least one user exists for foreign key user_id
        from models import User as UserModel
        seed_user = User.query.first()
        if not seed_user:
            seed_user = User(username='seed_user')
            seed_user.set_password('password')
            db.session.add(seed_user)
            db.session.commit()

        # 2. Create a new Character and link it to the seeded data
        main_character = Character(
            name='Arthur',
            age=25,
            alignment='Lawful Good',
            hp=15,
            strength=15,
            dexterity=12,
            constitution=14,
            intelligence=10,
            wisdom=11,
            charisma=13,
            race=human, # Pass the Race object
            character_class=class_fighter, # Pass the Class object
            background=background_acolyte,
            user=seed_user,
            level = 1
        )

        # 3. Add proficiencies and equipment using the relationships
        main_character.proficiencies.append(skill_athletics)
        main_character.inventory.append(equipment_sword)
        main_character.inventory.append(equipment_shield)

        db.session.add(main_character)
        db.session.commit()

        print("Database seeding complete!")
        print(f"Created character: {main_character.name} (ID: {main_character.id})")


# --- Authentication ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        elif not user:
            # Register new user
            if not username or not password:
                flash('Username and password required.')
                return render_template('login.html')
            new_user = User(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            session['user_id'] = new_user.id
            flash('Account created and logged in!')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out.')
    return redirect(url_for('login'))

# --- Flask Routes ---

# --- Dashboard ---
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in to access the dashboard.')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    characters = Character.query.filter_by(user_id=user.id).all()
    total = len(characters)  # Calculate the total number of characters
    per_page = 10  # Define the number of characters per page

    return render_template('dashboard.html', characters=characters, total=total, per_page=per_page)

@app.route('/create-character', methods=['GET', 'POST'])
def create_character():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'GET':
        races = Race.query.all()
        classes = Class.query.all()
        backgrounds = Background.query.all()
        skills = Skill.query.all()
        class_skill_map = get_class_skill_map()
        return render_template('index.html', races=races, classes=classes, backgrounds=backgrounds, skills=skills, class_skill_map=class_skill_map)

    # POST handling
    user = User.query.get(session['user_id'])
    character_name = request.form.get('name')
    character_age = request.form.get('age')
    race_id = request.form.get('race')
    character_class_id = request.form.get('class')
    character_level = request.form.get('level', 1)
    alignment = request.form.get('alignment', 'Neutral')
    hp = request.form.get('hp', 10)
    
    # Get currency values from form
    copper_pieces = request.form.get('copper_pieces', 0)
    silver_pieces = request.form.get('silver_pieces', 0)
    gold_pieces = request.form.get('gold_pieces', 0)
    electrum_pieces = request.form.get('electrum_pieces', 0)
    platinum_pieces = request.form.get('platinum_pieces', 0)

    selected_race = Race.query.get(race_id)
    selected_class = Class.query.get(character_class_id)
    background_id = request.form.get('background')
    selected_background = Background.query.get(background_id)

    if not selected_race or not selected_class:
        flash('Race and Class are required.')
        return redirect(url_for('create_character'))

    try:
        lvl = int(character_level)
        age_val = int(character_age) if character_age else 1
    except ValueError:
        flash('Invalid level or age.')
        return redirect(url_for('create_character'))

    try:
        copper = int(copper_pieces)
        silver = int(silver_pieces)
        gold = int(gold_pieces)
        electrum = int(electrum_pieces)
        platinum = int(platinum_pieces)
    except ValueError:
        flash('Invalid currency values.')
        return redirect(url_for('create_character'))

    new_character = Character(
        name=character_name,
        age=age_val,
        alignment=alignment,
        hp=hp,
        strength=0,
        dexterity=0,
        constitution=0,
        intelligence=0,
        wisdom=0,
        charisma=0,
        race=selected_race,
        character_class=selected_class,
        background=selected_background,
        user=user,
        level=lvl,
        copper_pieces=copper,
        silver_pieces=silver,
        gold_pieces=gold,
        electrum_pieces=electrum,
        platinum_pieces=platinum
    )

    if 'roll_scores' in request.form:
        new_character.roll_ability_scores()
    else:
        try:
            new_character.strength = int(request.form.get('strength', 0))
            new_character.dexterity = int(request.form.get('dexterity', 0))
            new_character.constitution = int(request.form.get('constitution', 0))
            new_character.intelligence = int(request.form.get('intelligence', 0))
            new_character.wisdom = int(request.form.get('wisdom', 0))
            new_character.charisma = int(request.form.get('charisma', 0))
        except ValueError:
            flash('Invalid ability scores.')
            return redirect(url_for('create_character'))

    selected_skill_ids = request.form.getlist('skills')
    selected_skills = Skill.query.filter(Skill.id.in_(selected_skill_ids)).all()
    for skill in selected_skills:
        if skill.id in get_class_skill_map().get(selected_class.id, []):
            new_character.proficiencies.append(skill)

    selected_equipment_ids = request.form.getlist('equipment')
    selected_equipment = Equipment.query.filter(Equipment.id.in_(selected_equipment_ids)).all()
    new_character.inventory.extend(selected_equipment)

    db.session.add(new_character)
    db.session.commit()

    flash(f"Character '{new_character.name}' created successfully!")
    return redirect(url_for('dashboard'))

@app.route('/delete-character/<int:char_id>', methods=['POST'])
def delete_character(char_id):
    if 'user_id' not in session:
        flash('You must be logged in to delete characters.')
        return redirect(url_for('login'))
    char = Character.query.get(char_id)
    if not char:
        flash('Character not found.')
        return redirect(url_for('dashboard'))
    # Ensure user owns this character
    if char.user_id != session.get('user_id'):
        flash('You do not have permission to delete that character.')
        return redirect(url_for('dashboard'))
    db.session.delete(char)
    db.session.commit()
    flash(f"Character '{char.name}' deleted.")
    return redirect(url_for('dashboard'))

@app.route('/get-class-details/<int:class_id>')
def get_class_details(class_id):
    character_class = Class.query.get(class_id)
    if not character_class:
        return jsonify({'error': 'Class not found'}), 404

    # Fetch skills and equipment associated with the class
    class_skill_map = get_class_skill_map()
    allowed_skill_ids = class_skill_map.get(character_class.name, [])
    skills = Skill.query.filter(Skill.id.in_(allowed_skill_ids)).all()

    # Define equipment rules by class name (case-insensitive)
    equipment_rules = {
        'fighter': ['LongSword', 'Shield'],
        'wizard': ['LongSword'],
    }
    allowed_equipment_names = equipment_rules.get(character_class.name.lower(), [])
    equipment = Equipment.query.filter(Equipment.name.in_(allowed_equipment_names)).all()

    return jsonify({
        'skills': [{'id': skill.id, 'name': skill.name} for skill in skills],
        'equipment': [{'id': equip.id, 'name': equip.name} for equip in equipment]
    })

@app.route('/get-races')
def get_races():
    races = Race.query.all()
    return jsonify([{'id': race.id, 'name': race.name} for race in races])

@app.route('/get-classes')
def get_classes():
    classes = Class.query.all()
    return jsonify([{'id': cls.id, 'name': cls.name} for cls in classes])

@app.route('/get-backgrounds')
def get_backgrounds():
    backgrounds = Background.query.all()
    return jsonify([{'id': bg.id, 'name': bg.name} for bg in backgrounds])

@app.route('/get-class-skill-map', methods=['GET'])
def get_class_skill_map_route():
    """API endpoint to fetch the class-to-skill mapping."""
    try:
        class_skill_map = get_class_skill_map()
        return jsonify(class_skill_map)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-character/<int:character_id>', methods=['GET'])
def get_character(character_id):
    character = Character.query.get_or_404(character_id)
    available_skills = Skill.query.all()
    return jsonify({
        'id': character.id,
        'level': character.level,
        'skills': [skill.id for skill in character.proficiencies],
        'available_skills': [{'id': skill.id, 'name': skill.name} for skill in available_skills]
    })

@app.route('/update-character', methods=['POST'])
def update_character():
    character_id = request.form.get('character_id')
    level = request.form.get('level')
    skill_ids = request.form.getlist('skills')

    character = Character.query.get_or_404(character_id)
    character.level = int(level)

    # Check if ability scores have already been updated for the current level
    if character.level >= 4 and character.level % 4 == 0:
        if character.last_updated_level == character.level:
            return jsonify({"error": "Ability scores have already been increased."}), 400

        ability_modification = request.form.get('ability_modification')
        if ability_modification == 'all_plus_one':
            # Add 1 to all ability scores
            character.strength += 1
            character.dexterity += 1
            character.constitution += 1
            character.intelligence += 1
            character.wisdom += 1
            character.charisma += 1
        elif ability_modification == 'single_plus_two':
            selected_ability = request.form.get('selected_ability')
            if selected_ability in ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']:
                setattr(character, selected_ability, getattr(character, selected_ability) + 2)

        # Update the last_updated_level to the current level
        character.last_updated_level = character.level

    selected_ability = None  # Initialize selected_ability to avoid UnboundLocalError

    # Debugging: Log ability modification and selected ability
    print(f"Ability modification: {ability_modification}")
    if selected_ability:
        print(f"Selected ability: {selected_ability}")

    # Ensure the character object is marked as modified
    db.session.add(character)

    # Debugging: Log updated ability scores
    print(f"Updated Strength: {character.strength}")
    print(f"Updated Dexterity: {character.dexterity}")
    print(f"Updated Constitution: {character.constitution}")
    print(f"Updated Intelligence: {character.intelligence}")
    print(f"Updated Wisdom: {character.wisdom}")
    print(f"Updated Charisma: {character.charisma}")

    # Update skills
    selected_skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
    character.proficiencies = selected_skills

    db.session.commit()
    return jsonify({'message': 'Character updated successfully'})

@app.route('/add-dnd-info', methods=['POST'])
def add_dnd_info():
    """Endpoint to dynamically add new DND information based on type."""
    data = request.form
    info_type = data.get('type')
    name = data.get('name')
    description = data.get('description')

    if not all([info_type, name, description]):
        return jsonify({'error': 'Missing required fields'}), 400

    # Print debug information
    print(f"Received info_type: {info_type}")
    print(f"Received name: {name}")
    print(f"Received description: {description}")
        
    # Check for existing items with the same name based on type
    if info_type == 'race':
        existing = Race.query.filter_by(name=name).first()
    elif info_type == 'class':
        existing = Class.query.filter_by(name=name).first()
    elif info_type == 'ability':
        existing = Skill.query.filter_by(name=name).first()
    elif info_type == 'background':
        existing = Background.query.filter_by(name=name).first()
    elif info_type == 'equipment':
        existing = Equipment.query.filter_by(name=name).first()
    else:
        return jsonify({'error': f'Invalid type: {info_type}. Must be one of: race, class, ability, background, equipment'}), 400
        
    if existing:
        return jsonify({'error': f'{info_type.capitalize()} with name "{name}" already exists'}), 400

    if info_type == 'race':
        # Parse ability score bonuses
        strength_bonus = int(data.get('strength_bonus', 0))
        dexterity_bonus = int(data.get('dexterity_bonus', 0))
        constitution_bonus = int(data.get('constitution_bonus', 0))
        intelligence_bonus = int(data.get('intelligence_bonus', 0))
        wisdom_bonus = int(data.get('wisdom_bonus', 0))
        charisma_bonus = int(data.get('charisma_bonus', 0))

        # Create a new Race object
        new_info = Race(
            name=name,
            description=description,
            strength_bonus=strength_bonus,
            dexterity_bonus=dexterity_bonus,
            constitution_bonus=constitution_bonus,
            intelligence_bonus=intelligence_bonus,
            wisdom_bonus=wisdom_bonus,
            charisma_bonus=charisma_bonus
        )
    elif info_type == 'class':
        hit_dice = data.get('hit_dice')
        new_info = Class(name=name, description=description, hit_die=hit_dice)
    elif info_type == 'ability':
        ability_type = data.get('ability_type')
        effect = data.get('effect')
        new_info = Skill(name=name, description=description, associated_attribute=ability_type)
    elif info_type == 'background':
        try:
            existing = Background.query.filter_by(name=name).first()
            if existing:
                return jsonify({'error': f'Background with name "{name}" already exists'}), 400
            new_info = Background(name=name, description=description)
        except Exception as e:
            return jsonify({'error': f'Failed to create background: {str(e)}'}), 400
    elif info_type == 'equipment':
        item_type = data.get('item_type')
        if item_type == 'Weapon':
            damage_dice = data.get('damage_dice')
            damage_type = data.get('damage_type')
            new_info = Equipment(
                name=name,
                description=description,
                item_type='Weapon',
                damage_dice=damage_dice,
                damage_type=damage_type,
                ac=None
            )
        elif item_type == 'Armor':
            ac = data.get('ac')
            new_info = Equipment(
                name=name,
                description=description,
                item_type='Armor',
                damage_dice=None,
                damage_type=None,
                ac=ac
            )
        else:
            new_info = Equipment(
                name=name,
                description=description,
                item_type='Other',
                damage_dice=None,
                damage_type=None,
                ac=None
            )
    else:
        return jsonify({'error': 'Invalid type'}), 400

    db.session.add(new_info)
    db.session.commit()
    return jsonify({'message': 'DND information added successfully'}), 201


@app.route('/get-dnd-info', methods=['GET'])
def get_dnd_info():
    """Endpoint to fetch all DND information."""
    races = Race.query.all()
    classes = Class.query.all()
    skills = Skill.query.all()
    equipment = Equipment.query.all()

    data = []
    for race in races:
        data.append({'type': 'Race', 'name': race.name, 'description': race.description})
    for cls in classes:
        data.append({'type': 'Class', 'name': cls.name, 'description': cls.description})
    for skill in skills:
        data.append({'type': 'Ability', 'name': skill.name, 'description': skill.description})
    for equip in equipment:
        data.append({'type': 'Weapon', 'name': equip.name, 'description': equip.description})

    return jsonify(data), 200

@app.route('/add-dnd-info')
def add_dnd_info_page():
    return render_template('add_dnd_info.html')

# --- Player Manual ---
@app.route('/gamer_manual.html')
def gamer_manual():
    return render_template('gamer_manual.html')

@app.route('/update-character-currency', methods=['POST'])
def update_character_currency():
    """Update a character's currency values."""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json()
    character_id = data.get('character_id')
    currency_type = data.get('currency_type')
    value = data.get('value')

    # Validate the currency type
    if currency_type not in ['copper_pieces', 'silver_pieces', 'gold_pieces', 'electrum_pieces', 'platinum_pieces']:
        return jsonify({'error': 'Invalid currency type'}), 400

    try:
        value = int(value)
        if value < 0:
            return jsonify({'error': 'Currency value cannot be negative'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid currency value'}), 400

    character = Character.query.get(character_id)
    if not character:
        return jsonify({'error': 'Character not found'}), 404

    # Ensure the user owns this character
    if character.user_id != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403

    # Update the currency value
    setattr(character, currency_type, value)
    db.session.commit()

    return jsonify({'message': 'Currency updated successfully'})

@app.route('/download-character/json/<int:character_id>')
def download_character_json(character_id):
    if 'user_id' not in session:
        flash('You must be logged in to download characters.')
        return redirect(url_for('login'))
    
    char = Character.query.get_or_404(character_id)
    if char.user_id != session['user_id']:
        return "Unauthorized", 403

    char_data = {
        'name': char.name,
        'age': char.age,
        'level': char.level,
        'alignment': char.alignment,
        'hp': char.hp,
        'race': char.race.name if char.race else None,
        'class': char.character_class.name if char.character_class else None,
        'background': char.background.name if char.background else None,
        'abilities': {
            'strength': char.strength,
            'dexterity': char.dexterity,
            'constitution': char.constitution,
            'intelligence': char.intelligence,
            'wisdom': char.wisdom,
            'charisma': char.charisma
        },
        'currency': {
            'copper': char.copper_pieces,
            'silver': char.silver_pieces,
            'gold': char.gold_pieces,
            'electrum': char.electrum_pieces,
            'platinum': char.platinum_pieces
        },
        'proficiencies': [s.name for s in char.proficiencies],
        'inventory': [e.name for e in char.inventory]
    }

    # Create a JSON file in memory
    json_str = json.dumps(char_data, indent=4)
    mem = io.BytesIO()
    mem.write(json_str.encode('utf-8'))
    mem.seek(0)

    return send_file(
        mem,
        as_attachment=True,
        download_name=f"{char.name.replace(' ', '_')}.json",
        mimetype='application/json'
    )

@app.route('/download-character/pdf/<int:character_id>')
def download_character_pdf(character_id):
    if 'user_id' not in session:
        flash('You must be logged in to download characters.')
        return redirect(url_for('login'))
        
    char = Character.query.get_or_404(character_id)
    if char.user_id != session['user_id']:
        return "Unauthorized", 403

    # Create a PDF in memory
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 50, f"Character Sheet: {char.name}")

    # Basic Info
    c.setFont("Helvetica", 12)
    y = height - 80
    c.drawString(50, y, f"Class: {char.character_class.name if char.character_class else 'None'}")
    y -= 20
    c.drawString(50, y, f"Race: {char.race.name if char.race else 'None'}")
    y -= 20
    c.drawString(50, y, f"Level: {char.level}")
    y -= 20
    c.drawString(50, y, f"Background: {char.background.name if char.background else 'None'}")
    y -= 20
    c.drawString(50, y, f"Alignment: {char.alignment}")
    y -= 20
    c.drawString(50, y, f"HP: {char.hp}")
    
    # Ability Scores
    y -= 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Ability Scores")
    c.setFont("Helvetica", 12)
    y -= 20
    abilities = [
        ('Strength', char.strength), ('Dexterity', char.dexterity),
        ('Constitution', char.constitution), ('Intelligence', char.intelligence),
        ('Wisdom', char.wisdom), ('Charisma', char.charisma)
    ]
    for name, score in abilities:
        c.drawString(50, y, f"{name}: {score}")
        y -= 15

    # Currency
    y -= 25
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Currency")
    c.setFont("Helvetica", 12)
    y -= 20
    c.drawString(50, y, f"Platinum: {char.platinum_pieces} | Gold: {char.gold_pieces} | Electrum: {char.electrum_pieces}")
    y -= 15
    c.drawString(50, y, f"Silver: {char.silver_pieces} | Copper: {char.copper_pieces}")

    # Skills
    y -= 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Proficiencies / Skills")
    c.setFont("Helvetica", 12)
    y -= 20
    for skill in char.proficiencies:
        if y < 50: # New page if running out of space
            c.showPage()
            y = height - 50
        c.drawString(50, y, f"- {skill.name}")
        y -= 15

    # Equipment
    y -= 25
    if y < 100:
        c.showPage()
        y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Equipment")
    c.setFont("Helvetica", 12)
    y -= 20
    for item in char.inventory:
        if y < 50:
            c.showPage()
            y = height - 50
        c.drawString(50, y, f"- {item.name} ({item.item_type})")
        y -= 15

    c.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{char.name.replace(' ', '_')}.pdf",
        mimetype='application/pdf'
    )

# --- Run the Application ---
if __name__ == '__main__':
    # Run the seeding function before starting the server
    seed_database()
    app.run(debug=True)