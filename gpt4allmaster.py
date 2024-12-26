
import os
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

# ************************************************************************
# *                         Logging Configuration                        *
# ************************************************************************

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ************************************************************************
# *                         Constant Definitions                         *
# ************************************************************************

DEFAULT_PASSWORD = "admin"
import json
USER_DATA_FOLDER = "userdata"
os.makedirs(USER_DATA_FOLDER, exist_ok=True)

# ************************************************************************
# *                         Prompt Management                            *
# ************************************************************************

EXAMPLE_RESPONSES = {}
PERSONALITIES = {}
PREMADE_PROMPTS = {}

# Load configuration from config.json
with open('config.json', 'r') as f:
    config = json.load(f)

PROMPTS_FILE_PATH = config.get("prompts_file_path", "z:/This/This/My APP/Earthship_capt/prompts.txt")
AVATAR_IMAGES_PATH = config.get("avatar_images_path", "icons")
MODEL_NAME = config.get("model_name", "Tuanpham/t-visstar-7b:latest")

def load_prompts(file_path):
    """Loads prompts, example responses, and personalities from a Python file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        prompts_code = file.read()
    local_vars = {}
    exec(prompts_code, {}, local_vars)
    return local_vars.get('EXAMPLE_RESPONSES', {}), local_vars.get('PERSONALITIES', {}), local_vars.get('PREMADE_PROMPTS', {})

def load_global_prompts():
    """Loads prompts into global variables, handling potential errors."""
    global EXAMPLE_RESPONSES, PERSONALITIES, PREMADE_PROMPTS
    try:
        EXAMPLE_RESPONSES, PERSONALITIES, PREMADE_PROMPTS = load_prompts(PROMPTS_FILE_PATH)
    except Exception as e:
        logging.error(f"Error loading prompts: {e}")
        # Provide a default personality if loading fails
        PERSONALITIES["Trợ lý"] = {
            "system": "Bạn là một trợ lý AI hữu ích.",
            "links": ["https://vi.wikipedia.org", "https://www.google.com.vn"]
        }

load_global_prompts()  # Load prompts at startup

# ************************************************************************
# *                         Model Definitions                            *
# ************************************************************************

MODEL_DISPLAY_NAMES = {
    "Vietai": "Tuanpham/t-visstar-7b:latest"
}

AVAILABLE_MODELS = {
    model_tech: model_tech for model_tech in {
        "Tuanpham/t-visstar-7b:latest"
    }
}

# ************************************************************************
# *                      Helper Functions                                *
# ************************************************************************

def get_all_usernames():
    """Gets a list of all registered usernames."""
    return [name for name in os.listdir(USER_DATA_FOLDER) if os.path.isdir(os.path.join(USER_DATA_FOLDER, name))]

def get_chat_titles(username):
    """Gets the titles of all chats for a user."""
    user_data = load_user_data(username)
    return [(user_data.get(f"title_{chat_id}", f"Chat {chat_id}"), chat_id) for chat_id in user_data.get("chat_history", {})] if user_data else []

def format_user_info(profile):
    """Format user profile information into a readable string."""
    return "\n".join(f"{key.replace('_', ' ').title()}: {value}" for key, value in profile.items() if value and key != "password") if profile else ""

def estimate_tokens(text):
    """Estimates the number of tokens in a text string."""
    encoding = tiktoken.encoding_for_model(MODEL_NAME)  # Assuming this is your primary model
    return len(encoding.encode(text))

def get_avatar_path(personality_name):
    """Get the avatar path for a given personality"""
    return os.path.join(AVATAR_IMAGES_PATH, f"{personality_name.lower().replace(' ', '_')}.png")

# ************************************************************************
# *                    Data Management Functions                         *
# ************************************************************************

def save_user_data(username, data):
    """Saves user data to a JSON file."""
    user_folder = os.path.join(USER_DATA_FOLDER, username)
    os.makedirs(user_folder, exist_ok=True)
    file_path = os.path.join(user_folder, "user_data.json")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error saving user data for {username}: {e}")

def load_user_data(username):
    """Loads user data from a JSON file."""
    user_folder = os.path.join(USER_DATA_FOLDER, username)
    file_path = os.path.join(user_folder, "user_data.json")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_chat_history(username, chat_id, chat_history):
    """Saves a chat session to a separate file."""
    user_folder = os.path.join(USER_DATA_FOLDER, username)
    chat_file_path = os.path.join(user_folder, f"chat_{chat_id}.json")
    try:
        with open(chat_file_path, 'w', encoding='utf-8') as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error saving chat history for {username}, chat ID {chat_id}: {e}")

def load_chat_history(username, chat_id):
    """Loads a chat session from its file."""
    user_folder = os.path.join(USER_DATA_FOLDER, username)
    chat_file_path = os.path.join(user_folder, f"chat_{chat_id}.json")
    if os.path.exists(chat_file_path):
        with open(chat_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

# ************************************************************************
# *                   User and Session Management                       *
# ************************************************************************

def create_new_user(username, password):
    """Creates a new user with default settings."""
    if not username or not password:
        return error_response("Vui lòng nhập tên đăng nhập và mật khẩu.")
    if load_user_data(username):
        return error_response("Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.")

    new_user_data = {
        "password": password,
        "chat_history": {},
        "next_chat_id": 0,
        "user_avatar": None,
        "bot_avatar": None,
        "first_login": True,
        "profile": {
            "real_name": "", "age": "", "gender": "", "height": "", "weight": "",
            "job": "", "muscle_percentage": "", "passion": "", "vegan": False, "personality": ""
        }
    }
    save_user_data(username, new_user_data)
    return success_response(username, password)

def login(username, password):
    """Handles user login, sets up session, and loads user data."""
    if not username or not password:
        return error_response("Vui lòng nhập tên đăng nhập và mật khẩu.")

    user_data = load_user_data(username)
    if not user_data or user_data.get("password") != password:
        return error_response("Tên đăng nhập hoặc mật khẩu không đúng.")

    # Successful login
    return success_response(username, password)
    
def error_response(message):
    """Generates a response for login or user creation errors."""
    return [
        gr.update(visible=True),  # login_group
        gr.update(visible=False),  # chat_group
        {"username": "", "password": "", "logged_in": False, "is_admin": False},  # login_info
        [],  # chatbot
        None,  # current_chat_id
        None,  # personality
        message,  # login_message
        gr.update(choices=[]),  # chat_history_dropdown
        gr.update(visible=False),  # admin_panel
        "0",  # selected_user
        [],  # admin_chatbot
        gr.update(choices=list(PERSONALITIES.keys()), value="Trợ lý"),  # personality choices
        gr.update(choices=list(MODEL_DISPLAY_NAMES.keys())),  # model choices
        # Profile fields
        gr.update(value="", visible=False),  # real_name
        gr.update(value=None, visible=False),  # age
        gr.update(value="", visible=False),  # gender
        gr.update(value=None, visible=False),  # height
        gr.update(value=None, visible=False),  # weight
        gr.update(value="", visible=False),  # job
        gr.update(value="", visible=False),  # muscle_percentage
        gr.update(value="", visible=False),  # passion
        gr.update(value=False, visible=False),  # vegan_checkbox
        gr.update(value="", visible=False),  # personality_text
        gr.update(visible=False),  # save_profile
        gr.update(visible=False),  # hide_profile_button
        gr.update(visible=True),   # show_profile_button
        gr.update(visible=False),  # password_input
        gr.update(visible=False)   # password_error
    ]

def success_response(username, password):
    """Generates a response for successful login or user creation."""
    user_data = load_user_data(username)
    profile_data = user_data.get("profile", {})
    chat_titles = get_chat_titles(username)
    
    # Set default titles for chats that don't have one
    for chat_id in user_data.get("chat_history", {}):
        if f"title_{chat_id}" not in user_data:
            user_data[f"title_{chat_id}"] = f"Chat {chat_id}"
    save_user_data(username, user_data)
    
    return [
        gr.update(visible=False),  # login_group
        gr.update(visible=True),   # chat_group
        {"username": username, "password": password, "logged_in": True, "is_admin": username.lower() == "admin"},  # login_info
        [],  # chatbot
        None,  # current_chat_id
        "Trợ lý",  # personality - Set default personality
        gr.update(visible=False),  # login_message
        gr.update(choices=chat_titles, value=None),  # chat_history_dropdown
        gr.update(visible=username.lower() == "admin"),  # admin_panel
        "0",  # selected_user
        [],  # admin_chatbot
        gr.update(choices=list(PERSONALITIES.keys()), value="Trợ lý"),  # personality choices
        gr.update(choices=list(MODEL_DISPLAY_NAMES.keys())),  # model choices
        # Profile fields with values from user_data
        gr.update(value=profile_data.get("real_name", ""), visible=False),
        gr.update(value=profile_data.get("age", None), visible=False),
        gr.update(value=profile_data.get("gender", ""), visible=False),
        gr.update(value=profile_data.get("height", None), visible=False),
        gr.update(value=profile_data.get("weight", None), visible=False),
        gr.update(value=profile_data.get("job", ""), visible=False),
        gr.update(value=profile_data.get("muscle_percentage", ""), visible=False),
        gr.update(value=profile_data.get("passion", ""), visible=False),
        gr.update(value=profile_data.get("vegan", False), visible=False),
        gr.update(value=profile_data.get("personality", ""), visible=False),
        gr.update(visible=False),  # save_profile
        gr.update(visible=False),  # hide_profile_button
        gr.update(visible=True),   # show_profile_button
        gr.update(visible=False),  # password_input
        gr.update(visible=False)   # password_error
    ]

# ************************************************************************
# *                    Chat and Prompt Management                       *
# ************************************************************************

def new_chat(login_info, personality_choice, model_choice):
    """Starts a new chat session."""
    if not login_info["logged_in"]:
        return [], None, gr.update(choices=[])

    username = login_info["username"]
    user_data = load_user_data(username) or {"next_chat_id": 1, "chat_history": {"1": []}, "settings": {}}
    new_chat_id = str(user_data["next_chat_id"])
    user_data["next_chat_id"] += 1
    user_data["chat_history"][new_chat_id] = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_data[f"title_{new_chat_id}"] = timestamp
    save_user_data(username, user_data)

    return [], new_chat_id, gr.update(choices=get_chat_titles(username), value=(timestamp, new_chat_id))

def load_selected_chat(login_info, chat_id):
    """Loads a selected chat session."""
    if not login_info["logged_in"] or not chat_id:
        return [], None

    username = login_info["username"]
    chat_history = load_chat_history(username, chat_id)
    if chat_history is None:
        logging.warning(f"Chat history not found for chat ID {chat_id}")
        return [], chat_id

    return chat_history, chat_id

def add_premade_prompt(prompt_name, current_msg, history):
    """Adds a premade prompt to the chat history."""
    new_history = list(history or [])
    new_history.append([prompt_name, None])
    return "", new_history

def rename_chat(new_name, chat_id, login_info):
    """Renames a chat session."""
    if not login_info["logged_in"] or not chat_id or not new_name:
        return gr.update(choices=get_chat_titles(login_info["username"])), gr.update(visible=False)

    username = login_info["username"]
    user_data = load_user_data(username)
    if user_data and chat_id in user_data.get("chat_history", {}):
        user_data[f"title_{chat_id}"] = new_name
        save_user_data(username, user_data)
        chat_titles = get_chat_titles(username)
        selected_index = next((i for i, (title, id) in enumerate(chat_titles) if id == chat_id), None)
        return gr.update(choices=chat_titles, value=chat_titles[selected_index] if selected_index is not None else None), gr.update(visible=False)

    return gr.update(choices=get_chat_titles(username)), gr.update(visible=False)

# ************************************************************************
# *                       Profile Management                            *
# ************************************************************************

def save_profile_info(real_name, age, gender, height, weight, job, muscle_percentage, passion, vegan_checkbox, personality_text, login_info):
    """Saves the user's profile information."""
    if not login_info.get("logged_in", False):
        return

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

        return [
            gr.update(visible=True),  # save_profile
            gr.update(value=real_name),  # real_name
            gr.update(value=age),  # age
            gr.update(value=gender),  # gender
            gr.update(value=height),  # height
            gr.update(value=weight),  # weight
            gr.update(value=job),  # job
            gr.update(value=muscle_percentage),  # muscle_percentage
            gr.update(value=passion),  # passion
            gr.update(value=vegan_checkbox),  # vegan_checkbox
            gr.update(value=personality_text),  # personality_text
            gr.update(visible=False)  # show_profile_button
        ]

