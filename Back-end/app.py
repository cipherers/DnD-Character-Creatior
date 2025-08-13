from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import random

# Make sure all your model definitions are in a file named 'models.py'
# and import them here.
from models import db, Character, Race, Class, Background, Skill, Equipment

# --- Flask Application Setup ---
app = Flask(__name__)
# Configure the SQLite database. This will create a file called 'site.db'
# in the same directory as this script.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SECRET_KEY'] = 'a_very_secret_key' # Needed for flash messages

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
            race=human,
            character_class=class_fighter,
            background=background_acolyte
        )

        # 3. Add proficiencies and equipment using the relationships
        # This will automatically populate the linking tables
        main_character.proficiencies.append(skill_athletics)
        main_character.inventory.append(equipment_sword)
        main_character.inventory.append(equipment_shield)

        db.session.add(main_character)
        db.session.commit()

        print("Database seeding complete!")
        print(f"Created character: {main_character.name} (ID: {main_character.id})")

# --- Flask Routes ---
@app.route('/')
def index():
    # Retrieve all races and classes from the database to populate the dropdowns
    races = Race.query.all()
    classes = Class.query.all()
    return render_template('index.html', races=races, classes=classes)

@app.route('/create-character', methods=['GET'])
def create_character():
    # Retrieve the Race and Class objects from the database based on the user's selection
    character_name = request.form.get('name')
    character_age = request.form.get('age')
    race_id = request.form.get('race')
    class_id = request.form.get('class')
    
    # Check if a 'roll_scores' button was submitted
    if 'roll_scores' in request.form:
        # A new, blank character is created and then its scores are rolled
        new_character = Character(
            name=character_name,
            age=int(character_age),
            alignment='Neutral',
            hp=10,
            strength=0, # These will be overwritten by the roll_ability_scores() method
            dexterity=0,
            constitution=0,
            intelligence=0,
            wisdom=0,
            charisma=0,
            race=Race.query.get(race_id),
            character_class=Class.query.get(class_id),
            background=None
        )
        new_character.roll_ability_scores()
        db.session.add(new_character)
        db.session.commit()
        flash(f"Character '{new_character.name}' created with rolled ability scores!")

    # Check if manual scores were submitted
    elif 'submit_manual' in request.form:
        new_character = Character(
            name=character_name,
            age=int(character_age),
            alignment='Neutral',
            hp=10,
            strength=int(request.form.get('strength')),
            dexterity=int(request.form.get('dexterity')),
            constitution=int(request.form.get('constitution')),
            intelligence=int(request.form.get('intelligence')),
            wisdom=int(request.form.get('wisdom')),
            charisma=int(request.form.get('charisma')),
            race=Race.query.get(race_id),
            character_class=Class.query.get(class_id),
            background=None
        )
        db.session.add(new_character)
        db.session.commit()
        flash(f"Character '{new_character.name}' created with manual ability scores!")

    return redirect(url_for('index'))


# --- Run the Application ---
if __name__ == '__main__':
    # Run the seeding function before starting the server
    seed_database()
    app.run(debug=True)