import os
import re
import json
import base64
import random
import logging
from pathlib import Path
import gradio as gr
import ollama
from datetime import datetime
import tiktoken
import requests
from bs4 import BeautifulSoup
import time

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize global variables
USER_DATA_FOLDER = "userdata"
PERSONALITIES = {}
EXAMPLE_RESPONSES = {}


# Create user data folder if it doesn't exist
if not os.path.exists(USER_DATA_FOLDER):
    os.makedirs(USER_DATA_FOLDER)

# ************************************************************************
# *                         Import prompts                        *
# ************************************************************************


def load_prompts(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        prompts_code = file.read()
    local_vars = {}
    exec(prompts_code, {}, local_vars)  # Execute the code in a local namespace
    return local_vars.get('EXAMPLE_RESPONSES'), local_vars.get('PERSONALITIES'), local_vars.get('PREMADE_PROMPTS')

# Load the prompts from prompts.txt
prompts_file_path = 'z:/This/This/My APP/Earthship_capt/prompts.txt'

# Initialize global variables
EXAMPLE_RESPONSES = {}
PERSONALITIES = {}
PREMADE_PROMPTS = {}

def load_global_prompts():
    global EXAMPLE_RESPONSES, PERSONALITIES, PREMADE_PROMPTS
    try:
        EXAMPLE_RESPONSES, PERSONALITIES, PREMADE_PROMPTS = load_prompts(prompts_file_path)
    except Exception as e:
        logging.error(f"Error loading prompts: {e}")
        PERSONALITIES["Trợ lý"] = {
            "system": "Bạn là một trợ lý AI hữu ích.",
            "links": ["https://vi.wikipedia.org", "https://www.google.com.vn"]
        }

# Load prompts at startup
load_global_prompts()

# ************************************************************************
# *                         Logging Configuration                        *
# ************************************************************************

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ************************************************************************
# *                         Constant Definitions                         *
# ************************************************************************

DEFAULT_PASSWORD = "admin"

# Available Ollama Models
MODEL_DISPLAY_NAMES = {
    "Vietai": "Tuanpham/t-visstar-7b:latest",
    "codegpt": "marco-o1",
}

# Technical model names for Ollama
AVAILABLE_MODELS = {
    model_tech: model_tech for model_tech in {
        "Tuanpham/t-visstar-7b:latest",
        "marco-o1",
        "llama2",
        "codellama"
    }
}

# Folder to store user data
USER_DATA_FOLDER = "userdata"
os.makedirs(USER_DATA_FOLDER, exist_ok=True)

# ************************************************************************
# *                  Helper Functions (New)                              *
# ************************************************************************

def get_all_usernames():
    """Gets a list of all registered usernames."""
    usernames = []
    for filename in os.listdir(USER_DATA_FOLDER):
        if os.path.isdir(os.path.join(USER_DATA_FOLDER, filename)):
            usernames.append(filename)
    return usernames

def get_chat_titles(username):
    """Gets the titles of all chats for a user."""
    user_data = load_user_data(username)
    if user_data:
        chat_titles = [
            (user_data.get(f"title_{chat_id}", f"Chat {chat_id}"), chat_id)
            for chat_id in user_data.get("chat_history", {})
        ]
        return chat_titles
    return []

def format_user_info(profile):
    """Format user profile information into a readable string."""
    if not profile:
        return ""
    
    formatted_info = []
    for key, value in profile.items():
        if value and key != "password":  # Skip empty values and password
            formatted_key = key.replace("_", " ").title()
            formatted_info.append(f"{formatted_key}: {value}")
    
    return "\n".join(formatted_info)

# ************************************************************************
# *                      Token Estimation Function                          *
# ************************************************************************

def estimate_tokens(text):
    """Estimates the number of tokens in a text string."""
    encoding = tiktoken.encoding_for_model("Tuanpham/t-visstar-7b:latest")
    return len(encoding.encode(text))

# ************************************************************************
# *            Function to Update Existing User Data                    *
# ************************************************************************

def update_existing_user_data():
    for filename in os.listdir(USER_DATA_FOLDER):
        if filename.endswith(".json"):
            filepath = os.path.join(USER_DATA_FOLDER, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    user_data = json.load(f)

                # Convert chat_history to dictionary if it's a list
                if "chat_history" in user_data and isinstance(user_data["chat_history"], list):
                    new_chat_history = {}
                    for i, msg in enumerate(user_data["chat_history"]):
                        if isinstance(msg, list) and len(msg) == 2:
                            new_chat_history[str(i)] = [msg[0], msg[1]]
                    user_data["chat_history"] = new_chat_history

                # Add next_chat_id if it doesn't exist
                if "next_chat_id" not in user_data:
                    # Find the highest existing chat ID and add 1
                    max_chat_id = -1
                    if "chat_history" in user_data and isinstance(user_data["chat_history"], dict):
                      for chat_id in user_data["chat_history"]:
                        if chat_id.isdigit() and int(chat_id) > max_chat_id:
                          max_chat_id = int(chat_id)
                    
                    user_data["next_chat_id"] = max_chat_id + 1

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(user_data, f, ensure_ascii=False, indent=2)
                print(f"Updated user data for {filename}")

            except Exception as e:
                print(f"Error updating {filename}: {e}")

# Call update_existing_user_data() at the beginning of your script
update_existing_user_data()

# ************************************************************************
# *               Web Search and Scrape Function                        *
# ************************************************************************

def web_search_and_scrape(query, personality, links):
    """
    Searches the web and specific links based on the query and personality,
    scrapes the content of the top results, and returns a summarized response
    along with reference links.
    """
    search_results = []
    reference_links = set()

    # Search specific links provided
    if links:
        for link in links:
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(link + "/search?q=" + query, headers=headers)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, 'html.parser')
                # Extract titles and snippets - adapt selectors as needed based on website structure
                results = soup.find_all('div', class_='search-result', limit=2)  # Example selector
                for result in results:
                    title_elem = result.find('h3')
                    snippet_elem = result.find('p')
                    
                    title = title_elem.text if title_elem else "No title"
                    snippet = snippet_elem.text if snippet_elem else "No snippet"
                    
                    search_results.append(f"{title}: {snippet}")
                    reference_links.add(link)
            except Exception as e:
                logging.error(f"Error searching link {link}: {e}")
                continue

    # General web search using DuckDuckGo if no specific results or if personality requires it
    if not search_results or personality == "Uncensored AI":
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(f"https://duckduckgo.com/html/?q={query}", headers=headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            # Extract titles, snippets, and links - adapt selectors as needed
            results = soup.find_all('div', class_='result', limit=3)
            for result in results:
                title_elem = result.find('a', class_='result__a')
                snippet_elem = result.find('a', class_='result__snippet')
                
                if title_elem:
                    title = title_elem.text
                    link = title_elem.get('href', '')
                    snippet = snippet_elem.text if snippet_elem else "No snippet"
                    
                    search_results.append(f"{title}: {snippet}")
                    if link:
                        reference_links.add(link)
        except Exception as e:
            logging.error(f"Error during general web search: {e}")

    if search_results:
        summary = "Thông tin tìm được:\n" + "\n".join(search_results)
        return summary, list(reference_links)
    else:
        return "Không tìm thấy thông tin liên quan.", []

# ************************************************************************
# *                    Save User Data Function                         *
# ************************************************************************

def save_user_data(username, data):
    user_folder = os.path.join(USER_DATA_FOLDER, username)
    os.makedirs(user_folder, exist_ok=True)  # Create user folder if it doesn't exist
    
    file_path = os.path.join(user_folder, "user_data.json")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error in save_user_data: {e}")

# ************************************************************************
# *                    Load User Data Function                         *
# ************************************************************************

def load_user_data(username):
    user_folder = os.path.join(USER_DATA_FOLDER, username)
    file_path = os.path.join(user_folder, "user_data.json")
    
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return data
    return None

# ************************************************************************
# *                  Save Chat History Function                        *
# ************************************************************************

def save_chat_history(username, chat_id, chat_history):
    """Saves a chat session to a separate file."""
    user_folder = os.path.join(USER_DATA_FOLDER, username)
    chat_file_path = os.path.join(user_folder, f"chat_{chat_id}.json")
    try:
        with open(chat_file_path, 'w', encoding='utf-8') as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error in save_chat_history: {e}")

# ************************************************************************
# *                  Load Chat History Function                        *
# ************************************************************************

def load_chat_history(username, chat_id):
    """Loads a chat session from its file."""
    user_folder = os.path.join(USER_DATA_FOLDER, username)
    chat_file_path = os.path.join(user_folder, f"chat_{chat_id}.json")
    if os.path.exists(chat_file_path):
        with open(chat_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

# ************************************************************************
# *                    Create New User Function                        *
# ************************************************************************

def create_new_user(username, password):
    if not username or not password:
        return (
            gr.update(visible=True),
            gr.update(visible=False),
            {"username": "", "password": "", "logged_in": False, "is_admin": False},
            [],
            None,
            None,
            gr.update(visible=True, value="Vui lòng nhập tên đăng nhập và mật khẩu."),
            [],
            gr.update(visible=False),
            None,
            [],
            gr.update(),
            gr.update()
        )
    
    user_data = load_user_data(username)
    if user_data:
        return (
            gr.update(visible=True),
            gr.update(visible=False),
            {"username": "", "password": "", "logged_in": False, "is_admin": False},
            [],
            None,
            None,
            gr.update(visible=True, value="Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác."),
            [],
            gr.update(visible=False),
            None,
            [],
            gr.update(),
            gr.update()
        )
    
    new_user_data = {
        "password": password,
        "chat_history": {},  # Changed to dictionary
        "next_chat_id": 0,
        "user_avatar": None,
        "bot_avatar": None,
        "profile": {
            "real_name": "",
            "age": "",
            "gender": "",
            "height": "",
            "weight": "",
            "job": "",
            "muscle_percentage": "",
            "passion": "",
            "vegan": False,
            "personality": ""
        }
    }
    save_user_data(username, new_user_data)
    
    return (
        gr.update(visible=False),
        gr.update(visible=True),
        {"username": username, "password": password, "logged_in": True, "is_admin": False},
        [],
        None,
        None,
        gr.update(visible=False),
        [],
        gr.update(visible=False),
        "0",
        [],
        gr.update(choices=list(PERSONALITIES.keys())),
        gr.update(choices=list(MODEL_DISPLAY_NAMES.keys()))
    )

# ************************************************************************
# *                          Custom CSS                                 *
# ************************************************************************

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
.accordion {
    background-color: #eee;
    color: #444;
    cursor: pointer;
    padding: 18px;
    width: 100%;
    text-align: left;
    border: none;
    outline: none;
    transition: 0.4s;
    margin-bottom: 5px;
}

.active, .accordion:hover {
    background-color: #ccc;
}

.panel {
    padding: 0 18px;
    background-color: white;
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.2s ease-out;
}
"""

# ************************************************************************
# *                     Create User Interface Function                  *
# ************************************************************************

def create_user_interface():
    # Ensure prompts are loaded
    if not PERSONALITIES:
        load_global_prompts()
    
    personality_choices = list(PERSONALITIES.keys())
    model_choices = list(MODEL_DISPLAY_NAMES.keys())

    with gr.Blocks(css=custom_css) as user_interface:
        gr.Markdown("# Earthship AI")

        # Initialize user data directory if it doesn't exist
        os.makedirs(USER_DATA_FOLDER, exist_ok=True)

        # Enable Gradio's built-in queue
        user_interface.queue(
            default_concurrency_limit=5,
            max_size=20,
            api_open=True
        )

        login_info = gr.State(value={"username": "", "password": "", "logged_in": False, "is_admin": False})
        current_chat_id = gr.State()

        # Add avatar components
        user_avatar = gr.Image(label="User Avatar", type="filepath", visible=False)
        bot_avatar = gr.Image(label="Bot Avatar", type="filepath", visible=False)

        with gr.Group() as login_group:
            with gr.Column():
                gr.Markdown("## Đăng nhập")
                username = gr.Textbox(label="Tên đăng nhập", placeholder="Nhập tên đăng nhập")
                password = gr.Textbox(label="Mật khẩu", placeholder="Nhập mật khẩu", type="password")
                with gr.Row():
                    login_button = gr.Button("Đăng nhập", variant="primary")
                    create_user_button = gr.Button("Tạo người dùng mới")
                login_message = gr.Markdown(visible=False)

        # Admin panel (initially hidden)
        with gr.Group(visible=False) as admin_panel:
            gr.Markdown("## Captain View")
            with gr.Row():
                user_selector = gr.Dropdown(choices=[], label="Select User", interactive=True)
                refresh_button = gr.Button("Refresh User List")
                show_all_chats_button = gr.Button("Show All Chat Histories")
            admin_chatbot = gr.Chatbot(elem_id="admin_chatbot", height=500)
        
        with gr.Group(visible=False) as chat_group:
            with gr.Row():
                # Left column for user profile
                with gr.Column(scale=1):
                    gr.Markdown("## Thông tin cá nhân")
                    gr.Markdown("AI lưu lại thông tin của bạn chỉ để hiểu bạn hơn.")
                    share_info_checkbox = gr.Checkbox(label="Cho phép AI truy cập thông tin cá nhân", value=True)
                    real_name = gr.Textbox(label="Họ và tên", placeholder="Nhập tên của bạn")
                    age = gr.Number(label="Tuổi")
                    gender = gr.Textbox(label="Giới tính", placeholder="Nhập giới tính của bạn")
                    vegan_checkbox = gr.Checkbox(label="Ăn chay", value=False)
                    height = gr.Number(label="Chiều cao (cm)")
                    weight = gr.Number(label="Cân nặng (kg)")
                    muscle_percentage = gr.Textbox(label="Phần trăm cơ (%)", placeholder="Nhập phần trăm cơ")
                    passion = gr.Textbox(label="Đam mê, sở thích", placeholder="Bạn thích làm điều gì?")
                    job = gr.Textbox(label="Nghề nghiệp", placeholder="Nhập nghề nghiệp của bạn")
                    personality_text = gr.TextArea(label="Tính cách", placeholder="Mô tả tính cách của bạn")
                    save_profile = gr.Button("Lưu thông tin", variant="primary")
                    hide_profile_button = gr.Button("Ẩn thông tin cá nhân")
                    show_profile_button = gr.Button("Chỉnh sửa thông tin cá nhân", visible=False)
                    password_input = gr.Textbox(label="Nhập mật khẩu", type="password", visible=False)
                    password_error = gr.Markdown(visible=False)

                    hide_profile_button.click(
                        fn=lambda: ([gr.update(visible=False) for _ in range(11)] + [gr.update(visible=False), gr.update(visible=True)]),
                        inputs=[],
                        outputs=[real_name, age, gender, height, weight, job, muscle_percentage, passion, vegan_checkbox, personality_text, save_profile, hide_profile_button, show_profile_button]
                    )

                    show_profile_button.click(
                        fn=lambda: (gr.update(visible=True), gr.update(visible=False)),
                        inputs=[],
                        outputs=[password_input, show_profile_button]
                    )

                    password_input.submit(
                        fn=lambda pwd, info: (
                            [gr.update(visible=True, value=load_user_data(info["username"]).get("profile", {}).get(field, "")) for field in ["real_name", "age", "gender", "height", "weight", "job", "muscle_percentage", "passion", "vegan", "personality"]] +
                            [gr.update(visible=True), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)]
                            if info["logged_in"] and load_user_data(info["username"]).get("password") == pwd
                            else [gr.update(visible=False) for _ in range(10)] + [gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), gr.update(visible=True, value="Incorrect password")]
                        ),
                        inputs=[password_input, login_info],
                        outputs=[real_name, age, gender, height, weight, job, muscle_percentage, passion, vegan_checkbox, personality_text, save_profile, hide_profile_button, password_input, password_error]
                    )
                    

                # Chat and inputs section

                with gr.Column(scale=3):
                    chatbot = gr.Chatbot(elem_id="chatbot", height=1000)
                    msg = gr.Textbox(
                        label="Nhập tin nhắn của bạn",
                        placeholder="Nhập tin nhắn và nhấn Enter",
                        elem_id="msg"
                    )
                    send = gr.Button("Gửi", variant="primary")
                    stop = gr.Button("Dừng tạo câu trả lời")

                # Right column (personality, model, internet, new chat, premade prompts)
                with gr.Column(scale=1):
                    personality = gr.Dropdown(
                        choices=personality_choices,
                        value=personality_choices[0],
                        label="Chọn tính cách AI",
                        interactive=True
                    )
                    model = gr.Dropdown(
                        choices=model_choices,
                        value=model_choices[0],
                        label="Chọn mô hình AI",
                        interactive=True
                    )
                    use_internet_checkbox = gr.Checkbox(label="Sử dụng Internet để tìm kiếm", value=False)
                    new_chat_button = gr.Button("Bắt đầu cuộc trò chuyện mới")
                    
                    gr.Markdown("### Thư viện công cụ")
                    premade_prompt_buttons = [gr.Button(prompt_name) for prompt_name in PREMADE_PROMPTS.keys()]
                    
                    gr.Markdown("## Lịch sử trò chuyện")
                    chat_history_dropdown = gr.Dropdown(choices=[], label="Chọn lịch sử trò chuyện", interactive=True, allow_custom_value=True)
                    with gr.Row():
                        load_chat_button = gr.Button("Load Chat")
                        rename_chat_button = gr.Button("Rename Chat")
                    rename_chat_textbox = gr.Textbox(placeholder="Enter new chat name", visible=False)

        # ************************************************************************
        # *                  Save Profile Info Function (Corrected)           *
        # ************************************************************************

        def save_profile_info(real_name, age, gender, height, weight, job, muscle_percentage, passion, vegan_checkbox, personality_text, login_info):
            if not login_info.get("logged_in", False):
                return

            # --- Conversion and Saving ---
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
                    "job": job,
                    "muscle_percentage": muscle_percentage,
                    "passion": passion,
                    "vegan": vegan_checkbox,
                    "personality": personality_text
                }
                save_user_data(username, user_data)
                
                # Return updates to keep showing the entered information
                return [
                    gr.update(visible=True),    # save_profile
                    gr.update(value=real_name), # real_name
                    gr.update(value=age),       # age
                    gr.update(value=gender),    # gender
                    gr.update(value=height),    # height
                    gr.update(value=weight),    # weight
                    gr.update(value=job),       # job
                    gr.update(value=muscle_percentage), # muscle_percentage
                    gr.update(value=passion),   # passion
                    gr.update(value=vegan_checkbox),    # vegan_checkbox
                    gr.update(value=personality_text),  # personality_text
                    gr.update(visible=False)    # show_profile_button
                ]
        # ************************************************************************
        # *                     Load Profile Info Function                      *
        # ************************************************************************
    
        def load_profile_info(login_info):
            if not login_info["logged_in"]:
                return [gr.update(value="") for _ in range(10)] + [gr.update(), gr.update()] # Return empty updates for personality and model

            username = login_info["username"]
            user_data = load_user_data(username)
            if user_data and "profile" in user_data:
                profile = user_data["profile"]
                # Convert numeric values to strings with proper handling
                height = str(profile.get('height', '')) if profile.get('height') is not None else ''
                weight = str(profile.get('weight', '')) if profile.get('weight') is not None else ''
                age = str(profile.get('age', '')) if profile.get('age') is not None else ''

                profile_info = f"""
        Thông tin người dùng:
        - Tên: {profile.get('real_name', '')}
        - Tuổi: {age}
        - Giới tính: {profile.get('gender', '')}
        - Chiều cao: {height} cm
        - Cân nặng: {weight} kg
        - Nghề nghiệp: {profile.get('job', '')}
        - Phần trăm cơ: {profile.get('muscle_percentage', '')}
        - Phần trăm mỡ: {profile.get('passion', '')}
        - Ăn chay: {'Có' if profile.get('vegan', False) else 'Không'}
        - Tính cách: {profile.get('personality', '')}
        """.encode('utf-8').decode('utf-8')

                return [
                    gr.update(visible=False),  # Hide save_profile button
                    gr.update(value=""),  # real_name
                    gr.update(value=""),  # age
                    gr.update(value=""),  # gender
                    gr.update(value=""),  # height
                    gr.update(value=""),  # weight
                    gr.update(value=""),  # job
                    gr.update(value=""),  # muscle_percentage
                    gr.update(value=""),  # passion
                    gr.update(value=False),  # vegan_checkbox
                    gr.update(value=""),  # personality_text
                    gr.update(visible=True),  # Show show_profile_button
                    gr.update(visible=True, value="It's so nice to know more about you. Do you want to hide the information? (You can still update it later)"),  # Update password_error with confirmation message
                    gr.update(visible=True)  # confirm_button
                
                ] + [gr.update(choices=list(PERSONALITIES.keys())), gr.update(choices=list(MODEL_DISPLAY_NAMES.keys()))]
            return [gr.update(value="") for _ in range(10)] + [gr.update(), gr.update()] # Return empty updates for personality and model


        # ************************************************************************
        # *                       New Chat Function                          *
        # ************************************************************************

        def new_chat(login_info, personality_choice, model_choice):
            if login_info["logged_in"]:
                username = login_info["username"]
                user_data = load_user_data(username)

                if user_data is None:
                    user_data = {"next_chat_id": 1, "chat_history": {"1": []}, "settings": {}}  # Initialize user data if None
                    save_chat_history(username, "1", [])  # Create first chat file
                    save_user_data(username, user_data)

                # Generate new chat ID
                new_chat_id = str(user_data["next_chat_id"])
                user_data["next_chat_id"] += 1

                # Create new chat entry in the dictionary
                user_data["chat_history"][new_chat_id] = []  # Initialize as an empty list

                # Update current chat ID
                current_chat_id.value = new_chat_id

                # Save user data
                save_user_data(username, user_data)

                # Update chat history dropdown (using datetime)
                chat_titles = [
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), chat_id)
                    for chat_id in user_data["chat_history"]
                ]

                return [], new_chat_id, gr.update(choices=chat_titles, value=new_chat_id)
            else:
                return [], None, gr.update(choices=[])

        # ************************************************************************
        # *                  Load Selected Chat Function                     *
        # ************************************************************************

        def load_selected_chat(login_info, chat_id):
            if login_info["logged_in"] and chat_id:
                username = login_info["username"]
                user_data = load_user_data(username)
                if chat_id in user_data["chat_history"]:
                    chat_history = load_chat_history(username, chat_id)

                if chat_history is None:
                    # Handle case where chat history file doesn't exist
                    logging.warning(f"Chat history not found for chat ID {chat_id}")
                    return [], chat_id  # Return empty history and current chat ID
                
                # Get the timestamp for the selected chat
                chat_timestamp = user_data.get(f"title_{chat_id}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

                current_chat_id.value = chat_id
                return chat_history, chat_id

            else:
                return [], None

        # ************************************************************************
        # *                    Stream Chat Function (Modified)                 *
        # ************************************************************************

        def stream_chat(message, history, login_info, personality, ollama_model, current_chat_id, use_internet):
            """
            Streams the response from Ollama word by word with a delay.
            """
            global stop_generation
            stop_generation = False

            # Ensure current_chat_id is a string
            current_chat_id = str(current_chat_id)

            try:
                response = ""
                personality_data = PERSONALITIES.get(personality)
                personality_prompt = personality_data.get("system", "") if personality_data else ""
                personality_links = personality_data.get("links", []) if personality_data else []

                # Get an example response for the selected personality
                if personality in EXAMPLE_RESPONSES:
                    example = random.choice(EXAMPLE_RESPONSES[personality])
                    personality_prompt = f"""
                    {personality_prompt}

                    QUAN TRỌNG: Bạn phải tuân theo các quy tắc sau trong các phản hồi của mình: 
                    1. Luôn duy trì tính cách và phong cách nói chuyện như trong ví dụ dưới đây 
                    2. Bao gồm các biểu hiện cảm xúc và hành động trong dấu ngoặc đơn như trong ví dụ 
                    3. Sử dụng các mẫu ngôn ngữ và cách diễn đạt tương tự 
                    4. Giữ nguyên mức độ trang trọng và giọng điệu 
                    5. Duy trì xưng hô đã được hướng dẫn, không thay đổi xưng hô trong hội thoại Ví dụ về phong cách phản hồi cần tuân theo: {example} 
                    Nhớ rằng: Mỗi phản hồi của bạn phải tuân theo phong cách này một cách chính xác, bao gồm cả các biểu hiện cảm xúc và hành động trong dấu ngoặc đơn.
                    """

                # Add user profile information to system message if allowed
                if share_info_checkbox.value:
                    user_data = load_user_data(login_info["username"])
                    if user_data and "profile" in user_data:
                        profile = user_data["profile"]
                        user_info = format_user_info(profile)
                        personality_prompt += f"\n\nUser Information:\n{user_info}"

                # Skip personality prompt for certain personalities
                skip_personality_prompt = personality in ["Uncen AI", "Uncensored AI"]
                if skip_personality_prompt:
                    system_message = personality_data.get("system", "")
                else:
                    system_message = f"{personality_prompt}\n\n{personality_data.get('system', '')}"

                # Create the conversation history
                messages = []
                messages.append({
                    'role': 'system',
                    'content': system_message
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
                response_complete = ""
                search_links = [] # Initialize search_links here
                
                # Stream response from Ollama
                response_stream = ollama.chat(
                    model=MODEL_DISPLAY_NAMES.get(ollama_model, ollama_model),
                    messages=messages,
                    stream=True
                )

                history = history or []
                current_response = ""
                
                for chunk in response_stream:
                    if stop_generation:
                        break

                    # Access the content correctly from the chunk
                    if 'message' in chunk and 'content' in chunk['message']:
                        response_chunk = chunk['message']['content']
                        current_response += response_chunk
                        
                        # Create a new history with the current message and accumulated response
                        new_history = history.copy()
                        new_history.append([message, current_response])  # Use list instead of tuple
                        yield new_history

                # Save final chat history
                if login_info.get("logged_in"):
                    username = login_info["username"]
                    final_history = history.copy()
                    final_history.append([message, current_response])  # Use list instead of tuple
                    save_chat_history(username, current_chat_id, final_history)

            except Exception as e:
                logging.error(f"Error in stream_chat: {str(e)}")
                history = history or []
                history.append([message, "Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại."])  # Use list instead of tuple
                yield history

        # ************************************************************************
        # *                       Stop Generation Function                    *
        # ************************************************************************

        def stop_gen():
            global stop_generation
            stop_generation = True

        # ************************************************************************
        # *                     Update Admin View Function                    *
        # ************************************************************************

        def update_admin_view(selected_user):
            if selected_user:
                user_data = load_user_data(selected_user)
                # Flatten the chat history for admin view
                admin_chat_history = []
                for chat_id, chat in user_data.get("chat_history", {}).items():
                    for msg in chat:
                        admin_chat_history.append(msg)
                return admin_chat_history
            return []

        # ************************************************************************
        # *                    Show All Chats Function                       *
        # ************************************************************************

        def show_all_chats():
            all_chats_history = []
            for user_file in os.listdir(USER_DATA_FOLDER):
                if os.path.isdir(os.path.join(USER_DATA_FOLDER, user_file)):
                    username = user_file
                    user_data = load_user_data(username)
                    all_chats_history.append([None, f"=== Chat History for {username} ==="])
                    for chat_id, chat in user_data.get("chat_history", {}).items():
                        for msg in chat:
                            if msg[0]:  # User message
                                all_chats_history.append([msg[0], None])
                            elif msg[1]: # Bot message
                                all_chats_history.append([None, msg[1]])
                    all_chats_history.append([None, "=== End of Chat History ==="])
            return all_chats_history

        # ************************************************************************
        # *                      Refresh Users Function                      *
        # ************************************************************************

        def refresh_users():
            user_files = os.listdir(USER_DATA_FOLDER)
            user_names = [f for f in user_files if os.path.isdir(os.path.join(USER_DATA_FOLDER, f))]
            return gr.update(choices=user_names)

        # ************************************************************************
        # *                          Login Function                           *
        # ************************************************************************

        def login(username, password):
            user_data = load_user_data(username)

            if user_data is None:
                # User does not exist
                return (
                    gr.update(visible=True),  # Keep login group visible
                    gr.update(visible=False),  # Hide chat interface
                    {"username": "", "password": "", "logged_in": False, "is_admin": False},
                    [],  # Clear chatbot
                    None,  # No user avatar
                    None,  # No bot avatar
                    gr.update(visible=True, value="Tên đăng nhập không tồn tại. Vui lòng tạo người dùng mới."),
                    gr.update(choices=[]),  # Clear user selector
                    gr.update(visible=False),  # Hide admin panel
                    None,  # Reset current chat ID
                    gr.update(choices=[]),  # Clear chat history dropdown
                    gr.update(),  # Empty update for personality
                    gr.update(),  # Empty update for model
                    gr.update(visible=False) # confirm_button
                )

            # User exists, check password
            if user_data.get("password") == password:
                # Successful login
                login_state = {
                    "username": username,
                    "password": password,
                    "logged_in": True,
                    "is_admin": user_data.get("is_admin", False)
                }

                # Load user's avatar or set default
                user_avatar_path = user_data.get("user_avatar", "default_user.png")
                bot_avatar_path = user_data.get("bot_avatar", "default_bot.png")

                # Load chat history
                chat_histories = []
                for chat_id in user_data["chat_history"]:
                    title = user_data.get(f"title_{chat_id}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    chat_histories.append((title, chat_id))

                # Load the last chat ID or start a new chat
                last_chat_id = str(user_data["next_chat_id"] - 1) if user_data["next_chat_id"] > 0 else "0"

                # Check if last_chat_id exists in chat_history, if not, create it
                if last_chat_id not in user_data["chat_history"]:
                    user_data["chat_history"][last_chat_id] = []
                    save_user_data(username, user_data)

                return (
                    gr.update(visible=False),  # Hide login group
                    gr.update(visible=True),  # Show chat interface
                    login_state,  # Update login info
                    user_data["chat_history"].get(last_chat_id, [])[-10:],  # Load last 10 messages of the last chat
                    user_avatar_path,  # Set user avatar
                    bot_avatar_path,  # Set bot avatar
                    gr.update(visible=False),  # Hide login message
                    gr.update(choices=list(get_all_usernames()) if login_state["is_admin"] else []),  # Update user selector
                    gr.update(visible=login_state["is_admin"]),  # Show/hide admin panel
                    last_chat_id,  # Set current chat ID
                    gr.update(choices=chat_histories),  # Update chat history dropdown
                    gr.update(choices=list(PERSONALITIES.keys())),  # Update personality choices
                    gr.update(choices=list(MODEL_DISPLAY_NAMES.keys())),  # Update model choices
                    gr.update(visible=False) # confirm_button
                )
            else:
                # Invalid password
                return (
                    gr.update(visible=True),
                    gr.update(visible=False),
                    {"username": "", "password": "", "logged_in": False, "is_admin": False},
                    [],
                    None,
                    None,
                    gr.update(visible=True, value="Mật khẩu không đúng. Vui lòng thử lại."),
                    [],
                    gr.update(visible=False),
                    None,
                    [],
                    gr.update(),  # Empty update for personality
                    gr.update(),   # Empty update for model
                    gr.update(visible=False) # confirm_button
                )
        # ************************************************************************
        # *                     Connect Admin Panel Components                 *
        # ************************************************************************

        # Connect the admin panel components
        refresh_button.click(refresh_users, outputs=[user_selector])
        user_selector.change(update_admin_view, inputs=[user_selector], outputs=[admin_chatbot])
        show_all_chats_button.click(show_all_chats, outputs=[admin_chatbot])

        # ************************************************************************
        # *                     Connect Login and other Components             *
        # ************************************************************************

        # Update login button to handle admin view
        login_button.click(
            fn=login,
            inputs=[username, password],
            outputs=[
                login_group, chat_group, login_info, chatbot,
                user_avatar, bot_avatar, login_message,
                user_selector, admin_panel, current_chat_id, chat_history_dropdown,
                personality, model
            ]
        )
            

        # ************************************************************************
        # *                         User Message Function                      *
        # ************************************************************************

        def user_msg(user_message, history, login_info, current_chat_id):
            # Ensure current_chat_id is a string
            current_chat_id = str(current_chat_id)
            if not login_info.get("logged_in", False):
                return "Vui lòng đăng nhập trước khi gửi tin nhắn.", history

            history = history or []

            if not user_message or not user_message.strip():
                return "", history  # Return without changing history if the message is empty

            history.append([user_message, None])  # Add user message as a list of [user_message, None]
            return "", history

        # ************************************************************************
        # *                        Bot Response Function (Modified)            *
        # ************************************************************************

        def bot_response(message, history, login_info, personality, model, current_chat_id, use_internet):
            if not message:
                return [] if history is None else history
            
            history = [] if history is None else history
            
            try:
                for new_history in stream_chat(message, history, login_info, personality, model, current_chat_id, use_internet):
                    if isinstance(new_history, list):
                        history = new_history
                        yield history
            except Exception as e:
                logging.error(f"Error in bot_response: {str(e)}")
                history.append([message, "Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại."])  # Use list instead of tuple
                yield history

        # Set up chat handlers
        def on_submit(message, history, login_info, current_chat_id, personality_choice, model_choice, use_internet):
            # First, update history with user message
            history = history or []
            history.append([message, None])
            
            # Then generate bot response
            try:
                for new_history in stream_chat(message, history[:-1], login_info, personality_choice, model_choice, current_chat_id, use_internet):
                    if isinstance(new_history, list):
                        yield new_history
            except Exception as e:
                logging.error(f"Error in on_submit: {str(e)}")
                history.append([message, "Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại."])
                yield history

        msg.submit(
            on_submit,
            inputs=[msg, chatbot, login_info, current_chat_id, personality, model, use_internet_checkbox],
            outputs=chatbot
        ).then(
            lambda: "",
            None,
            msg
        )

        send.click(
            on_submit,
            inputs=[msg, chatbot, login_info, current_chat_id, personality, model, use_internet_checkbox],
            outputs=chatbot
        ).then(
            lambda: "",
            None,
            msg
        )

        stop.click(stop_gen)

        save_profile.click(
            save_profile_info,
            inputs=[real_name, age, gender, height, weight, job, muscle_percentage, passion, vegan_checkbox, personality_text, login_info],
            outputs=[save_profile, real_name, age, gender, height, weight, job, muscle_percentage, passion, vegan_checkbox, personality_text, show_profile_button]
        )
    
        
        hide_profile_button.click(
            fn=lambda: ([gr.update(visible=False) for _ in range(11)] + [gr.update(visible=False), gr.update(visible=True)]),
            inputs=[],
            outputs=[real_name, age, gender, height, weight, job, muscle_percentage, passion, vegan_checkbox, personality_text, hide_profile_button, save_profile]
        )

        load_chat_button.click(
            fn=load_selected_chat,
            inputs=[login_info, chat_history_dropdown],
            outputs=[chatbot, current_chat_id]
        )
        # ************************************************************************
        # *                    Add Premade Prompt Function                    *
        # ************************************************************************
        
        def add_premade_prompt(prompt_name, current_msg, history):
            prompt_data = PREMADE_PROMPTS.get(prompt_name, {})
            if prompt_data:
                user_instruction = prompt_data.get("user", "")
                new_history = history + [[user_instruction, None]] if history else [[user_instruction, None]]
                return "", new_history
            return current_msg, history
                    
        # ************************************************************************
        # *                       Rename Chat Function                         *
        # ************************************************************************

        def rename_chat(new_name, chat_id, login_info):
            if not login_info["logged_in"] or not chat_id:
                return [], gr.update(visible=False)

            username = login_info["username"]
            user_data = load_user_data(username)

            if user_data:
                user_data[f"title_{chat_id}"] = new_name  # Directly set the new name
                save_user_data(username, user_data)
                chat_histories = get_chat_titles(username) # Use the helper function

                return chat_histories, gr.update(visible=False)

            return [], gr.update(visible=False)        
        # ************************************************************************
        # *                  Show Rename Textbox Function                     *
        # ************************************************************************

        def show_rename_textbox():
            return gr.update(visible=True)

        def hide_rename_textbox():
            return gr.update(visible=False)

        # ************************************************************************
        # *                    Connect Remaining Components                   *
        # ************************************************************************

        new_chat_button.click(
            fn=new_chat,
            inputs=[login_info, personality, model],
            outputs=[chatbot, current_chat_id, chat_history_dropdown]
        )

        personality.change(
            fn=new_chat,
            inputs=[login_info, personality, model],
            outputs=[chatbot, current_chat_id, chat_history_dropdown]
        )

        create_user_button.click(
            fn=create_new_user,
            inputs=[username, password],
            outputs=[login_group, chat_group, login_info, chatbot, user_avatar, bot_avatar, login_message, user_selector, admin_panel, current_chat_id, chat_history_dropdown, personality, model]
        )

        msg.submit(user_msg, [msg, chatbot, login_info, current_chat_id], [msg, chatbot]).then(
            bot_response, [chatbot, login_info, personality, model, current_chat_id, use_internet_checkbox], [chatbot, chat_history_dropdown, chat_history_dropdown]
        )
        send.click(user_msg, [msg, chatbot, login_info, current_chat_id], [msg, chatbot]).then(
            bot_response, [chatbot, login_info, personality, model, current_chat_id, use_internet_checkbox], [chatbot, chat_history_dropdown, chat_history_dropdown]
        )
        stop.click(stop_gen)

        save_profile.click(
            save_profile_info,
            inputs=[real_name, age, gender, height, weight, job, muscle_percentage, passion, vegan_checkbox, personality_text, login_info],
            outputs=[save_profile, real_name, age, gender, height, weight, job, muscle_percentage, passion, vegan_checkbox, personality_text, show_profile_button]
        )
    
        
        hide_profile_button.click(
            fn=lambda: ([gr.update(visible=False) for _ in range(11)] + [gr.update(visible=False), gr.update(visible=True)]),
            inputs=[],
            outputs=[real_name, age, gender, height, weight, job, muscle_percentage, passion, vegan_checkbox, personality_text, hide_profile_button, save_profile]
        )

        load_chat_button.click(
            fn=load_selected_chat,
            inputs=[login_info, chat_history_dropdown],
            outputs=[chatbot, current_chat_id]
        )
        # ************************************************************************
        # *                    Add Premade Prompt Function                    *
        # ************************************************************************
        
        def add_premade_prompt(prompt_name, current_msg, history):
            prompt_data = PREMADE_PROMPTS.get(prompt_name, {})
            if prompt_data:
                user_instruction = prompt_data.get("user", "")
                new_history = history + [[user_instruction, None]] if history else [[user_instruction, None]]
                return "", new_history
            return current_msg, history

        for button, prompt_name in zip(premade_prompt_buttons, PREMADE_PROMPTS.keys()):
            button.click(
                add_premade_prompt,
                inputs=[gr.State(prompt_name), msg, chatbot],
                outputs=[msg, chatbot]
            )

        rename_chat_button.click(
            fn=show_rename_textbox,
            inputs=[],
            outputs=[rename_chat_textbox]
        )

        rename_chat_textbox.submit(
            fn=rename_chat,
            inputs=[rename_chat_textbox, current_chat_id, login_info],
            outputs=[chat_history_dropdown, rename_chat_textbox]
        ).then(
            fn=hide_rename_textbox,
            inputs=[],
            outputs=[rename_chat_textbox]
        )

    return user_interface




# ************************************************************************
# *                     Launch User Interface                          *
# ************************************************************************

user_interface = create_user_interface()
user_interface.launch(
    server_name="127.0.0.1",
    server_port=7871,
    share=False,
)