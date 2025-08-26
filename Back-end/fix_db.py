"""
Fix script: ensures characters.user_id column exists, creates a fallback user if none exist,
and assigns any existing characters to that user.
"""
import sqlite3
from pathlib import Path

# Try multiple candidate locations for the SQLite DB. Some runs may use
# different working directories, so check common locations.
candidates = [
    Path(__file__).parent / 'instance' / 'site.db',
    Path(__file__).parent / 'site.db',
    Path.cwd() / 'instance' / 'site.db',
    Path.cwd() / 'site.db',
]
DB_PATH = None
for p in candidates:
    if p.exists():
        DB_PATH = p
        break
print('DB candidates:', candidates)
if not DB_PATH:
    print('DB file not found in any candidate locations, exiting')
    raise SystemExit(1)
print('Using DB:', DB_PATH)

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

# Check characters table
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='characters'")
if not cur.fetchone():
    print('characters table not found; nothing to do')
    conn.close()
    raise SystemExit(0)

# Check columns
cur.execute("PRAGMA table_info(characters)")
cols = [row[1] for row in cur.fetchall()]
print('characters columns before:', cols)
if 'user_id' not in cols:
    print("Adding user_id column to characters...")
    cur.execute("ALTER TABLE characters ADD COLUMN user_id INTEGER")
    conn.commit()
    cur.execute("PRAGMA table_info(characters)")
    cols = [row[1] for row in cur.fetchall()]
    print('characters columns after add:', cols)
else:
    print('user_id already present')

# Ensure users table exists
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
if not cur.fetchone():
    print('users table not found; creating a minimal users table')
    cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)")
    conn.commit()

# Check for existing users
cur.execute('SELECT id, username FROM users LIMIT 1')
row = cur.fetchone()
if row:
    user_id = row[0]
    print('Found existing user:', row[1], 'id=', user_id)
else:
    print('No user found; inserting fallback user "migrated_user"')
    cur.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ('migrated_user','migrated'))
    conn.commit()
    user_id = cur.lastrowid
    print('Inserted fallback user id=', user_id)

# Assign characters without user_id to this user
cur.execute('SELECT COUNT(*) FROM characters WHERE user_id IS NULL OR user_id = ""')
count = cur.fetchone()[0]
print('Characters missing user_id:', count)
if count > 0:
    cur.execute('UPDATE characters SET user_id = ? WHERE user_id IS NULL OR user_id = ""', (user_id,))
    conn.commit()
    print('Assigned', cur.rowcount, 'characters to user id', user_id)

# Final columns and sample
cur.execute("PRAGMA table_info(characters)")
print('Final characters columns:', [r[1] for r in cur.fetchall()])
cur.execute('SELECT id, name, user_id FROM characters LIMIT 5')
for r in cur.fetchall():
    print(r)

conn.close()
print('Done')
