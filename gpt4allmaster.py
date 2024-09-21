import gradio as gr
from gpt4all import GPT4All
import uuid
import time
import logging
import json
import os


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize the GPT4All model with error handling
def initialize_model():
    model_path = r"Z:\This\This\Ai\AiRun\Gpt4all\Models\qwen2-7b-instruct-q4_0.gguf"
    try:
        model = GPT4All(model_path, device="amd")  # Always use CPU for consistency
        logging.info("Model initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize model: {str(e)}")
        raise
    return model

model = initialize_model()

# Dictionary to store chat histories for each user
user_chats = {}

# Folder to store user data
USER_DATA_FOLDER = "userdata"
os.makedirs(USER_DATA_FOLDER, exist_ok=True)

def save_user_chat(username, chat_history):
    file_path = os.path.join(USER_DATA_FOLDER, f"{username}.json")
    with open(file_path, 'w') as f:
        json.dump(chat_history, f)

def load_user_chat(username):
    file_path = os.path.join(USER_DATA_FOLDER, f"{username}.json")
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return []

def generate_response(message, history):
    try:
        with model.chat_session():
            response = model.generate(message, max_tokens=1024)
        return response
    except Exception as e:
        logging.error(f"Error generating response: {str(e)}")
        return "I'm sorry, but I encountered an error while processing your request. Please try again later."

# Custom CSS to make the interface look more like Claude
custom_css = """
.user {
    background-color: #38697c !important;
    padding: 15px;
    border-radius: 15px;
    margin-bottom: 10px;
}
.bot {
    background-color: #276619 !important;
    padding: 15px;
    border-radius: 15px;
    margin-bottom: 10px;
}
.message {
    font-size: 16px;
    line-height: 1.5;
}
"""

def user(user_message, history, username):
    if username not in user_chats:
        user_chats[username] = load_user_chat(username)
    user_chats[username] = history + [[user_message, None]]
    save_user_chat(username, user_chats[username])
    return "", user_chats[username]

def bot(history, username):
    user_message = history[-1][0]
    bot_message = generate_response(user_message, history)
    history[-1][1] = bot_message
    user_chats[username] = history
    save_user_chat(username, history)
    return history
# ... (previous code remains the same)

# Add this global variable at the top of your script
stop_generation = False

def generate_response(message, history):
    global stop_generation
    stop_generation = False
    try:
        with model.chat_session():
            response = ""
            for token in model.generate(message, max_tokens=1024, streaming=True):
                if stop_generation:
                    break
                response += token
        return response
    except Exception as e:
        logging.error(f"Error generating response: {str(e)}")
        return "I'm sorry, but I encountered an error while processing your request. Please try again later."

def stop_gen():
    global stop_generation
    stop_generation = True

# User Interface
def create_user_interface():
    with gr.Blocks(css=custom_css) as user_interface:
        gr.Markdown("# GPT4All Chatbot")
        username = gr.Textbox(placeholder="Enter your username", label="Username")
        chatbot = gr.Chatbot(elem_id="chatbot")
        msg = gr.Textbox(placeholder="Type your message here...", label="User Input")
        stop_btn = gr.Button("Stop Generating")
         
        # Load chat history for the user
        def load_chat_history(username):
            return load_user_chat(username)

        # Handle user input
        def user_msg(user_message, history, username):
            return user(user_message, history, username)

        # Handle bot response
        def bot_msg(history, username):
            return bot(history, username)

        # Assign input/output actions
        username.submit(load_chat_history, inputs=[username], outputs=[chatbot])
        msg.submit(user_msg, [msg, chatbot, username], [msg, chatbot]).then(
            bot_msg, [chatbot, username], chatbot
        )

        stop_btn.click(stop_gen)

    return user_interface

# ... (rest of the code remains the same)
# Master Interface
def create_master_interface():
    with gr.Blocks(css=custom_css) as master_interface:
        gr.Markdown("# Master View - GPT4All Chatbot Monitor")
        
        user_selector = gr.Dropdown(choices=[], label="Select User", interactive=True)
        master_chatbot = gr.Chatbot(elem_id="master_chatbot")
        refresh_button = gr.Button("Refresh User List")

        # Refresh user list
        def refresh_users():
            return gr.Dropdown.update(choices=list(user_chats.keys()))

        # Update chat history for selected user
        def update_master_view(selected_user):
            if selected_user in user_chats:
                return user_chats[selected_user]
            return []

        # Handle button and dropdown interactions
        refresh_button.click(refresh_users, outputs=[user_selector])
        user_selector.change(update_master_view, inputs=[user_selector], outputs=[master_chatbot])

    return master_interface

# Create and launch interfaces
user_interface = create_user_interface()
master_interface = create_master_interface()

# Launch user interface
user_interface.launch(server_name="127.0.0.1", server_port=7871, share=True)


# Launch master interface
master_interface.launch(server_name="127.0.0.1", server_port=7870)

