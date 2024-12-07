import gradio as gr
import ollama
import uuid
import time
import logging
import json
import os
import base64
from pathlib import Path

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
    model_tech: model_tech for model_tech in {
        "Tuanpham/t-visstar-7b:latest",
        "marco-o1",
        "llama2",
        "codellama"
    }
}
# Global variable to store user chats
user_chats = {}

# Personalities dictionary
PERSONALITIES = {
    "Trợ lý": "Bạn là một trợ lý AI hữu ích.",
    "Thư ký": "Bạn luôn trả lời câu hỏi của người dùng bằng một lời khen trước khi giải đáp.",
    "Giáo sư": "Bạn là một giáo sư có kiến thức sâu rộng, chuyên môn cao, và luôn sẵn lòng giải thích chi tiết các khái niệm phức tạp cho học sinh một cách dễ hiểu nhất.",
    "Chuyên gia tâm lý": "Bạn là một chuyên gia tâm lý tận tâm, luôn lắng nghe, đồng cảm và tư vấn cách vượt qua khó khăn, giúp người dùng cảm thấy được hỗ trợ và hiểu rõ hơn về cảm xúc của mình.",
    "Bạn thân": "Bạn là một người bạn thân thiết, luôn sẵn lòng hỗ trợ, chia sẻ niềm vui và nỗi buồn cùng người dùng, mang lại sự gần gũi và tin tưởng.",
    "Bạn trai": "Bạn là một người bạn trai thân thiện, luôn lắng nghe và chia sẻ tình cảm với người khác, mang lại sự an ủi và hạnh phúc.",
    "Bạn gái": "Bạn là một người bạn gái dịu dàng, luôn quan tâm đến cảm xúc của người khác và tạo ra không khí ấm áp trong mọi cuộc trò chuyện."
}

PREMADE_PROMPTS = {
    "Dịch văn bản": "Bạn là chuyên gia ngôn ngữ có thể dịch tốt mọi thứ tiếng. Hãy dịch đoạn văn sau sang tiếng Việt một cách tự nhiên và chuẩn chính xác, đảm bảo giữ nguyên ý nghĩa gốc và sử dụng từ vựng phù hợp: ",
    "Giải thích khoa học": "Bạn là một nhà khoa học. Hãy giải thích hiện tượng sau để một đứa trẻ 10 tuổi cũng có thể hiểu được, sử dụng ngôn ngữ đơn giản và ví dụ sinh động: ",
    "Viết phần mềm": "Bạn là một lập trình viên giỏi. Hãy giúp tôi giải quyết vấn đề lập trình này bằng cách cung cấp mã nguồn chi tiết, giải thích từng bước và đưa ra lời khuyên để tránh lỗi tương tự trong tương lai: ",
    "Sáng tác truyện": "Bạn là một nhà văn tài năng. Hãy viết một đoạn văn ngắn khoảng 100 từ về chủ đề sau, sử dụng ngôn ngữ sáng tạo và hấp dẫn: ",
    "Tư vấn tài chính": "Bạn là một chuyên gia tài chính. Hãy tư vấn cho tôi về vấn đề tài chính này bằng cách cung cấp thông tin chi tiết, ví dụ minh họa, và lời khuyên thực tế để ứng dụng trong cuộc sống hàng ngày: ",
    "Tham vấn tâm lý": "Bạn là chuyên gia tâm lý học. Hãy cung cấp sự hỗ trợ tâm lý cho người dùng về chủ đề sau, bao gồm việc lắng nghe, đưa ra lời khuyên phù hợp và hướng dẫn cách xử lý tình huống: ",
    "Tư vấn tập GYM": "Bạn là huấn luyện viên thể hình chuyên nghiệp. Hãy tư vấn cho tôi một chương trình tập luyện GYM phù hợp với mức độ hiện tại của tôi, bao gồm các bài tập chính, lịch trình tập luyện, và lời khuyên về cách giữ động lực dựa trên thông tin cân nặng và chiều cao và % cơ của tôi sau đây: ",
    "Tư vấn dinh dưỡng": "Bạn là chuyên gia dinh dưỡng. Hãy tư vấn cho tôi về chế độ ăn uống phù hợp với mục tiêu sức khỏe của tôi (ví dụ: giảm cân, tăng cơ, giữ gìn sức khỏe), bao gồm lời khuyên về thực phẩm, khẩu phần, và lịch trình ăn uống: ",
    "Sáng tác lời bài hát": "Bạn là một nhà thơ và nhạc sĩ. Hãy sáng tác lời bài hát ngắn (khoảng 8-16 câu) về chủ đề sau, sử dụng ngôn ngữ giàu cảm xúc và ý nghĩa sâu sắc: ",
    "Sáng tác nhạc": "Bạn là nhạc sĩ tài năng. Hãy sáng tác một bài hát với lời cau về chủ đề sau, sử dụng nhịp điệu phù hợp và âm nhạc dễ nghe: "
}

