import os
import json
import socket
import time
import threading
import requests
from github import Github  # PyGithub for updating GitHub repo
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime
from pyngrok import ngrok

# Constants for security
KEY_LIST = ["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", "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", "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", "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"]  # Predefined keys to send upon verification

USED_KEYS = set()  # Set to track used keys

# External URL to fetch users.json (e.g., GitHub raw file URL)
USER_DB_URL = 'https://raw.githubusercontent.com/Anonymous01100/vjdvjfjgrhjrhjkgjhjhjjbjbkbhjsbjkfbjkfbjkgbjbfjbfskjbsfjkbfjbfjksbfjkfjkbjkbfj/refs/heads/main/users.json'
users = {}

# GitHub repo credentials (replace with your GitHub token)
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # Ensure this is set securely
REPO_NAME = "Anonymous01100/vjdvjfjgrhjrhjkgjhjhjjbjbkbhjsbjkfbjkfbjkgbjbfjbfskjbsfjkbfjbfjksbfjkfjkbjkbfj"
PUBLIC_URL_FILE_PATH = "public_url.json"

# Initialize Flask app
app = Flask(__name__)
limiter = Limiter(get_remote_address, app=app, default_limits=["10 per minute"])  # Rate limiting

def fetch_users():
    """Fetch users.json from an external URL."""
    global users
    try:
        response = requests.get(USER_DB_URL)
        if response.status_code == 200:
            users = response.json()
            print("Successfully fetched users.json from the external URL.")
        else:
            print(f"Failed to fetch users.json. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error fetching users.json: {e}")

# Periodically update users.json every 2 minutes
def periodic_update():
    while True:
        fetch_users()
        time.sleep(120)  # Wait for 2 minutes

# Start a thread to run the periodic update in the background
update_thread = threading.Thread(target=periodic_update)
update_thread.start()

# Utility functions
def is_account_expired(expiry_date):
    """Check if the account is expired."""
    expiry_datetime = datetime.strptime(expiry_date, '%Y-%m-%d')
    return datetime.utcnow() > expiry_datetime

def find_free_key():
    """Find a free key from the list."""
    for key in KEY_LIST:
        if key not in USED_KEYS:
            USED_KEYS.add(key)
            return key
    return None  # No keys available

def release_key(key):
    """Release a key so it's available for others."""
    if key in USED_KEYS:
        USED_KEYS.remove(key)

# Function to update public_url.json file in GitHub repository
def update_github_public_url(url):
    """Update the public_url.json file in the GitHub repository."""
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        # Get the file contents and SHA
        contents = repo.get_contents(PUBLIC_URL_FILE_PATH)
        file_sha = contents.sha
        
        # Prepare new content
        new_content = json.dumps({"ngrok_url": url}, indent=4)
        
        # Update the file in the repository
        repo.update_file(
            contents.path,
            "Update public_url.json with new ngrok URL",
            new_content,
            file_sha,
            branch="main"
        )
        print(f"Successfully updated {PUBLIC_URL_FILE_PATH} in the GitHub repo with the new URL: {url}")
    except Exception as e:
        print(f"Failed to update {PUBLIC_URL_FILE_PATH} in GitHub: {e}")

# User verification route
@app.route('/verify', methods=['POST'])
@limiter.limit("5 per minute")
def verify_user():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    token = data.get('token')

    # Check if the username exists in the loaded users
    if username in users:
        user_data = users[username]

        # Check if account is expired
        if is_account_expired(user_data['expiry_date']):
            return jsonify({"status": "error", "message": "Account expired"}), 403

        # Verify password and token
        if password == user_data['password'] and token == user_data['token']:
            # Check if the user already has a key
            if 'assigned_key' in user_data and user_data['assigned_key']:
                return jsonify({"status": "success", "key": user_data['assigned_key']}), 200

            # Find a free key and assign it
            key = find_free_key()
            if key:
                user_data['assigned_key'] = key  # Remember in memory only
                return jsonify({"status": "success", "key": key}), 200
            else:
                return jsonify({"status": "error", "message": "No keys available"}), 503
        else:
            return jsonify({"status": "error", "message": "Invalid credentials"}), 401
    else:
        return jsonify({"status": "error", "message": "User not found"}), 404

# Logout route to release the key
@app.route('/logout', methods=['POST'])
def logout_user():
    data = request.json
    username = data.get('username')
    token = data.get('token')

    # Check if the username exists in the loaded users
    if username in users:
        user_data = users[username]

        # Verify token
        if token == user_data['token']:
            if 'assigned_key' in user_data and user_data['assigned_key']:
                key = user_data['assigned_key']
                release_key(key)  # Mark key as free
                user_data['assigned_key'] = None  # Clear the assigned key in memory
                return jsonify({"status": "success", "message": "Logged out successfully, key released"}), 200
            else:
                return jsonify({"status": "error", "message": "No key assigned to this user"}), 400
        else:
            return jsonify({"status": "error", "message": "Invalid token"}), 401
    else:
        return jsonify({"status": "error", "message": "User not found"}), 404

# Function to get local IP address
def get_local_ip():
    hostname = socket.gethostname()
    return socket.gethostbyname(hostname)

# Start the server
if __name__ == '__main__':
    # Check if ngrok token is available and set it
    NGROK_TOKEN = os.getenv('NGROK_TOKEN')
    if not NGROK_TOKEN:
        print("Error: NGROK_TOKEN is not set. Please set your ngrok auth token.")
        exit(1)

    # Start ngrok and get the public URL
    ngrok.set_auth_token(NGROK_TOKEN)
    http_tunnel = ngrok.connect(5002)
    public_url = http_tunnel.public_url
    print(f"Ngrok tunnel created: {public_url}")

    # Update public_url.json in the GitHub repo
    update_github_public_url(public_url)

    # Run Flask server
    local_ip = get_local_ip()
    print(f"Server is running on https://{local_ip}:5002")
    app.run(host='0.0.0.0', port=5002, ssl_context='adhoc', debug=False)