def load_profile_info(login_info):
    """Loads and displays the user's profile information."""
    if not login_info["logged_in"]:
        return [gr.update(value="") for _ in range(10)] + [gr.update(), gr.update()]

    username = login_info["username"]
    user_data = load_user_data(username)
    if user_data and "profile" in user_data:
        profile = user_data["profile"]
        # Convert numeric values to strings
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
        - Đam mê: {profile.get('passion', '')}
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
    return [gr.update(value="") for _ in range(10)] + [gr.update(), gr.update()]

# ************************************************************************
# *                         AI Interaction                              *
# ************************************************************************

def generate_better_prompt(message, personality_choice):
    """Gợi ý cách cải thiện câu lệnh (prompt) bằng cách sử dụng mô hình AI."""
    if not message.strip():
        return "Vui lòng nhập nội dung trước khi sử dụng công cụ gợi ý"

    system_message = """Bạn là một trợ lý AI hữu ích. Nhiệm vụ của bạn là phân tích văn bản đầu vào đã cho và đề xuất các cách để cải thiện nó thành một câu lệnh (prompt) hoàn chỉnh hơn. 
    Hãy xem xét các khía cạnh sau:
    1. Rõ ràng và cụ thể
    2. Bối cảnh và thông tin nền
    3. Định dạng đầu ra mong muốn
    4. Các ràng buộc hoặc yêu cầu

    Cung cấp các đề xuất cụ thể dựa trên văn bản đầu vào."""

    messages = [
        {'role': 'system', 'content': system_message},
        {'role': 'user', 'content': f"Hãy giúp tôi cải thiện câu lệnh này: {message}"}
    ]

    try:
        response = chat_with_model(messages, list(MODEL_DISPLAY_NAMES.keys())[0], max_tokens=250)  # Use default model
        return response
    except Exception as e:
        logging.error(f"Error in generate_better_prompt: {str(e)}")
        return "Xin lỗi, đã có lỗi xảy ra khi tạo gợi ý. Vui lòng thử lại."

