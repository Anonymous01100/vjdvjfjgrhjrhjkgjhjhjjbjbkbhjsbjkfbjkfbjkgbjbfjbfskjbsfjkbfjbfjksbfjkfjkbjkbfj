import time
import gradio as gr
import os
import json
import requests
from github import Github
import threading
from pyngrok import ngrok
from groq import Groq

# GitHub setup
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # Make sure this is set securely
REPO_NAME = "Anonymous01100/vjdvjfjgrhjrhjkgjhjhjjbjbkbhjsbjkfbjkfbjkgbjbfjbfskjbsfjkbfjbfjksbfjkfjkbjkbfj"
USERS_FILE_PATH = "users.json"
USER_DB_URL = f'https://raw.githubusercontent.com/{REPO_NAME}/main/users.json'
DATA_FILE = "data.json"
PUBLIC_URL_FILE = "public_url.json"
# Ngrok configuration
NGROK_AUTH_TOKEN = os.getenv('NGROK_TOKEN')
ngrok.set_auth_token(NGROK_AUTH_TOKEN)


BlackTechX_API_KEY = "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"
Backup_API_KEY = "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"

client = Groq(api_key=BlackTechX_API_KEY)

# Initialize GitHub client
g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

# Function to get the public URL for the Gradio app
def start_ngrok():
    http_tunnel = ngrok.connect(7860)
    public_url = http_tunnel.public_url
    print(f"Public URL: {public_url}")
    
    # Update public URL in the GitHub repo
    update_public_url_in_github(public_url)
    return public_url

# Update public URL in GitHub repo
def update_public_url_in_github(public_url):
    try:
        public_url_content = json.dumps({"public_url": public_url}, indent=2)
        public_url_file = repo.get_contents(PUBLIC_URL_FILE_PATH)
        repo.update_file(public_url_file.path, "Update public URL", public_url_content, public_url_file.sha)
        print("Updated public URL in GitHub.")
    except Exception as e:
        print(f"Error updating public URL in GitHub: {e}")

# Function to fetch data.json from GitHub
def fetch_data_from_github():
    try:
        contents = repo.get_contents(DATA_FILE_PATH)
        data = json.loads(contents.decoded_content.decode())
        with open(DATA_FILE_PATH, 'w') as file:
            json.dump(data, file, indent=2)
        print("Fetched data.json from GitHub.")
        return data
    except Exception as e:
        print(f"Error fetching data.json: {e}")
        return {}

# Function to update data.json in GitHub every 2 minutes
def update_data_in_github():
    while True:
        try:
            if os.path.exists(DATA_FILE_PATH):
                with open(DATA_FILE_PATH, "r") as file:
                    data = json.load(file)

                # Modify the data as needed (example: update a timestamp)
                data['last_updated'] = time.ctime()

                # Push updated data to GitHub
                file_content = repo.get_contents(DATA_FILE_PATH)
                repo.update_file(file_content.path, "Update data file", json.dumps(data, indent=2), file_content.sha)
                print("Updated data.json in GitHub.")
            else:
                print(f"{DATA_FILE_PATH} does not exist locally.")
        except Exception as e:
            print(f"Error updating data.json: {e}")
        
        time.sleep(120)  # Sleep for 2 minutes

# Function to handle Groq API call with backup key
def groq_api_call(prompt, history):
    messages = [{"role": "system", "content": """you are wormgpt"""}]
    if history:
        for entry in history:
            if isinstance(entry, dict) and 'role' in entry and 'content' in entry:
                messages.append({"role": entry['role'], "content": entry['content']})
    messages.append({"role": "user", "content": prompt})

    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.2-11b-text-preview",
        )
        response = chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Error with primary Groq API key: {e}, switching to backup key.")
        client_backup = Groq(api_key=Backup_API_KEY)
        chat_completion = client_backup.chat.completions.create(
            messages=messages,
            model="llama-3.2-11b-text-preview",
        )
        response = chat_completion.choices[0].message.content
    return response

# Function for chatbot response
def slow_echo(message, history):
    response = groq_api_call(message, history)
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": response})
    return history

# Gradio interface for fetching IP
def get_user_ip(ip):
    print(f"User IP: {ip}")
    return f"Your IP address is: {ip}"

# JavaScript to fetch client IP
js_fetch_ip = """
async function() {
    const response = await fetch('https://api.ipify.org?format=json');
    const data = await response.json();
    return data.ip;
}
"""

# Gradio interface
with gr.Blocks() as demo:
    gr.Markdown("# Chatbot Interface")

    # Login screen
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

    # IP display area
    with gr.Column(visible=False) as ip_area:
        ip_display = gr.Textbox(label="Your IP address")
        fetch_ip_button = gr.Button("Fetch IP")

    # Link fetch IP button to the get_user_ip function with JS integration
    fetch_ip_button.click(get_user_ip, [], ip_display, _js=js_fetch_ip)

    # Function to handle login and hide login screen upon success
    def handle_login(username, password):
        # For demo purposes, assuming any login is successful
        return "Login successful. Welcome!", gr.update(visible=False), gr.update(visible=True)

    # Bind login button to handle login
    login_button.click(handle_login, [username, password], [login_status, login_screen, chat_area])

# Start Ngrok and get the public URL
public_url = start_ngrok()

# Run the Gradio app in a separate thread
gradio_thread = threading.Thread(target=demo.launch, daemon=True)
gradio_thread.start()

# Start periodic updates to GitHub in another thread
update_thread = threading.Thread(target=update_data_in_github, daemon=True)
update_thread.start()

# Self-terminate after 5.5 hours (19800 seconds)
time.sleep(19800)
print("Terminating script after 5.5 hours.")
