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

def test_dashboard(session):
    print("\nTesting /api/dashboard...")
    resp = session.get(f"{BASE_URL}/api/dashboard")
    print(f"Dashboard Status: {resp.status_code}, Body: {resp.json()}")

if __name__ == "__main__":
    try:
        test_health()
        test_races()
        session = test_login_and_auth()
        test_dashboard(session)
        print("\nVerification script finished.")
    except Exception as e:
        print(f"Error during verification: {e}")
        print("Make sure the Flask server is running at http://localhost:5000")