# Global variable to control generation
stop_generation = False

# Folder to store user data
USER_DATA_FOLDER = "userdata"
os.makedirs(USER_DATA_FOLDER, exist_ok=True)

def save_user_data(username, data):
    file_path = os.path.join(USER_DATA_FOLDER, f"{username}.json")
    with open(file_path, 'w') as f:
        json.dump(data, f)

def load_user_data(username):
    file_path = os.path.join(USER_DATA_FOLDER, f"{username}.json")
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            data = json.load(f)
        if "chat_history" in data:
            # Convert old format to new format if necessary
            if data["chat_history"] and isinstance(data["chat_history"][0], dict):
                data["chat_history"] = [
                    [msg["content"], None] if msg["role"] == "user" else [None, msg["content"]]
                    for msg in data["chat_history"]
                ]
            # Ensure the format is correct
            data["chat_history"] = [
                [msg[0], msg[1]] for msg in data["chat_history"] if isinstance(msg, list) and len(msg) == 2
            ]
        else:
            data["chat_history"] = []
        return data
    return None

# Global variable to control generation
stop_generation = False

PROMPT_TEMPLATE = """<|im_start|>system
{system_message}<|im_end|>
<|im_start|>user
{prompt}<|im_end|>
<|im_start|>assistant"""
def create_new_user(username, password):
    if not username or not password:
        return {
            "visible": True,
            "chat_visible": False,
            "login_info": {"username": "", "password": "", "logged_in": False},
            "chatbot": [],
            "user_avatar": None,
            "bot_avatar": None,
            "login_message": "Vui lòng nhập tên đăng nhập và mật khẩu."
        }
    
    user_data = load_user_data(username)
    if user_data:
        return {
            "visible": True,
            "chat_visible": False,
            "login_info": {"username": "", "password": "", "logged_in": False},
            "chatbot": [],
            "user_avatar": None,
            "bot_avatar": None,
            "login_message": "Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác."
        }
    
    new_user_data = {
        "password": password,
        "chat_history": [],
        "user_avatar": None,
        "bot_avatar": None
    }
    save_user_data(username, new_user_data)
    
    return {
        "visible": False,
        "chat_visible": True,
        "login_info": {"username": username, "password": password, "logged_in": True},
        "chatbot": [],
        "user_avatar": None,
        "bot_avatar": None,
        "login_message": ""
    }
