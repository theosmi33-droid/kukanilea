import re
import threading
import uuid

import requests

BASE_URL = "http://127.0.0.1:5051"

def user_session(user_id):
    session = requests.Session()
    username = f"testuser_{user_id}"
    password = "password123"

    print(f"[{user_id}] Logging in...")
    try:
        r = session.get(f"{BASE_URL}/login")
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text)
        csrf_token = match.group(1) if match else ""
        
        r = session.post(f"{BASE_URL}/login", data={
            "username": username,
            "password": password,
            "csrf_token": csrf_token
        })
        
        # Test 1: Hit Index
        r = session.get(f"{BASE_URL}/")
        
        # Extract CSRF token from index for upload
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text)
        csrf_token = match.group(1) if match else csrf_token

        # Test 2: Upload a dummy text file
        print(f"[{user_id}] Uploading file...")
        files = {'file': (f'dummy_{user_id}_{uuid.uuid4().hex[:8]}.txt', b'This is a test document for stress testing.')}
        r = session.post(f"{BASE_URL}/upload", files=files, data={"csrf_token": csrf_token})
        if r.status_code not in (200, 400, 429):
            print(f"[{user_id}] Upload returned: {r.status_code} {r.text[:100]}")
        else:
            print(f"[{user_id}] Upload OK: {r.status_code}")
            
        # Test 3: Hit Chat and send message
        print(f"[{user_id}] Loading chat...")
        r = session.get(f"{BASE_URL}/chat")
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text)
        csrf_token = match.group(1) if match else csrf_token

        print(f"[{user_id}] Sending chat message...")
        r = session.post(f"{BASE_URL}/api/chat", json={
            "message": "Hello from stress test user " + str(user_id)
        }, headers={"X-CSRFToken": csrf_token})
        print(f"[{user_id}] Chat API returned: {r.status_code}")
        
    except Exception as e:
        print(f"[{user_id}] Exception: {e}")

threads = []
print("Starting 10 concurrent user threads...")
for i in range(10):
    t = threading.Thread(target=user_session, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print("Stress test completed.")
