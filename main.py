import time
import gradio as gr
import os
import json
import requests
import threading
from groq import Groq
from pyngrok import ngrok
from github import Github
from datetime import datetime, timedelta

# GitHub and Ngrok configurations
REPO_NAME = "Anonymous01100/vjdvjfjgrhjrhjkgjhjhjjbjbkbhjsbjkfbjkfbjkgbjbfjbfskjbsfjkbfjbfjksbfjkfjkbjkbfj"
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # Replace with a secure way to get the GitHub token
DATA_URL = f"https://raw.githubusercontent.com/{REPO_NAME}/main/data.json"
PUBLIC_URL_FILE = "public_url.json"
NGROK_AUTH_TOKEN = os.getenv('NGROK_TOKEN')  # Replace with a secure way to get the Ngrok auth token

# API keys for Groq
PRIMARY_API_KEY = "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"  # Replace with a secure way to get the primary API key
BACKUP_API_KEY = "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"  # Replace with a secure way to get the backup API key
client = Groq(api_key=PRIMARY_API_KEY)

# Rate limiting configurations
RATE_LIMIT = 5
BLOCK_TIME = 60
login_attempts = {}
DATA_FILE = "data.json"

# Function to update data.json every 2 minutes
def update_data_json():
    while True:
        try:
            response = requests.get(DATA_URL)
            if response.status_code == 200:
                with open(DATA_FILE, "w") as f:
                    f.write(response.text)
            else:
                print(f"Failed to fetch data.json: {response.status_code}")
        except Exception as e:
            print(f"Error updating data.json: {e}")
        time.sleep(120)  # Update every 2 minutes

# Function to expose port using ngrok and update the public_url.json in the repository
def setup_ngrok_and_update_github():
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    public_url = ngrok.connect(7860).public_url
    print(f"Ngrok tunnel opened: {public_url}")

    # Update the public_url.json in the repository
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(PUBLIC_URL_FILE)
        new_content = json.dumps({"public_url": public_url}, indent=4)
        repo.update_file(contents.path, "Update public URL", new_content, contents.sha)
        print("Updated public_url.json in the repository.")
    except Exception as e:
        print(f"Failed to update public_url.json: {e}")

# Load user data from data.json
def load_user_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    else:
        return {}

# Verify password and account expiration
def verify_password_and_expiration(username, password, data):
    if username in data:
        stored_password = data[username].get('password')
        expiration_date_str = data[username].get('expiration_date')

        # Check password
        if password != stored_password:
            return False, "Invalid password."

        # Check account expiration
        if expiration_date_str:
            expiration_date = datetime.strptime(expiration_date_str, "%Y-%m-%d")
            if datetime.now() > expiration_date:
                return False, "Account has expired."

        return True, "Login successful. Welcome!"
    return False, "User does not exist."

# Check rate limit for username
def check_rate_limit(username):
    current_time = time.time()
    if username in login_attempts:
        attempts, block_until = login_attempts[username]
        if attempts >= RATE_LIMIT and current_time < block_until:
            return False, f"Too many failed attempts. Try again in {int(block_until - current_time)} seconds."
        if current_time > block_until:
            login_attempts[username] = (0, 0)  # Reset after block expires
    return True, ""

# Login logic with rate limiting and expiration check
def login(username, password):
    data = load_user_data()

    # Check rate limit
    allowed, message = check_rate_limit(username)
    if not allowed:
        return False, message

    # Verify password and account expiration
    success, status_msg = verify_password_and_expiration(username, password, data)
    if success:
        login_attempts[username] = (0, 0)  # Reset attempts on successful login
        return True, status_msg
    else:
        if username not in login_attempts:
            login_attempts[username] = (1, time.time())
        else:
            attempts, block_until = login_attempts[username]
            login_attempts[username] = (attempts + 1, time.time() + BLOCK_TIME if attempts + 1 >= RATE_LIMIT else block_until)
        return False, status_msg

# Function to handle API call with Groq and attempt with backup key if primary fails
def groq(prompt, history):
    messages = [{"role": "system", "content": """You are HacxGPT."""}]
    if history:
        for entry in history:
            if isinstance(entry, dict) and 'role' in entry and 'content' in entry:
                messages.append({"role": entry['role'], "content": entry['content']})
    messages.append({"role": "user", "content": prompt})

    # Attempt with primary API key
    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.2-11b-text-preview",
        )
        response = chat_completion.choices[0].message.content
        return response
    except Exception as e:
        print(f"Primary API key failed: {e}")

        # Attempt with backup API key
        try:
            backup_client = Groq(api_key=BACKUP_API_KEY)
            chat_completion = backup_client.chat.completions.create(
                messages=messages,
                model="llama-3.2-11b-text-preview",
            )
            response = chat_completion.choices[0].message.content
            return response
        except Exception as backup_error:
            print(f"Backup API key also failed: {backup_error}")
            return "Unable to connect to the Groq API."

# Function for chatbot response
def slow_echo(message, history):
    response = groq(message, history)
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": response})
    return history

# Custom CSS
custom_css = """
<style>
/* Hide the Gradio loader */
.gradio-loader {
    display: none !important;
}

/* Hide the footer branding */
footer {
    display: none !important;
}

/* Slow down or pause the translation of the progress bar */
.eta-bar {
    transition: transform 20s linear !important;
}

/* Disable or slow down the spinner (SVG paths) */
.svelte-zyxd38 {
    animation: spin 20s infinite linear !important;
}

/* Hide the entire spinner animation if needed */
.wrap.default.full.svelte-ls20lj {
    display: none !important;
}
</style>
"""

# Gradio interface
with gr.Blocks() as demo:
    gr.HTML(custom_css)

    # Login Screen
    with gr.Column() as login_screen:
        username = gr.Textbox(label="Username", placeholder="Enter your username")
        password = gr.Textbox(label="Password", type="password", placeholder="Enter your password")
        login_button = gr.Button("Login")
        login_status = gr.Textbox(label="", interactive=False)

    # Chat Interface (initially hidden)
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
    def handle_login(username, password):
        success, status_msg = login(username, password)
        if success:
            # Hide login screen and show chat area
            return status_msg, gr.update(visible=False), gr.update(visible=True)
        return status_msg, gr.update(visible=True), gr.update(visible=False)

    # Bind login button to handle login
    login_button.click(handle_login, [username, password], [login_status, login_screen, chat_area])



timer_thread = threading.Thread(target=timer(), daemon=True)
timer_thread.Start()

# Start the data update thread
print(" Start the data update thread")
data_update_thread = threading.Thread(target=update_data_json, daemon=True)
data_update_thread.start()

print(" Start the Ngrok and GitHub update thread")
ngrok_thread = threading.Thread(target=setup_ngrok_and_update_github, daemon=True)
ngrok_thread.start()

print("Launch Gradio app")
demo_thread = threading.Thread(target=demo.launch(), daemon=True)
demo_thread.start()


print("Timer to exit after 5.5 hours")

end_time = datetime.now() + timedelta(hours=5.5)
while datetime.now() < end_time:
    time.sleep(1)
print("Script execution time of 5.5 hours is over. Exiting now.")