def regenerate_response(chatbot_history, message_index, login_info, personality_choice, model_choice):
    """Regenerates a response for a specific message in the chat history."""
    if not chatbot_history or message_index >= len(chatbot_history) or not login_info["logged_in"]:
        return chatbot_history

    user_message = chatbot_history[message_index][0]
    personality_data = PERSONALITIES.get(personality_choice, {})
    personality_prompt = personality_data.get("system", "")

    messages = [{'role': 'system', 'content': personality_prompt}]
    for i in range(message_index):
        if chatbot_history[i][0]:
            messages.append({'role': 'user', 'content': chatbot_history[i][0]})
        if chatbot_history[i][1]:
            messages.append({'role': 'assistant', 'content': chatbot_history[i][1]})
    messages.append({'role': 'user', 'content': user_message})

    try:
        response = chat_with_model(messages, model_choice, max_tokens=700)
        chatbot_history[message_index][1] = response
        username = login_info["username"]
        chat_id = current_chat_id.value
        if chat_id:
            save_chat_history(username, chat_id, chatbot_history)
    except Exception as e:
        logging.error(f"Error in regenerate_response: {str(e)}")
        chatbot_history[message_index][1] = "Xin lỗi, đã có lỗi xảy ra khi tạo lại câu trả lời. Vui lòng thử lại."

    return chatbot_history

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

