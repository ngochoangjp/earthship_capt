import gradio as gr
import ollama
import uuid
import time
import logging
import json
import os
import base64
import random
from pathlib import Path
import requests
from googlesearch import search
from datetime import datetime
import bcrypt  # For password hashing

# Import prompts from prompts.py
from prompts import PERSONALITIES, EXAMPLE_RESPONSES, PREMADE_PROMPTS

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DEFAULT_PASSWORD = "admin"
# Available Ollama Models
MODEL_DISPLAY_NAMES = {
    "Vietai": "Tuanpham/t-visstar-7b:latest",
    "codegpt": "marco-o1",
    "Llama 2": "llama2",
    "CodeLlama": "codellama"
}

# Technical model names for Ollama
AVAILABLE_MODELS = {
    model_tech: model_tech for model_tech in [
        "Tuanpham/t-visstar-7b:latest",
        "marco-o1",
        "llama2",
        "codellama"
    ]
}
# Global variable to store user chats
# This is not really needed anymore with the improved file handling
# user_chats = {}

# Internet connectivity settings
INTERNET_ENABLED = False
CITATION_ENABLED = False
# Security: Hash passwords
# User data folder
USER_DATA_FOLDER = "user_data"
os.makedirs(USER_DATA_FOLDER, exist_ok=True)

# Password hashing functions (using bcrypt)

def hash_password(password):
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    # Encode to Base64 string
    hashed_password_string = base64.b64encode(hashed_password).decode('utf-8')
    return hashed_password_string  # Return the string


def verify_password(password, hashed_password_string):
    hashed_password_bytes = base64.b64decode(hashed_password_string.encode('utf-8'))
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password_bytes)



