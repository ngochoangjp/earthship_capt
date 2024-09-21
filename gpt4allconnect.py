import logging
from gpt4all import GPT4All
import json
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Folder to store user data
USER_DATA_FOLDER = "userdata"
os.makedirs(USER_DATA_FOLDER, exist_ok=True)

# Global variables
model = None
user_chats = {}
stop_generation = False

def initialize_model():
    global model
    model_path = r"Z:\This\This\Ai\AiRun\Gpt4all\Models\qwen2-7b-instruct-q4_0.gguf"
    try:
        model = GPT4All(model_path, device="gpu")  # Always use CPU for consistency
        logging.info("Model initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize model: {str(e)}")
        raise

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

def user_message(user_message, history, username):
    if username not in user_chats:
        user_chats[username] = load_user_chat(username)
    user_chats[username] = history + [[user_message, None]]
    save_user_chat(username, user_chats[username])
    return "", user_chats[username]

def bot_message(history, username):
    user_message = history[-1][0]
    bot_message = generate_response(user_message, history)
    history[-1][1] = bot_message
    user_chats[username] = history
    save_user_chat(username, history)
    return history

def get_all_users():
    return list(user_chats.keys())

def get_user_chat(username):
    return user_chats.get(username, [])
