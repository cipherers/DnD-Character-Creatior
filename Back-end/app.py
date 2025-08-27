from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
import random

# Make sure all your model definitions are in a file named 'models.py'
# and import them here.
from models import db, Character, Race, Class, Background, Skill, Equipment, User

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
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    characters = user.characters
    if not characters:
        # No characters: show character creator UI in dashboard layout
        races = Race.query.all()
        classes = Class.query.all()
        return render_template('dashboard.html', characters=[], races=races, classes=classes)
    # Characters exist: show dashboard with character list
    # For performance, show up to 10 at a time (pagination can be added later)
    page = int(request.args.get('page', 1))
    per_page = 10
    paginated = characters[(page-1)*per_page:page*per_page]
    total = len(characters)
    return render_template('dashboard.html', characters=paginated, total=total, page=page, per_page=per_page)

@app.route('/create-character', methods=['GET', 'POST'])
def create_character():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    # If GET, render the character creation form so users can create additional characters
    if request.method == 'GET':
        races = Race.query.all()
        classes = Class.query.all()
        return render_template('index.html', races=races, classes=classes)
    # Retrieve the Race and Class IDs from the form
    character_name = request.form.get('name')
    character_age = request.form.get('age')
    race_id = request.form.get('race')
    character_class_id = request.form.get('class')  # Fix: match form field name
    character_level = request.form.get('level', 1)
    # Fetch the full Race and Class objects from the database
    selected_race = Race.query.get(race_id)
    selected_class = Class.query.get(character_class_id)

    # Corrected: Handle the case where character_age might be an empty string
    age_val = int(character_age) if character_age else 1 # Default age to 1 if not provided

    # Check if a 'roll_scores' button was submitted
    user = User.query.get(session['user_id'])
    if 'roll_scores' in request.form:
        # Validate required fields for rolling random scores
        missing_fields = []
        if not character_name or not character_name.strip():
            missing_fields.append('Name')
        if not character_age or not character_age.strip():
            missing_fields.append('Age')
        if not character_class_id or not character_class_id.strip():
            missing_fields.append('Class')
        if missing_fields:
            flash(f"The following fields are required for rolling random scores: {', '.join(missing_fields)}.")
            return redirect(url_for('dashboard'))
        # A new, blank character is created and then its scores are rolled
        new_character = Character(
            name=character_name,
            age=age_val,
            alignment='Neutral',
            hp=10,
            strength=0, 
            dexterity=0,
            constitution=0,
            intelligence=0,
            wisdom=0,
            charisma=0,
            race=selected_race, # Pass the Race object
            character_class=selected_class, # Pass the Class object
            background=None,
            user=user,
            level = character_level
        )
        new_character.roll_ability_scores()
        db.session.add(new_character)
        db.session.commit()
        flash(f"Character '{new_character.name}' created with rolled ability scores!")

    # Check if manual scores were submitted
    elif 'submit_manual' in request.form:
        new_character = Character(
            name=character_name,
            age=age_val,
            alignment='Neutral',
            hp=10,
            strength=int(request.form.get('strength')),
            dexterity=int(request.form.get('dexterity')),
            constitution=int(request.form.get('constitution')),
            intelligence=int(request.form.get('intelligence')),
            wisdom=int(request.form.get('wisdom')),
            charisma=int(request.form.get('charisma')),
            race=selected_race, # Pass the Race object
            character_class=selected_class, # Pass the Class object
            background=None,
            user=user,
            level=character_level
        )
        db.session.add(new_character)
        db.session.commit()
        flash(f"Character '{new_character.name}' created with manual ability scores!")

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


# --- Run the Application ---
if __name__ == '__main__':
    # Run the seeding function before starting the server
    seed_database()
    app.run(debug=True)