def generate_response(message, history, personality, ollama_model):
    global stop_generation
    stop_generation = False
    try:
        response = ""
        personality_prompt = PERSONALITIES.get(personality, "")
        # Create the conversation history
        messages = []
          # Add system message first
        messages.append({
            'role': 'system',
            'content': personality_prompt
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
                yield response   
    
    except Exception as e:
        logging.error(f"Error generating response: {str(e)}")
        yield "Xin lỗi, nhưng tôi đã gặp lỗi trong khi xử lý yêu cầu của bạn. Vui lòng thử lại sau."

def stop_gen():
    global stop_generation
    stop_generation = True

# Custom CSS and the rest of the code remains the same as in the original script 
# (previous user_interface and master_interface functions)

# Custom CSS to make the interface look more like Claude and improve user-friendliness
custom_css = """
body {
    font-family: Arial, sans-serif;
    background-color: #f5f5f5;
    color: #333;
}
.container {
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
}
.user {
    background-color: #95C8D8;
    color: #000000;
    padding: 15px;
    border-radius: 15px;
    margin-bottom: 10px;
}
.bot {
    background-color: #f0f0f0;
    color: #000000;
    padding: 15px;
    border-radius: 15px;
    margin-bottom: 10px;
}
.message {
    font-size: 16px;
    line-height: 1.5;
}
#chatbot, #master_chatbot {
    background-color: #ffffff;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    padding: 20px;
}
.input-group {
    margin-bottom: 15px;
}
.input-group label {
    display: block;
    margin-bottom: 5px;
    font-weight: bold;
}
.input-group input[type="text"],
.input-group input[type="password"],
.input-group select {
    width: 100%;
    padding: 10px;
    border: 1px solid #ccc;
    border-radius: 5px;
}
.button-group {
    display: flex;
    justify-content: space-between;
    margin-top: 15px;
}
button {
    background-color: #4CAF50;
    color: white;
    border: none;
    padding: 10px 20px;
    text-align: center;
    text-decoration: none;
    display: inline-block;
    font-size: 16px;
    margin: 4px 2px;
    cursor: pointer;
    border-radius: 5px;
    transition: background-color 0.3s;
}
button:hover {
    background-color: #45a049;
}
.premade-prompt {
    margin: 5px;
    padding: 10px;
    border: 1px solid #ccc;
    border-radius: 5px;
    cursor: pointer;
    background-color: #f9f9f9;
    transition: background-color 0.3s;
}
.premade-prompt:hover {
    background-color: #e0e0e0;
}
.premade-prompt.active {
    background-color: #4CAF50;
    color: white;
}
"""

# User Interface
def create_user_interface():
    with gr.Blocks(css=custom_css) as user_interface:
        gr.Markdown("# Earthship AI")
        
        # Enable Gradio's built-in queue
        user_interface.queue(
            default_concurrency_limit=5,  # Number of simultaneous requests
            max_size=20,  # Maximum number of requests in queue
            api_open=True
            )
        
        # Optional: Add queue status indicator
        queue_status = gr.Markdown("Queue Status: Ready")
        
        def update_queue_status(request):
            """Track queue status"""
            queue_size = user_interface.queue.queue.qsize()
            return f"Queue Status: {queue_size} waiting requests"
        
        login_info = gr.State(value={"username": "", "password": "", "logged_in": False})
        with gr.Group() as login_group:
            with gr.Column():
                gr.Markdown("## Đăng nhập")
                username = gr.Textbox(label="Tên đăng nhập", placeholder="Nhập tên đăng nhập")
                password = gr.Textbox(label="Mật khẩu", placeholder="Nhập mật khẩu", type="password")
                with gr.Row():
                    login_button = gr.Button("Đăng nhập", variant="primary")
                    create_user_button = gr.Button("Tạo người dùng mới")
                login_message = gr.Markdown(visible=False)
        
        with gr.Group(visible=False) as chat_group:
            with gr.Row():
                with gr.Column(scale=1):
                    personality = gr.Dropdown(
                        choices=list(PERSONALITIES.keys()),
                        value="Trợ lý",
                        label="Chọn tính cách AI",
                        interactive=True
                    )
                    model = gr.Dropdown(
                        choices=list(MODEL_DISPLAY_NAMES.keys()),  # Use display names instead
                        value="Vietai",  # Set default to Vietai
                        label="Chọn mô hình AI",
                        interactive=True
                    )
                    with gr.Column():
                        gr.Markdown("### Thư viện công cụ")
                        premade_prompt_buttons = [gr.Button(prompt_name) for prompt_name in PREMADE_PROMPTS.keys()]
                with gr.Column(scale=4):
                    chatbot = gr.Chatbot(elem_id="chatbot", height=500)
                    with gr.Column(scale=1):
                        msg = gr.Textbox(
                            label="Nhập tin nhắn của bạn",
                            placeholder="Nhập tin nhắn và nhấn Enter",
                            elem_id="msg"
                        )
                        send = gr.Button("Gửi", variant="primary")
                    with gr.Row():
                        clear = gr.Button("Xóa lịch sử trò chuyện")
                        stop = gr.Button("Dừng tạo câu trả lời")
         # Update the queue status periodically
        def update_queue_status():
            queue_size = request_queue.queue.qsize()
            active_users = len(request_queue.active_users)
            return f"Queue Status: {queue_size} waiting, {active_users} active"

                        
        user_avatar = gr.Image(label="User Avatar", type="filepath", visible=False)
        bot_avatar = gr.Image(label="Bot Avatar", type="filepath", visible=False)
        def handle_create_user(username, password):
            result = create_new_user(username, password)
            return [
                gr.update(visible=result["visible"]),
                gr.update(visible=result["chat_visible"]),
                result["login_info"],
                result["chatbot"],
                result["user_avatar"],
                result["bot_avatar"],
                gr.update(visible=True, value=result["login_message"])
            ]

        create_user_button.click(
            handle_create_user,
            inputs=[username, password],
            outputs=[login_group, chat_group, login_info, chatbot, user_avatar, bot_avatar, login_message]
        )    
        def create_new_user(username, password):
            if not username or not password:
                return (
                    gr.update(visible=True),
                    gr.update(visible=False),
                    {"username": "", "password": "", "logged_in": False},
                    [],
                    None,
                    None,
                    gr.update(visible=True, value="Vui lòng nhập tên đăng nhập và mật khẩu.")
                )
            
            user_data = load_user_data(username)
            if user_data:
                return (
                    gr.update(visible=True),
                    gr.update(visible=False),
                    {"username": "", "password": "", "logged_in": False},
                    [],
                    None,
                    None,
                    gr.update(visible=True, value="Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.")
                )
            
            new_user_data = {
                "password": password,
                "chat_history": [],
                "user_avatar": None,
                "bot_avatar": None
            }
            save_user_data(username, new_user_data)
            
            login_info = {"username": username, "password": password, "logged_in": True}
            return (
                gr.update(visible=False),
                gr.update(visible=True),
                login_info,
                [],
                None,
                None,
                gr.update(visible=False)
            )
        
        def login(username, password):
            user_data = load_user_data(username)
            if not user_data:
                return (
                    gr.update(visible=True),
                    gr.update(visible=False),
                    {"username": "", "password": "", "logged_in": False},
                    [],
                    None,
                    None,
                    gr.update(visible=True, value="Tên đăng nhập không tồn tại. Vui lòng tạo người dùng mới.")
                )
            elif user_data["password"] != password:
                return (
                    gr.update(visible=True),
                    gr.update(visible=False),
                    {"username": "", "password": "", "logged_in": False},
                    [],
                    None,
                    None,
                    gr.update(visible=True, value="Mật khẩu không đúng. Vui lòng thử lại.")
                )
            else:
                login_info = {"username": username, "password": password, "logged_in": True}
                return (
                    gr.update(visible=False),
                    gr.update(visible=True),
                    login_info,
                    user_data.get("chat_history", [])[-10:],
                    user_data.get("user_avatar"),
                    user_data.get("bot_avatar"),
                    gr.update(visible=False)
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
                for chunk in generate_response(user_message, history[:-1], personality, ollama_model):
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

        def add_premade_prompt(prompt_text, current_msg):
            return current_msg + prompt_text if current_msg else prompt_text

        login_button.click(
            login,
            inputs=[username, password],
            outputs=[login_group, chat_group, login_info, chatbot, user_avatar, bot_avatar, login_message]
        )

        create_user_button.click(
            create_new_user,
            inputs=[],
            outputs=[login_group, chat_group, login_info, chatbot, user_avatar, bot_avatar, login_message]
        )

        msg.submit(user_msg, [msg, chatbot, login_info], [msg, chatbot]).then(
            bot_response, [chatbot, login_info, personality, model], chatbot
        )
        send.click(user_msg, [msg, chatbot, login_info], [msg, chatbot]).then(
            bot_response, [chatbot, login_info, personality, model], chatbot
        )

        clear.click(clear_chat, [login_info], chatbot)
        stop.click(stop_gen)

        for button, prompt_text in zip(premade_prompt_buttons, PREMADE_PROMPTS.values()):
            button.click(
                add_premade_prompt,
                inputs=[gr.State(prompt_text), msg],
                outputs=[msg]
            )

    return user_interface

# Master Interface
def create_master_interface():
    with gr.Blocks(css=custom_css) as master_interface:
        gr.Markdown("# Captain view")
        
        with gr.Row():
            user_selector = gr.Dropdown(choices=[], label="Select User", interactive=True)
            refresh_button = gr.Button("Refresh User List")
        
        master_chatbot = gr.Chatbot(elem_id="master_chatbot", height=500)

        # Refresh user list based on existing files in userdata folder
        def refresh_users():
            user_files = os.listdir(USER_DATA_FOLDER)
            user_names = [os.path.splitext(f)[0] for f in user_files if f.endswith('.json')]
            return gr.Dropdown(choices=user_names)

        # Update chat history for selected user
        def update_master_view(selected_user):
            user_data = load_user_data(selected_user)
            return user_data.get("chat_history", [])

        # Handle button and dropdown interactions
        refresh_button.click(refresh_users, outputs=[user_selector])
        user_selector.change(update_master_view, inputs=[user_selector], outputs=[master_chatbot])

    return master_interface

# Create and launch interfaces
user_interface = create_user_interface()
master_interface = create_master_interface()

# Launch user interface with CORS configuration
user_interface.launch(
    server_name="127.0.0.1",  # Changed from 127.0.0.1 to allow external connections
    server_port=7871,
    share=False,
)

# Launch master interface
master_interface.launch(server_name="127.0.0.1", server_port=7870, share=False)