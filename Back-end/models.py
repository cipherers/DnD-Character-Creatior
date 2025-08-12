from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

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
    death_save_successes = db.Column(db.Integer, default=0, nullable=False)
    death_save_failures = db.Column(db.Integer, default=0, nullable=False)
    copper_pieces = db.Column(db.Integer, default=0, nullable=False)
    silver_pieces = db.Column(db.Integer, default=0, nullable=False)
    gold_pieces = db.Column(db.Integer, default=0, nullable=False)
    platinum_pieces = db.Column(db.Integer, default=0, nullable=False)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    background_id = db.Column(db.Integer, db.ForeignKey('backgrounds.id'), nullable=False)

    proficiencies = db.relationship(
        'Skill',
        secondary=character_proficiencies,
        backref=db.backref('characters', lazy='dynamic'),
        lazy='dynamic'
    )
    inventory = db.relationship(
        'Equipment',
        secondary=character_equipment,
        backref=db.backref('characters', lazy='dynamic'),
        lazy='dynamic'
    )

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
    item_type = db.Column(db.String, nullable=False)  # e.g., "Weapon", "Armor", "Tool"
    damage_dice = db.Column(db.String, nullable=True)
    damage_type = db.Column(db.String, nullable=True)
    ac = db.Column(db.Integer, nullable=True)