# --- API Key Handling (for Google Custom Search, etc.) ---
def read_api_keys():
    try:
        with open('API_KEY.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
            api_keys = {}
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=')
                    api_keys[key] = value
            return api_keys
    except FileNotFoundError:
        logging.warning("API_KEY.txt not found. Internet search and some features may not work.")
        return {}
    except Exception as e:
        logging.error(f"Error reading API keys: {e}")
        return {}


api_keys = read_api_keys()
GOOGLE_CSE_ID = api_keys.get('Google_CSE_ID', '').split('cx=')[-1] if 'Google_CSE_ID' in api_keys else ""
OSHO_GOOGLE_CSE_ID = api_keys.get('Osho_Google_CSE_ID', '').split('cx=')[-1] if 'Osho_Google_CSE_ID' in api_keys else ""


# Global variable to control generation
stop_generation = False

# Folder to store user data
USER_DATA_FOLDER = "user_data"
os.makedirs(USER_DATA_FOLDER, exist_ok=True)


def get_user_folder(username):
    """Get or create user's data folder"""
    user_folder = os.path.join(USER_DATA_FOLDER, username)
    os.makedirs(user_folder, exist_ok=True)
    return user_folder


def create_new_chat(username, title="Cuộc trò chuyện mới"):
    """Create a new chat session with optional title"""
    user_folder = get_user_folder(username)
    chat_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    chat_file = os.path.join(user_folder, f"chat_{timestamp}_{chat_id[:8]}.json")

    chat_data = {
        "id": chat_id,
        "timestamp": timestamp,
        "title": title,  # Use provided title
        "messages": []
    }

    with open(chat_file, "w", encoding="utf-8") as f:
        json.dump(chat_data, f, ensure_ascii=False, indent=2)

    return chat_id, chat_file


def get_user_chats(username):
    """Get list of user's chat sessions"""
    user_folder = get_user_folder(username)
    chat_files = []
    try:
        for file in os.listdir(user_folder):
            # Only process files that start with 'chat_' and end with '.json'
            if file.startswith("chat_") and file.endswith(".json"):
                file_path = os.path.join(user_folder, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        chat_data = json.load(f)
                        # Ensure required keys exist
                        if all(key in chat_data for key in ["id", "title", "timestamp"]):
                            chat_files.append({
                                "id": chat_data["id"],
                                "title": chat_data["title"],
                                "timestamp": chat_data["timestamp"],
                                "filename": file
                            })
                except json.JSONDecodeError:
                    logging.error(f"Error decoding JSON in file: {file}")
                except KeyError as e:
                    logging.error(f"Missing key in chat file {file}: {e}")
                except Exception as e:
                    logging.error(f"Error loading chat history: {e}")

        return sorted(chat_files, key=lambda x: x["timestamp"], reverse=True)
    except FileNotFoundError:
        return []  # Return empty list if user folder doesn't exist


def save_chat_message(username, chat_id, message, response):
    """Save chat message to specific chat file and update user chat history"""
    user_folder = get_user_folder(username)
    chat_files = [f for f in os.listdir(user_folder) if f.endswith(".json") and "chat_" in f]

    # Find the matching chat file
    matching_file = None
    for file in chat_files:
        file_path = os.path.join(user_folder, file)
        with open(file_path, "r", encoding="utf-8") as f:
            chat_data = json.load(f)
            if chat_data["id"] == chat_id:
                matching_file = file_path
                break

    # If no matching file found, create a new one
    if not matching_file:
        chat_id, matching_file = create_new_chat(username)
    
    # Load and update chat data
    with open(matching_file, "r", encoding="utf-8") as f:
        chat_data = json.load(f)

    # Add message to chat data
    chat_data["messages"].append({
        "user": message,
        "assistant": response,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    # Update chat title if it's the first message and no title was explicitly set
    if len(chat_data["messages"]) == 1 and chat_data["title"] == "Cuộc trò chuyện mới":
        chat_data["title"] = (message[:30] + "...") if len(message) > 30 else message

    # Save updated chat data
    with open(matching_file, "w", encoding="utf-8") as f:
        json.dump(chat_data, f, ensure_ascii=False, indent=2)

    return chat_id


def load_chat_history(username, chat_id):
    """Load messages from specific chat"""
    user_folder = get_user_folder(username)
    chat_files = [f for f in os.listdir(user_folder) if f.startswith("chat_") and f.endswith(".json")]

    for file in chat_files:
        file_path = os.path.join(user_folder, file)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                chat_data = json.load(f)
                if chat_data.get("id") == chat_id:
                    # Ensure messages exist and are in the correct format
                    messages = chat_data.get("messages", [])
                    return [(msg.get("user", ""), msg.get("assistant", "")) for msg in messages]
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Error loading chat file {file}: {e}")

    return []

def load_user_data(username):
    """Load user data from file"""
    user_folder = get_user_folder(username)
    user_data_file = os.path.join(user_folder, "user_data.json")

    if os.path.exists(user_data_file):
        try:
            with open(user_data_file, 'r', encoding='utf-8') as f:
                user_data = json.load(f)

                # Check and correct the password if it's not base64 encoded
                if "password" in user_data and not isinstance(user_data['password'], bytes) and '$2b$' not in user_data['password']:
                    user_data['password'] = hash_password(user_data['password'])
                    save_user_data(username, user_data)  # Save updated user data
                return user_data
        except Exception as e:
            logging.error(f"Error loading user data: {e}")
    return {}



def save_user_data(username, user_data):
    """Save user data to file"""
    user_folder = get_user_folder(username)
    user_data_file = os.path.join(user_folder, "user_data.json")

    with open(user_data_file, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

# Define custom CSS
custom_css = """
.message {
padding: 10px;
margin: 5px;
border-radius: 10px;
}
.user-message {
background-color: #e3f2fd;
text-align: right;
}
.bot-message {
background-color: #f5f5f5;
text-align: left;
}
"""

def load_chat_history_list(login_info):
    """Load list of user's chat sessions"""
    if not login_info.get("logged_in", False):
        return gr.update(choices=[], visible=False), None  # Also return None for current_chat_id

    title = f"Cuộc trò chuyện với {personality}" if personality else "Cuộc trò chuyện mới"  # Improved title handling
    chat_id, _ = create_new_chat(login_info["username"], title=title)
    chats = get_user_chats(login_info["username"])
    
    # Create choices with chat ID and title
    chat_choices = [[chat["id"], f"{chat['title']} ({chat['timestamp']})"] for chat in chats]

    return gr.update(
        choices=chat_choices,
        visible=True
    ), [], chat_id  # Return None when loading history list



def load_selected_chat(login_info, selected_chat, current_chat_id):
    """Load messages from a selected chat session, updating current_chat_id"""
    if not login_info.get("logged_in", False) or not selected_chat:
        return [], None  # Return empty history and None for chat_id

    chat_id = selected_chat[0] if isinstance(selected_chat, list) else selected_chat
    
    current_chat_id = chat_id  # Update the current_chat_id state
    return load_chat_history(login_info["username"], chat_id), current_chat_id
def create_new_chat(username, title="Cuộc trò chuyện mới"):
    """Create a new chat session with optional title"""
    user_folder = get_user_folder(username)
    chat_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    chat_file = os.path.join(user_folder, f"chat_{timestamp}_{chat_id[:8]}.json")

    chat_data = {
        "id": chat_id,
        "timestamp": timestamp,
        "title": title,  # Use provided title
        "messages": []
    }

    with open(chat_file, "w", encoding="utf-8") as f:
        json.dump(chat_data, f, ensure_ascii=False, indent=2)

    return chat_id, chat_file


def create_user_interface():
    with gr.Blocks(css=custom_css) as interface:
        gr.Markdown("# Earthship AI")
        login_info = gr.State({"username": "", "password": "", "logged_in": False, "is_admin": False})
        # Enable Gradio's built-in queue
        interface.queue(
            default_concurrency_limit=5,
            max_size=20,
            api_open=True
        )
        # State for current chat ID
        current_chat_id = gr.State(None)  # Initialize as None
        chat_history_list = gr.Dropdown(
            label="Lịch sử trò chuyện",
            choices=[],
            visible=False,
            interactive=True
        )
        # Correct the chat_history_list.change outputs
        chatbot = gr.Chatbot(elem_id="chatbot", height=500, show_label=False)
        current_chat_id = gr.State(None)
        login_info = gr.State({"logged_in": False})  # Simplified login_info
        chat_history_list = gr.Dropdown(label="Lịch sử trò chuyện", choices=[], visible=False, interactive=True)
        new_chat_button = gr.Button("Tạo cuộc trò chuyện mới")
        history_button = gr.Button("📜 Lịch sử")
        msg = gr.Textbox(label="Nhập câu hỏi của bạn", placeholder="Nhập câu hỏi của bạn tại đây...")
        # Now that chatbot is defined, we can add the change handler
        chat_history_list.change(
            fn=load_selected_chat,
            inputs=[login_info, chat_history_list, current_chat_id],
            outputs=[chatbot, current_chat_id]
        )

        new_chat_button.click(
            fn=create_new_chat_and_update,
            inputs=login_info,
            outputs=[chat_history_list, chatbot, current_chat_id]
        )
        
        current_chat_id = gr.State(None)
        # State for chat settings
        chat_settings = gr.State({"use_internet": False, "show_citations": False})
        
        # Add avatar components
        user_avatar = gr.Image(label="User Avatar", type="filepath", visible=False)
        bot_avatar = gr.Image(label="Bot Avatar", type="filepath", visible=False)
        
        # Login interface
        login_container = gr.Column(visible=True)
        with login_container:
            gr.Markdown("## Đăng nhập")
            username = gr.Textbox(label="Tên đăng nhập", placeholder="Nhập tên đăng nhập")
            password = gr.Textbox(label="Mật khẩu", placeholder="Nhập mật khẩu", type="password")
            with gr.Row():
                login_button = gr.Button("Đăng nhập", variant="primary")
                create_user_button = gr.Button("Tạo người dùng mới")
            login_message = gr.Markdown(visible=False)

        # Admin interface (initially hidden)
        admin_container = gr.Column(visible=False)
        with admin_container:
            gr.Markdown("## Captain View")
            with gr.Row():
                user_selector = gr.Dropdown(choices=[], label="Select User", interactive=True)
                refresh_button = gr.Button("Refresh User List")
            admin_chatbot = gr.Chatbot(elem_id="admin_chatbot", height=500)
        # Chatbot
        chatbot = gr.Chatbot(elem_id="chatbot", height=500, show_label=False)
        current_chat_id = gr.State(None)
        login_info = gr.State({"logged_in": False})  # Simplified login_info
        chat_history_list = gr.Dropdown(label="Lịch sử trò chuyện", choices=[], visible=False, interactive=True)
        new_chat_button = gr.Button("Tạo cuộc trò chuyện mới")  # New chat button
        history_button = gr.Button("📜 Lịch sử")
        msg = gr.Textbox(label="Nhập câu hỏi của bạn", placeholder="Nhập câu hỏi của bạn tại đây...")  # Move msg here
        submit = gr.Button("Gửi")
        # ... other components like personality, model, internet_toggle, citation_toggle


        # chat_container (Simplified)
        chat_container = gr.Column(visible=False)
        with chat_container:
            with gr.Row():
                # Left column for user profile
                with gr.Column(scale=1):
                    gr.Markdown("## Thông tin cá nhân")
                    real_name = gr.Textbox(label="Họ và tên", placeholder="Nhập họ tên của bạn")
                    age = gr.Number(label="Tuổi")
                    gender = gr.Radio(choices=["Nam", "Nữ", "Khác"], label="Giới tính")
                    height = gr.Number(label="Chiều cao (cm)")
                    weight = gr.Number(label="Cân nặng (kg)")
                    education = gr.Textbox(label="Trình độ học vấn", placeholder="Nhập trình độ học vấn")
                    interests = gr.TextArea(label="Sở thích", placeholder="Nhập sở thích của bạn")
                    treatment = gr.TextArea(label="Cách đối xử mong muốn", placeholder="Bạn muốn AI đối xử với bạn như thế nào?")
                    save_profile = gr.Button("Lưu thông tin", variant="primary")

                # Right column for chat
                with gr.Column(scale=3):
                    # Top controls
                    with gr.Row():
                        with gr.Column(scale=3):
                            with gr.Row():
                                personality = gr.Dropdown(
                                    choices=list(PERSONALITIES.keys()),
                                    value="Trợ lý",
                                    label="Chọn tính cách AI",
                                    interactive=True
                                )
                                model = gr.Dropdown(
                                    choices=list(MODEL_DISPLAY_NAMES.keys()),
                                    value="Vietai",
                                    label="Chọn mô hình AI",
                                    interactive=True
                                )
                        with gr.Column(scale=1):
                            with gr.Row():
                                internet_toggle = gr.Checkbox(
                                    label="Kết nối Internet",
                                    value=False,
                                    interactive=True,
                                    visible=True
                                )
                                citation_toggle = gr.Checkbox(
                                    label="Hiển thị nguồn trích dẫn",
                                    value=False,
                                    interactive=True,
                                    visible=True
                                )
                         
                    
                
                    

            # NOW you can use login_info because it's defined
            chat_history_list.change(
                fn=load_selected_chat,
                inputs=[login_info, chat_history_list, current_chat_id],
                outputs=[chatbot, current_chat_id]
            )              
                    
            # Prompt input
            msg = gr.Textbox(
                label="Nhập câu hỏi của bạn", 
                placeholder="Nhập câu hỏi của bạn tại đây..."
            )
                    
            # Bottom row for buttons
            with gr.Row():
                with gr.Column(scale=3):
                    submit = gr.Button("Gửi")
                    chat_history_list = gr.Dropdown(label="Lịch sử trò chuyện", choices=[], visible=False, interactive=True)
                    new_chat_button = gr.Button("Tạo cuộc trò chuyện mới")  # New chat button
                    history_button = gr.Button("📜 Lịch sử")
                    personality.change(fn=lambda x, y: create_new_chat_and_update(y, x), inputs=[personality, login_info], outputs=[chat_history_list, chatbot, current_chat_id])
            
        # Premade prompts section
            gr.Markdown("### Thư viện công cụ")
            with gr.Row():
                prompt_buttons = [gr.Button(prompt_name) for prompt_name in PREMADE_PROMPTS.keys()]
        # State for login info
            login_info = gr.State({"username": "", "password": "", "logged_in": False, "is_admin": False})
        # Add click handlers for login and create user buttons
        login_button.click(
            fn=login,
            inputs=[username, password],
            outputs=[
                login_container,  # login container
                chat_container,   # chat container
                admin_container,  # admin container
                login_info,      # login info state
                chatbot,         # chatbot
                user_avatar,     # user avatar
                bot_avatar,      # bot avatar
                login_message,   # login message
                user_selector,   # user list for admin
            ]
        )

        create_user_button.click(
            fn=create_new_user,
            inputs=[username, password],
            outputs=[
                login_container,  # login container
                chat_container,   # chat container
                admin_container,  # admin container
                login_info,      # login info state
                chatbot,         # chatbot
                user_avatar,     # user avatar
                bot_avatar,      # bot avatar
                login_message,   # login message
                user_selector,   # user list for admin
            ]
        )

        # Add handlers for chat functionality
        submit.click(
            fn=user_msg,
            inputs=[msg, chatbot, login_info],
            outputs=[msg, chatbot]
        ).then(
            fn=bot_response,
            inputs=[chatbot, login_info, personality, model],
            outputs=chatbot
        )

        
        history_button.click(
            fn=load_chat_history_list,
            inputs=[login_info],
            outputs=[chat_history_list, current_chat_id] # Update current_chat_id here
        )

        personality.change(
            fn=lambda x, y: create_new_chat_and_update(y, x),  # Pass personality value
            inputs=[personality, login_info],
            outputs=[chat_history_list, chatbot, current_chat_id]  # Update chat list and clear chatbot
        )
        chat_history_list.change(
            fn=load_selected_chat,
            inputs=[login_info, chat_history_list],
            outputs=chatbot
        )

        # Add handlers for premade prompts
        for button, prompt_name in zip(prompt_buttons, PREMADE_PROMPTS.keys()):
            button.click(
                fn=lambda x: PREMADE_PROMPTS[x],
                inputs=[gr.State(prompt_name)],
                outputs=[msg]
            )

        # Add handlers for toggles
        internet_toggle.change(fn=toggle_internet, inputs=[internet_toggle])
        citation_toggle.change(fn=toggle_citation, inputs=[citation_toggle])

        # Add handler for saving profile
        save_profile.click(
            fn=save_profile_info,
            inputs=[real_name, age, gender, height, weight, education, interests, treatment, login_info],
            outputs=[login_message]
        )

        # Add handler for admin refresh
        refresh_button.click(fn=refresh_users, outputs=[user_selector])
        user_selector.change(fn=update_admin_view, inputs=[user_selector], outputs=[admin_chatbot])

    return interface
# Helper function to create chat and update components:
def create_new_chat_and_update(login_info):
    """Helper function to create chat, update components, and return new chat_id"""
    if not login_info.get("logged_in", False):
        return gr.update(choices=[], visible=False), [], None

    title = "Cuộc trò chuyện mới"
    if personality:
        title = f"Cuộc trò chuyện với {personality}"

    chat_id, chat_file = create_new_chat(login_info["username"], title=title)
    chats = get_user_chats(login_info["username"])
    chat_choices = [[chat["id"], f"{chat['title']} ({chat['timestamp']})"] for chat in chats]
    updated_chat_list = gr.update(choices=chat_choices, visible=True)
    return updated_chat_list, [], chat_id


def save_profile_info(real_name, age, gender, height, weight, education, interests, treatment, login_info):
    if not login_info["logged_in"]:
        return
    
    # Convert numeric values properly
    try:
        height = float(height) if height else None
        weight = float(weight) if weight else None
        age = int(age) if age else None
    except (ValueError, TypeError):
        height = None
        weight = None
        age = None
    
    username = login_info["username"]
    user_data = load_user_data(username)
    if user_data:
        user_data["profile"] = {
            "real_name": real_name,
            "age": age,
            "gender": gender,
            "height": height,
            "weight": weight,
            "education": education,
            "interests": interests,
            "treatment_preference": treatment
        }
        save_user_data(username, user_data)
        return "Profile saved successfully"

def load_profile_info(login_info):
    if not login_info["logged_in"]:
        return [gr.update(value="") for _ in range(8)]
    
    username = login_info["username"]
    user_data = load_user_data(username)
    if user_data and "profile" in user_data:
        profile = user_data["profile"]
        return [
            profile.get("real_name", ""),
            profile.get("age", ""),
            profile.get("gender", ""),
            profile.get("height", ""),
            profile.get("weight", ""),
            profile.get("education", ""),
            profile.get("interests", ""),
            profile.get("treatment_preference", "")
        ]
    return [gr.update(value="") for _ in range(8)]

def generate_response(message, history, personality, ollama_model, login_info):
    global stop_generation
    stop_generation = False
    try:
        response = ""
        personality_prompt = PERSONALITIES.get(personality, "")
        
        # Get an example response for the selected personality
        if personality in EXAMPLE_RESPONSES:
            example = random.choice(EXAMPLE_RESPONSES[personality])
            personality_prompt = f"""
{personality_prompt}

<div class="g3mark-callout g3mark-callout-important">
<span class="g3mark-callout__icon" aria-hidden="true"></span>
<span class="g3mark-callout__keyword">IMPORTANT:</span> You must follow these rules in your responses:

</div>
Always maintain the personality and speaking style shown in the example below

Include emotional expressions and actions in parentheses like in the example

Use similar language patterns and mannerisms

Keep the same level of formality and tone

Duy trì xưng hô đã được hướng dẫn, không thay đổi xưng hô trong hội thoại

Example response style to follow:
{example}

Remember: Your every response must follow this style exactly, including the emotional expressions and actions in parentheses.
"""
        
        # Add user profile information to system message
        if login_info["logged_in"]:
            user_data = load_user_data(login_info["username"])
            if user_data and "profile" in user_data:
                profile = user_data["profile"]
                # Convert numeric values to strings with proper handling
                height = str(profile.get('height', '')) if profile.get('height') is not None else ''
                weight = str(profile.get('weight', '')) if profile.get('weight') is not None else ''
                age = str(profile.get('age', '')) if profile.get('age') is not None else ''
                
                profile_info = f"""
Thông tin người dùng:

Tên: {profile.get('real_name', '')}

Tuổi: {age}

Giới tính: {profile.get('gender', '')}

Chiều cao: {height} cm

Cân nặng: {weight} kg

Học vấn: {profile.get('education', '')}

Sở thích: {profile.get('interests', '')}

Cách đối xử mong muốn: {profile.get('treatment_preference', '')}
""".encode('utf-8').decode('utf-8')
                personality_prompt = f"{personality_prompt}\n{profile_info}"
        
        # Create the conversation history
        messages = []
        messages.append({
            'role': 'system',
            'content': personality_prompt
        })
        
        # Check if the message is from a premade prompt
        current_prompt = None
        for prompt_name, prompt_data in PREMADE_PROMPTS.items():
            if prompt_data["user"] in message:
                current_prompt = prompt_data
                break
        
        if current_prompt:
            # Add the system prompt for the premade prompt
            messages.append({
                'role': 'system',
                'content': current_prompt["system"]
            })
            # Remove the instruction text from the user's message
            message = message.replace(current_prompt["user"], "").strip()
        
        # Add conversation history
        if history:
            for user_msg, assistant_msg in history:
                if user_msg:
                    messages.append({
                        'role': 'user',
                        'content': user_msg
                    })
                if assistant_msg:
                    messages.append({
                        'role': 'assistant',
                        'content': assistant_msg
                    })
        
        # Add current message
        messages.append({
            'role': 'user',
            'content': message
        })
        
        # Generate response using ollama.chat
        progress = gr.Progress()
        for chunk in ollama.chat(
            model=AVAILABLE_MODELS[ollama_model],
            messages=messages,
            stream=True
        ):
            if stop_generation:
                break
            if 'message' in chunk:
                response += chunk['message']['content']
                yield response.encode('utf-8').decode('utf-8')
    
    except Exception as e:
        logging.error(f"Error generating response: {str(e)}")
        yield "Xin lỗi, nhưng tôi đã gặp lỗi trong khi xử lý yêu cầu của bạn. Vui lòng thử lại."
def load_chat_history_list(login_info):
    """Load list of user's chat sessions, fixing history functionality"""
    if not login_info.get("logged_in", False):
        return gr.update(choices=[], visible=False), None

    chats = get_user_chats(login_info["username"])
    chat_choices = [[chat["id"], f"{chat['title']} ({chat['timestamp']})"] for chat in chats]

    return gr.update(choices=chat_choices, visible=True), None #Added None




def load_selected_chat(login_info, selected_chat, current_chat_id):  # Add current_chat_id
    """Load messages from a selected chat session"""
    if not login_info.get("logged_in", False) or not selected_chat:
        return [], None  # Return empty history and None for chat_id

    chat_id = selected_chat[0] if isinstance(selected_chat, list) else selected_chat
    chat_history = load_chat_history(login_info["username"], chat_id)
    return chat_history, chat_id # Return the chat_id



def user_msg(user_message, history, login_info, current_chat_id):  # Add current_chat_id as input
    if not login_info.get("logged_in", False):
        return "Vui lòng đăng nhập trước khi gửi tin nhắn.", history, None

    if not user_message or not user_message.strip():
        return "", history, current_chat_id # Don't change history or chat_id for empty messages


    history.append([user_message, None])
    return "", history, current_chat_id  # Return current_chat_id unchanged




def bot_response(history, login_info, personality, model, current_chat_id):
    if not history or not login_info.get("logged_in", False):
        return history or []  # Return current history if empty or not logged in

    user_message = history[-1][0]
    bot_message = ""

    try:
        ollama_model = MODEL_DISPLAY_NAMES.get(model, model)
        for chunk in generate_response(user_message, history[:-1], personality, ollama_model, login_info):
            bot_message = chunk  # Update the full bot message
            history[-1][1] = bot_message  # Update the bot's response in history
            # Important: Save the message after EACH chunk
            save_chat_message(login_info["username"], current_chat_id, user_message, bot_message)
            yield history  # Yield updated history for each chunk


    except Exception as e:
        logging.error(f"Error in bot_response: {str(e)}")
        error_message = "Xin lỗi, đã xảy ra lỗi khi xử lý yêu cầu của bạn. Vui lòng thử lại."
        history[-1][1] = error_message  # Update with error message
        yield history



def stop_gen():
    global stop_generation
    stop_generation = True

def update_admin_view(selected_user):
    if selected_user:
        user_data = load_user_data(selected_user)
        return user_data.get("chat_history", [])
    return []

def refresh_users():
    user_files = os.listdir(USER_DATA_FOLDER)
    user_names = [os.path.splitext(f)[0] for f in user_files if os.path.isdir(os.path.join(USER_DATA_FOLDER, f))]
    return gr.update(choices=user_names)  # Use gr.update to update the dropdown choices




def login(username, password):
    """Handle user login with simple password comparison"""
    try:
        user_folder = get_user_folder(username)
        user_data_file = os.path.join(user_folder, "user_data.json")
        
        if not os.path.exists(user_data_file):
            return (
                gr.Column(visible=True),  # login container
                gr.Column(visible=False),  # chat container
                gr.Column(visible=False),  # admin container
                {"username": "", "password": "", "logged_in": False, "is_admin": False},  # login info
                [],  # chatbot
                None,  # user avatar
                None,  # bot avatar
                gr.Markdown("User not found", visible=True),  # login message
                []  # user list for admin
            )

        with open(user_data_file, 'r', encoding='utf-8') as f:
            user_data = json.load(f)

        stored_password = user_data.get("password", "")
        
        if password == stored_password:  # Simple password comparison
            is_admin = (username == "admin")
            login_info = {
                "username": username,
                "password": password,
                "logged_in": True,
                "is_admin": is_admin
            }
            
            return (
                gr.Column(visible=False),  # login container
                gr.Column(visible=True),   # chat container
                gr.Column(visible=is_admin),  # admin container
                login_info,  # login info
                [],  # chatbot
                None,  # user avatar
                None,  # bot avatar
                gr.Markdown("Login successful!", visible=True),  # login message
                refresh_users() if is_admin else []  # user list for admin
            )
        else:
            return (
                gr.Column(visible=True),  # login container
                gr.Column(visible=False),  # chat container
                gr.Column(visible=False),  # admin container
                {"username": "", "password": "", "logged_in": False, "is_admin": False},  # login info
                [],  # chatbot
                None,  # user avatar
                None,  # bot avatar
                gr.Markdown("Incorrect password", visible=True),  # login message
                []  # user list for admin
            )
    except Exception as e:
        logging.error(f"Login error: {e}")
        return (
            gr.Column(visible=True),  # login container
            gr.Column(visible=False),  # chat container
            gr.Column(visible=False),  # admin container
            {"username": "", "password": "", "logged_in": False, "is_admin": False},  # login info
            [],  # chatbot
            None,  # user avatar
            None,  # bot avatar
            gr.Markdown(f"Login error: {str(e)}", visible=True),  # login message
            []  # user list for admin
        )
def user_msg(user_message, history, login_info):
    if not login_info.get("logged_in", False):
        return "Vui lòng đăng nhập trước khi gửi tin nhắn.", history
    
    history = history or []
    
    if not user_message or not user_message.strip():
        return "", history  # Return without changing history if the message is empty
    
    history.append([user_message, None])  # Add user message as a list of [user_message, None]
    return "", history

def bot_response(history, login_info, personality, model):
    if not history:
        return history or []

    user_message = history[-1][0]
    bot_message = ""
    try:
        # Convert display name to technical model name if it exists in mapping
        ollama_model = MODEL_DISPLAY_NAMES.get(model, model)
        for chunk in generate_response(user_message, history[:-1], personality, ollama_model, login_info):
            new_content = chunk[len(bot_message):]  # Get only the new content
            bot_message = chunk  # Update the full bot message
            history[-1][1] = bot_message  # Update the bot's response in history
            yield history
    
        user_data = load_user_data(login_info["username"])
        user_data["chat_history"] = history
        save_user_data(login_info["username"], user_data)
    except Exception as e:
        logging.error(f"Error in bot_response: {str(e)}")
        error_message = "Xin lỗi, đã xảy ra lỗi khi xử lý yêu cầu của bạn. Vui lòng thử lại."
        history[-1][1] = error_message  # Update with error message
        yield history

def clear_chat(login_info):
    if login_info["logged_in"]:
        user_data = load_user_data(login_info["username"])
        user_data["chat_history"] = []
        save_user_data(login_info["username"], user_data)
        return []
    return None

def add_premade_prompt(prompt_name, current_msg, history):
    prompt_data = PREMADE_PROMPTS.get(prompt_name, {})
    if prompt_data:
        user_instruction = prompt_data.get("user", "")
        new_history = history + [[None, user_instruction]] if history else [[None, user_instruction]]
        return "", new_history
    return current_msg, history

def toggle_internet(value):
    global INTERNET_ENABLED
    INTERNET_ENABLED = value
    return f"Kết nối internet đã được {'bật' if value else 'tắt'}"

def toggle_citation(value):
    global CITATION_ENABLED
    CITATION_ENABLED = value
    return f"Hiển thị nguồn trích dẫn đã được {'bật' if value else 'tắt'}"

def search_internet(query, cse_id):
    """Search the internet using Google Custom Search Engine"""
    if not INTERNET_ENABLED:
        return "Kết nối internet hiện đang tắt. Vui lòng bật kết nối internet để sử dụng tính năng này."
    
    try:
        results = []
        # Increase number of search results for better accuracy
        for url in search(query, num_results=5, custom_search_engine_id=cse_id):
            results.append(url)
        
        # Analyze multiple sources for better reliability
        reliable_sources = [url for url in results if any(domain in url.lower() for domain in [
            '.edu', '.gov', '.org', 'wikipedia.org', 'research', 'academic',
            'plumvillage.org', 'langmai.org', 'osho.com', 'thuvienhoasen.org'
        ])]
        
        if reliable_sources:
            results = reliable_sources[:3]  # Prioritize reliable sources
        else:
            results = results[:3]  # Use top 3 results if no reliable sources found
        
        if CITATION_ENABLED:
            return "\n\nNguồn tham khảo:\n" + "\n".join([f"- {url}" for url in results])
        return ""
    except Exception as e:
        return f"Lỗi tìm kiếm internet: {str(e)}"

def create_new_user(username, password):
    """Create a new user account"""
    try:
        user_folder = get_user_folder(username)
        user_data_file = os.path.join(user_folder, "user_data.json")
        
        if os.path.exists(user_data_file):
            return (
                gr.Column(visible=True),  # login container
                gr.Column(visible=False),  # chat container
                gr.Column(visible=False),  # admin container
                {"username": "", "password": "", "logged_in": False, "is_admin": False},  # login info
                [],  # chatbot
                None,  # user avatar
                None,  # bot avatar
                gr.Markdown("Username already exists", visible=True),  # login message
                []  # user list for admin
            )

        user_data = {
            "username": username,
            "password": password  # Store password directly
        }
        
        with open(user_data_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, indent=2, ensure_ascii=False)
            
        return (
            gr.Column(visible=True),  # login container
            gr.Column(visible=False),  # chat container
            gr.Column(visible=False),  # admin container
            {"username": "", "password": "", "logged_in": False, "is_admin": False},  # login info
            [],  # chatbot
            None,  # user avatar
            None,  # bot avatar
            gr.Markdown("User created successfully! Please login.", visible=True),  # login message
            []  # user list for admin
        )
    except Exception as e:
        logging.error(f"Create user error: {e}")
        return (
            gr.Column(visible=True),  # login container
            gr.Column(visible=False),  # chat container
            gr.Column(visible=False),  # admin container
            {"username": "", "password": "", "logged_in": False, "is_admin": False},  # login info
            [],  # chatbot
            None,  # user avatar
            None,  # bot avatar
            gr.Markdown(f"Error creating user: {str(e)}", visible=True),  # login message
            []  # user list for admin
        )
# Launch only the user interface
if __name__ == "__main__":
    interface = create_user_interface()
    interface.launch(
        server_port=7872,
        share=False,
        debug=True,
        show_error=True
    )