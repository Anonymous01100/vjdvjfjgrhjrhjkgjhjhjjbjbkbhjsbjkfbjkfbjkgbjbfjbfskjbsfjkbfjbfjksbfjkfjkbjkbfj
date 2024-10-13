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

USED_KEYS = set()

# External URL to fetch users.json (same GitHub repository)

users = {}

# GitHub repo credentials
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # Make sure this is set securely
REPO_NAME = "Anonymous01100/vjdvjfjgrhjrhjkgjhjhjjbjbkbhjsbjkfbjkfbjkgbjbfjbfskjbsfjkbfjbfjksbfjkfjkbjkbfj"
USERS_FILE_PATH = "users.json"
USER_DB_URL = f'https://raw.githubusercontent.com/{REPO_NAME}/main/users.json'
PUBLIC_URL_FILE_PATH = "public_url.json"

# Flask app setup
app = Flask(__name__)
limiter = Limiter(get_remote_address, app=app, default_limits=["10 per minute"])

# Load the initial users from GitHub
def fetch_users():
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
        users = {}

# Save users to GitHub
def update_users_in_github():
    """Update the users.json file in the GitHub repository."""
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        # Get the file contents and SHA
        contents = repo.get_contents(USERS_FILE_PATH)
        file_sha = contents.sha
        
        # Prepare new content
        new_content = json.dumps(users, indent=4)
        
        # Update the file in the repository
        repo.update_file(
            contents.path,
            "Update users.json",
            new_content,
            file_sha,
            branch="main"
        )
        print("Successfully updated users.json in the GitHub repo.")
    except Exception as e:
        print(f"Failed to update users.json in GitHub: {e}")

# Utility functions
def is_account_expired(expiry_date):
    """Check if the account is expired."""
    expiry_datetime = datetime.strptime(expiry_date, '%Y-%m-%d')
    return datetime.utcnow() > expiry_datetime

def find_free_key():
    """Find an available key from the list."""
    for key in KEY_LIST:
        if key not in USED_KEYS:
            USED_KEYS.add(key)
            return key
    return None

def release_key(key):
    """Release a key and mark it as available."""
    if key in USED_KEYS:
        USED_KEYS.remove(key)

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
                user_data['assigned_key'] = key
                update_users_in_github()  # Save changes to GitHub
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
                user_data['assigned_key'] = None  # Clear the assigned key
                update_users_in_github()  # Save changes to GitHub
                return jsonify({"status": "success", "message": "Logged out successfully, key released"}), 200
            else:
                return jsonify({"status": "error", "message": "No key assigned to this user"}), 400
        else:
            return jsonify({"status": "error", "message": "Invalid token"}), 401
    else:
        return jsonify({"status": "error", "message": "User not found"}), 404

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

# Fetch users initially
fetch_users()
