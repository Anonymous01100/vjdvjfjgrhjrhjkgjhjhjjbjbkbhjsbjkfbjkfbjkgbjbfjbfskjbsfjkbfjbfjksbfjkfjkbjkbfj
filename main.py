import time
import gradio as gr
import os
import json
import requests
from groq import Groq
from github import Github
from pyngrok import ngrok
import concurrent.futures

# GitHub access
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # Make sure this is set securely
REPO_NAME = "Anonymous01100/vjdvjfjgrhjrhjkgjhjhjjbjbkbhjsbjkfbjkfbjkgbjbfjbfskjbsfjkbfjbfjksbfjkfjkbjkbfj"
USERS_FILE_PATH = "users.json"
USER_DB_URL = f'https://raw.githubusercontent.com/{REPO_NAME}/main/users.json'
DATA_FILE = "data.json"
PUBLIC_URL_FILE = "public_url.json"

# Initialize PyGithub
g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

# Ngrok setup
NGROK_AUTH_TOKEN =  os.getenv('NGROK_TOKEN')  # Replace with your ngrok auth token
ngrok.set_auth_token(NGROK_AUTH_TOKEN)
public_url = ngrok.connect(9860)  # Expose Gradio app on port 7860

# Write public URL to public_url.json in GitHub repo
def update_public_url(public_url):
    public_url_data = {"public_url": public_url}
    content = json.dumps(public_url_data)
    
    try:
        contents = repo.get_contents(PUBLIC_URL_FILE)
        repo.update_file(contents.path, "Update public URL", content, contents.sha)
    except:
        repo.create_file(PUBLIC_URL_FILE, "Create public URL file", content)

# Update the file in the GitHub repo every 2 minutes
def update_file_in_repo():
    while True:
        try:
            with open(DATA_FILE, "r") as f:
                data = f.read()

            # Fetch the file from the repo
            contents = repo.get_contents(DATA_FILE)
            # Update the file in the repo
            repo.update_file(contents.path, "Update data file", data, contents.sha)
            print(f"Updated {DATA_FILE} in GitHub repository.")
        except Exception as e:
            print(f"Error updating {DATA_FILE}: {e}")

        time.sleep(120)  # Update every 2 minutes

# Timer function to exit after 5.5 hours
def exit_after_timer():
    time.sleep(5.5 * 3600)  # Sleep for 5.5 hours
    print("Time's up! Exiting the script.")
    os._exit(0)

# Run both the update and timer functions in the background
import threading
update_thread = threading.Thread(target=update_file_in_repo)
timer_thread = threading.Thread(target=exit_after_timer)

update_thread.start()
timer_thread.start()

# Load user data from data.json
def load_user_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    else:
        return {}

# Gradio interface and chat functions remain the same...
MAIN_API_KEY = "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"
BACKUP_API_KEY = "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"

client_main = Groq(api_key=MAIN_API_KEY)
client_backup = Groq(api_key=BACKUP_API_KEY)

login_attempts = {}
RATE_LIMIT = 5  # Allowed attempts
BLOCK_TIME = 60  # Block time in seconds (e.g., 1 minute)

# JavaScript to fetch the user's IP using api.ipify.org
custom_js = """
async function fetch_ip() {
    let response = await fetch('https://api.ipify.org?format=json');
    let data = await response.json();
    return data.ip;
}
"""

# Function to verify IP address based on user input
def verify_ip(username, user_ip, data):
    if username in data and data[username]['ip'] == user_ip:
        return True
    return False

# Function to verify password
def verify_password(username, password, data):
    if username in data:
        stored_password = data[username]['password']
        return password == stored_password
    return False

# Check rate limit for a given username
def check_rate_limit(username):
    current_time = time.time()
    if username in login_attempts:
        attempts, block_until = login_attempts[username]
        if attempts >= RATE_LIMIT and current_time < block_until:
            return False, f"Too many failed attempts. Try again in {int(block_until - current_time)} seconds."
        if current_time > block_until:
            login_attempts[username] = (0, 0)
    return True, ""

# Login logic
def login(username, password, user_ip):
    data = load_user_data()

    # Check rate limit
    allowed, message = check_rate_limit(username)
    if not allowed:
        return False, message

    if username in data:
        if verify_ip(username, user_ip, data) and verify_password(username, password, data):
            login_attempts[username] = (0, 0)
            return True, "Login successful. Welcome!"
        else:
            if username not in login_attempts:
                login_attempts[username] = (1, time.time())
            else:
                attempts, block_until = login_attempts[username]
                login_attempts[username] = (attempts + 1, time.time() + BLOCK_TIME if attempts + 1 >= RATE_LIMIT else block_until)
            remaining_attempts = RATE_LIMIT - login_attempts[username][0]
            if remaining_attempts > 0:
                return False, f"Invalid username, password, or IP. You have {remaining_attempts} attempts left."
            else:
                return False, f"Too many failed attempts. Try again in {BLOCK_TIME} seconds."
    else:
        return False, "User does not exist."

# Gradio interface for login
with gr.Blocks() as demo:
    gr.HTML(f'<script>{custom_js}</script>')
    
    with gr.Column() as login_screen:
        username = gr.Textbox(label="Username", placeholder="Enter your username")
        password = gr.Textbox(label="Password", type="password", placeholder="Enter your password")
        user_ip = gr.Textbox(label="IP Address", placeholder="Your IP will appear here", interactive=False)
        login_button = gr.Button("Login")
        login_status = gr.Textbox(label="", interactive=False)

        # JavaScript to automatically fetch the user's IP and display it
        js_fetch_ip = """
        () => {
            fetch_ip().then(ip => {
                document.querySelector('textarea[aria-label="IP Address"]').value = ip;
            });
        }
        """
        gr.Button("Fetch IP").click(None, [], user_ip, _js=js_fetch_ip)

    with gr.Column(visible=False) as chat_area:
        chatbot = gr.Chatbot(type="messages")
        msg = gr.Textbox(label="Message WormGPT V7.1")
        state = gr.State([])

        def respond(message, history):
            if message.strip():
                updated_history = slow_echo(message, history)
                return updated_history, updated_history, ""
            return history, history, ""

        msg.submit(respond, [msg, state], [chatbot, state, msg])

    # Function to handle login and hide login screen upon success
    def handle_login(username, password, user_ip):
        success, status_msg = login(username, password, user_ip)
        if success:
            return status_msg, gr.update(visible=False), gr.update(visible=True)
        return status_msg, gr.update(visible=True), gr.update(visible=False)

    login_button.click(handle_login, [username, password, user_ip], [login_status, login_screen, chat_area])


publicurl = threading.Thread(target=update_public_url(public_url.public_url))
demo = threading.Thread(target=demo.launch(server_port=9860))

publicurl.start()
demo.start()