def chat_with_model(messages, model_choice, max_tokens=700):
    """Interacts with the chosen AI model to generate a response."""
    try:
        response_stream = ollama.chat(
            model=MODEL_DISPLAY_NAMES.get(model_choice, model_choice),
            messages=messages,
            stream=True,           
        )
        response = ""
        for chunk in response_stream:
            if 'message' in chunk and 'content' in chunk['message']:
                response += chunk['message']['content']
        return response
    except Exception as e:
        logging.error(f"Error in chat_with_model: {str(e)}")
        return "Xin lỗi, đã có lỗi xảy ra khi giao tiếp với mô hình AI."

def stream_chat(message, history, login_info, personality, ollama_model, current_chat_id, use_internet, share_info_checkbox):
    """Streams the response from Ollama word by word."""
    global stop_generation
    stop_generation = False
    current_chat_id = str(current_chat_id)

    if not login_info.get("logged_in", False):
        yield []
        return

    history = history or []
    history.append([message, None])

    if not message or not message.strip():
        yield history
        return
    
    try:
        response = ""
        personality_data = PERSONALITIES.get(personality)
        personality_prompt = personality_data.get("system", "") if personality_data else ""
        personality_links = personality_data.get("links", []) if personality_data else []

        # Add example response for the selected personality
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

        # Add user profile information if allowed
        if share_info_checkbox:
            user_data = load_user_data(login_info["username"])

        # Skip personality prompt for certain personalities
        skip_personality_prompt = personality in ["Uncen AI", "Uncensored AI"]
        system_message = personality_data.get("system", "") if skip_personality_prompt else f"{personality_prompt}\n\n{personality_data.get('system', '')}"

        # Create the conversation history
        messages = [{'role': 'system', 'content': system_message}]
        for prompt_name, prompt_data in PREMADE_PROMPTS.items():
            if prompt_data["user"] in message:
                messages.append({'role': 'system', 'content': prompt_data["system"]})
                break
        for user_msg, assistant_msg in history[:-1]:  # Exclude the last message (current one)
            if user_msg:
                messages.append({'role': 'user', 'content': user_msg})
            if assistant_msg:
                messages.append({'role': 'assistant', 'content': assistant_msg})
        messages.append({'role': 'user', 'content': message})

        # Perform web search if enabled
        if use_internet:
            search_results, search_links = web_search_and_scrape(message, personality, personality_links)
            if search_results:
                messages.append({'role': 'system', 'content': search_results})

        # Stream response from Ollama
        response_stream = ollama.chat(
            model=MODEL_DISPLAY_NAMES.get(ollama_model, ollama_model),
            messages=messages,
            stream=True,
            options={
                "num_predict": 1000,
                "temperature": 0.7,
                "top_k": 40,
                "top_p": 0.9
            }
        )

        current_response = ""
        for chunk in response_stream:
            if stop_generation:
                break
            if 'message' in chunk and 'content' in chunk['message']:
                response_chunk = chunk['message']['content']
                current_response += response_chunk
                new_history = history[:-1] + [[message, current_response]]
                yield new_history

        # Save final chat history
        if login_info.get("logged_in"):
            final_history = history[:-1] + [[message, current_response]]
            save_chat_history(login_info["username"], current_chat_id, final_history)

    except Exception as e:
        logging.error(f"Error in stream_chat: {str(e)}")
        yield history[:-1] + [[message, "Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại."]]

def stop_gen():
    """Stops the generation of the current response."""
    global stop_generation
    stop_generation = True

# ************************************************************************
# *                     Admin Panel Functions                           *
# ************************************************************************

def update_admin_view(selected_user):
    """Updates the admin view with the selected user's chat history."""
    if selected_user:
        user_data = load_user_data(selected_user)
        if user_data:  # Check if user_data is not None
            admin_chat_history = []
            for chat_id, chat in user_data.get("chat_history", {}).items():
                for msg in chat:
                    admin_chat_history.append(msg)
            return admin_chat_history
        else:
            return []  # Or some other appropriate message/handling
    return []

def show_all_chats():
    """Displays all chat histories for all users."""
    all_chats_history = []
    for user_file in os.listdir(USER_DATA_FOLDER):
        if os.path.isdir(os.path.join(USER_DATA_FOLDER, user_file)):
            username = user_file
            user_data = load_user_data(username)
            all_chats_history.append([None, f"=== Chat History for {username} ==="])
            for chat_id, chat in user_data.get("chat_history", {}).items():
                for msg in chat:
                    if msg[0]:
                        all_chats_history.append
