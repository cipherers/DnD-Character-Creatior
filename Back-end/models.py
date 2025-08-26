from flask_sqlalchemy import SQLAlchemy
import random

db = SQLAlchemy()

from werkzeug.security import generate_password_hash, check_password_hash

# User model for authentication
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    characters = db.relationship('Character', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Linking table for Character <-> Skill (Proficiencies)
character_proficiencies = db.Table(
    'character_proficiencies',
    db.Column('character_id', db.Integer, db.ForeignKey('characters.id'), primary_key=True),
    db.Column('skill_id', db.Integer, db.ForeignKey('skills.id'), primary_key=True)
)

# Linking table for Character <-> Equipment (Inventory)
character_equipment = db.Table(
    'character_equipment',
    db.Column('character_id', db.Integer, db.ForeignKey('characters.id'), primary_key=True),
    db.Column('equipment_id', db.Integer, db.ForeignKey('equipment.id'), primary_key=True)
)

class Character(db.Model):
    __tablename__ = 'characters'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    age = db.Column(db.Integer, nullable=False)
    level = db.Column(db.Integer, default=1, nullable=False)
    alignment = db.Column(db.String, nullable=False)
    hp = db.Column(db.Integer, nullable=False)
    strength = db.Column(db.Integer, nullable=False)
    dexterity = db.Column(db.Integer, nullable=False)
    constitution = db.Column(db.Integer, nullable=False)
    intelligence = db.Column(db.Integer, nullable=False)
    wisdom = db.Column(db.Integer, nullable=False)
    charisma = db.Column(db.Integer, nullable=False)

    # Death save tracking
    death_save_successes = db.Column(db.Integer, nullable=False, default=0)
    death_save_failures = db.Column(db.Integer, nullable=False, default=0)

    # Currency
    copper_pieces = db.Column(db.Integer, nullable=False, default=0)
    silver_pieces = db.Column(db.Integer, nullable=False, default=0)
    gold_pieces = db.Column(db.Integer, nullable=False, default=0)
    electrum_pieces = db.Column(db.Integer, nullable=False, default=0)
    platinum_pieces = db.Column(db.Integer, nullable=False, default=0)

    # Foreign keys for relationships
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    character_class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    background_id = db.Column(db.Integer, db.ForeignKey('backgrounds.id'), nullable=True)

    # Relationships to other models
    race = db.relationship('Race', backref='characters', lazy=True)
    character_class = db.relationship('Class', backref='characters', lazy=True)
    background = db.relationship('Background', backref='characters', lazy=True)
    
    # Many-to-many relationships
    proficiencies = db.relationship('Skill', secondary=character_proficiencies, backref=db.backref('characters_with_skill'), lazy=True)
    inventory = db.relationship('Equipment', secondary=character_equipment, backref=db.backref('characters_with_equipment'), lazy=True)

    def __init__(self, name, age, alignment, hp, strength, dexterity, constitution, intelligence, wisdom, charisma, race, character_class, background=None, user=None):
        self.name = name
        self.age = age
        self.alignment = alignment
        self.hp = hp
        self.strength = strength
        self.dexterity = dexterity
        self.constitution = constitution
        self.intelligence = intelligence
        self.wisdom = wisdom
        self.charisma = charisma
        self.race = race # Assign the full Race object
        self.character_class = character_class # Assign the full Class object
        self.background = background
        self.user = user

    def roll_ability_scores(self):
        """
        Rolls 4d6 and drops the lowest for each ability score,
        then applies racial bonuses.
        """
        abilities = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']
        
        # Roll ability scores
        rolled_scores = {}
        for ability in abilities:
            rolls = sorted([random.randint(1, 6) for _ in range(4)], reverse=True)
            score = sum(rolls[:3])
            rolled_scores[ability] = score

        # Apply racial bonuses and assign scores to the character
        self.strength = rolled_scores['strength'] + self.race.strength_bonus
        self.dexterity = rolled_scores['dexterity'] + self.race.dexterity_bonus
        self.constitution = rolled_scores['constitution'] + self.race.constitution_bonus
        self.intelligence = rolled_scores['intelligence'] + self.race.intelligence_bonus
        self.wisdom = rolled_scores['wisdom'] + self.race.wisdom_bonus
        self.charisma = rolled_scores['charisma'] + self.race.charisma_bonus

    def __repr__(self):
        return f"<Character {self.name}>"

class Race(db.Model):
    __tablename__ = 'races'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, nullable=False)
    strength_bonus = db.Column(db.Integer, default=0, nullable=False)
    dexterity_bonus = db.Column(db.Integer, default=0, nullable=False)
    constitution_bonus = db.Column(db.Integer, default=0, nullable=False)
    intelligence_bonus = db.Column(db.Integer, default=0, nullable=False)
    wisdom_bonus = db.Column(db.Integer, default=0, nullable=False)
    charisma_bonus = db.Column(db.Integer, default=0, nullable=False)

class Class(db.Model):
    __tablename__ = 'classes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, nullable=False)
    hit_die = db.Column(db.Integer, nullable=False)

class Background(db.Model):
    __tablename__ = 'backgrounds'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, nullable=False)

class Skill(db.Model):
    __tablename__ = 'skills'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, nullable=False)
    associated_attribute = db.Column(db.String, nullable=False)

class Equipment(db.Model):
    __tablename__ = 'equipment'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, nullable=False)
    item_type = db.Column(db.String, nullable=False)
    damage_dice = db.Column(db.String, nullable=True)
    damage_type = db.Column(db.String, nullable=True)
    ac = db.Column(db.Integer, nullable=True)