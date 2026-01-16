import requests
import json

BASE_URL = "http://localhost:5000"

def test_health():
    print("Testing /health...")
    resp = requests.get(f"{BASE_URL}/health")
    print(f"Status: {resp.status_code}, Body: {resp.json()}")

def test_races():
    print("\nTesting /get-races...")
    resp = requests.get(f"{BASE_URL}/get-races")
    print(f"Status: {resp.status_code}, Body: {resp.json()}")

def test_login_and_auth():
    print("\nTesting /login and /api/check-auth...")
    session = requests.Session()
    # Using form data as expected by backend
    login_data = {"username": "test_hero", "password": "password123"}
    resp = session.post(f"{BASE_URL}/login", data=login_data)
    print(f"Login Status: {resp.status_code}, Body: {resp.json()}")
    
    auth_resp = session.get(f"{BASE_URL}/api/check-auth")
    print(f"Auth Check Status: {auth_resp.status_code}, Body: {auth_resp.json()}")
    return session

def test_character_ops(session):
    print("\nTesting /create-character...")
    char_data = {
        "name": "Aragorn",
        "age": "87",
        "level": "1",
        "race": "1", # Human
        "class": "1", # Fighter
        "alignment": "Lawful Good"
    }
    resp = session.post(f"{BASE_URL}/create-character", data=char_data)
    print(f"Create Status: {resp.status_code}, Body: {resp.json()}")
    char_id = resp.json().get('id')
    
    print(f"\nTesting /update-character for ID {char_id}...")
    update_data = {
        "character_id": char_id,
        "name": "Strider",
        "level": "2"
    }
    resp = session.post(f"{BASE_URL}/update-character", data=update_data)
    print(f"Update Status: {resp.status_code}, Body: {resp.json()}")
    
    # Test upload-portrait (mock)
    print(f"\nTesting /upload-portrait for ID {char_id}...")
    files = {'portrait': ('test.png', b'not-a-real-image', 'image/png')}
    resp = session.post(f"{BASE_URL}/upload-portrait", data={"character_id": char_id}, files=files)
    print(f"Upload Status: {resp.status_code}, Body: {resp.json()}")

    # Test Level Up (Stats & HP)
    print(f"\nTesting Level Up Stats for ID {char_id}...")
    levelup_data = {
        "character_id": char_id,
        "level": "3",
        "hp": "25",
        "strength": "18",
        "dexterity": "14"
    }
    resp = session.post(f"{BASE_URL}/update-character", data=levelup_data)
    print(f"Level Up Status: {resp.status_code}, Body: {resp.json()}")

def test_dashboard(session):
    print("\nTesting /api/dashboard...")
    resp = session.get(f"{BASE_URL}/api/dashboard")
    print(f"Dashboard Status: {resp.status_code}, Body: {resp.json()}")

if __name__ == "__main__":
    try:
        test_health()
        test_races()
        session = test_login_and_auth()
        test_character_ops(session)
        test_dashboard(session)
        print("\nVerification script finished.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error during verification: {e}")
        print("Make sure the Flask server is running at http://localhost:5000")
