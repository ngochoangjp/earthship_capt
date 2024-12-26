import os
import json
import gradio as gr
from datetime import datetime
from gpt4allmaster import (
    load_global_prompts,
    PERSONALITIES,
    PREMADE_PROMPTS,
    get_all_usernames,
    get_chat_titles,
    get_avatar_path,
    load_user_data,
    save_user_data,
    load_chat_history,
    save_chat_history,
    create_new_user,
    login,
    error_response,
    success_response,
    new_chat,
    load_selected_chat,
    add_premade_prompt,
    rename_chat,
    save_profile_info,
    load_profile_info,
    generate_better_prompt,
    regenerate_response,
    stream_chat,
    stop_gen,
    update_admin_view,
    show_all_chats,
    MODEL_DISPLAY_NAMES
)

# Load configuration from config.json
with open('config.json', 'r') as f:
    config = json.load(f)

USER_DATA_FOLDER = config.get("user_data_folder", "userdata")
PROMPTS_FILE_PATH = config.get("prompts_file_path", "z:/This/This/My APP/Earthship_capt/prompts.txt")
AVATAR_IMAGES_PATH = config.get("avatar_images_path", "icons")
MODEL_NAME = config.get("model_name", "Tuanpham/t-visstar-7b:latest")
SERVER_PORT = config.get("server_port", 7871)

def create_user_interface():
    """Creates the Gradio user interface."""
    if not PERSONALITIES:
        load_global_prompts()

    with gr.Blocks(css="""
        .message {
            display: flex;
            align-items: flex-start;
            gap: 10px;
        }
        .message-content {
            flex-grow: 1;
            position: relative;
        }
        .message-actions {
            display: none;
            position: absolute;
            right: 10px;
            top: 5px;
            gap: 5px;
        }
        .message:hover .message-actions {
            display: flex;
        }
        .action-button {
            padding: 2px 5px;
            border-radius: 3px;
            cursor: pointer;
            background: rgba(0,0,0,0.1);
            font-size: 12px;
        }
        .action-button:hover {
            background: rgba(0,0,0,0.2);
        }
        .input-actions {
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            display: flex;
            gap: 5px;
        }
        .avatar-container img {
            pointer-events: none;
        }
        .gr-body {
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }
        .gr-main {
            flex: 1;
            display: flex;
            flex-direction: column;
            max-width: 100%;
            padding: 10px;
        }
        .gr-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .gr-column {
            flex: 1;
            min-width: 200px;
            max-width: 100%;
        }
        #chatbot {
            max-width: 100%;
        }
        .gr-textbox {
            max-width: 100%;
        }
        .gr-dropdown {
            max-width: 100%;
        }
        .gr-button {
            max-width: 100%;
        }
        """) as user_interface:
        gr.Markdown("# Earthship AI")

        # Initialize user data directory
        os.makedirs(USER_DATA_FOLDER, exist_ok=True)

        # Enable Gradio's built-in queue
        user_interface.queue(default_concurrency_limit=5, max_size=20, api_open=True)

        # States
        login_info = gr.State(value={"username": "", "password": "", "logged_in": False, "is_admin": False})
        current_chat_id = gr.State()
        selected_user = gr.State(value="0")

        # Components
        user_avatar = gr.Image(label="User Avatar", type="filepath", visible=False)
        bot_avatar = gr.Image(label="Bot Avatar", type="filepath", visible=False)

        # --- Login/Registration ---
        with gr.Group() as login_group:
            with gr.Column():
                gr.Markdown("## Đăng nhập")
                username = gr.Textbox(label="Tên đăng nhập", placeholder="Nhập tên đăng nhập")
                password = gr.Textbox(label="Mật khẩu", placeholder="Nhập mật khẩu", type="password")
                with gr.Row():
                    login_button = gr.Button("Đăng nhập", variant="primary")
                    create_user_button = gr.Button("Tạo người dùng mới")
                login_message = gr.Markdown(visible=False)

        # --- Admin Panel ---
        with gr.Group(visible=False) as admin_panel:
            gr.Markdown("## Captain View")
            with gr.Row():
                user_selector = gr.Dropdown(choices=get_all_usernames(), label="Select User", interactive=True)
                refresh_button = gr.Button("Refresh User List")
                show_all_chats_button = gr.Button("Show All Chat Histories")
            admin_chatbot = gr.Chatbot(elem_id="admin_chatbot", height=500)

        # --- Main Chat Interface ---
        with gr.Group(visible=False) as chat_group:
            with gr.Row():
                # --- User Profile ---
                with gr.Column(scale=1):
                    gr.Markdown("## Thông tin cá nhân")
                    gr.Markdown("AI lưu lại thông tin của bạn chỉ để hiểu bạn hơn.")
                    real_name = gr.Textbox(label="Họ và tên", placeholder="Nhập tên của bạn")
                    age = gr.Number(label="Tuổi")
                    gender = gr.Textbox(label="Giới tính", placeholder="Nhập giới tính của bạn")
                    vegan_checkbox = gr.Checkbox(label="Ăn chay", value=False, interactive=True)
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

                # --- Chat and Inputs ---
                with gr.Column(scale=3):
                    personality = gr.Dropdown(choices=list(PERSONALITIES.keys()), value=list(PERSONALITIES.keys())[0], label="Chọn tính cách AI", interactive=True)
                    chatbot = gr.Chatbot(
                        elem_id="chatbot",
                        height=1000,
                        render=True,
                        elem_classes="custom-chatbot",
                        render_markdown=True,
                        container=True,
                        avatar_images=[None, get_avatar_path(list(PERSONALITIES.keys())[0])],
                        show_copy_button=True,
                        show_share_button=False,
                        bubble_full_width=True,
                        show_copy_all_button=True,
                        autoscroll=True,
                    )

                    with gr.Row():
                        with gr.Column(scale=12):
                            msg = gr.Textbox(
                                label="Nhập tin nhắn của bạn",
                                placeholder="Nhập tin nhắn và nhấn Enter",
                                elem_id="msg",
                                container=True,
                                show_copy_button=True,
                                max_length=1000,
                            )
                            prompt_helper = gr.Button("Cải thiện nội dung", elem_classes="action-button", visible=True)
                        with gr.Column(scale=1):
                            send = gr.Button("Gửi", variant="primary")
                            stop = gr.Button("Dừng tạo câu trả lời")

                # --- Settings and Tools ---
                with gr.Column(scale=1):
                    model = gr.Dropdown(choices=list(MODEL_DISPLAY_NAMES.keys()), value=list(MODEL_DISPLAY_NAMES.keys())[0], label="Chọn mô hình AI", interactive=True)
                    use_internet_checkbox = gr.Checkbox(label="Sử dụng Internet để tìm kiếm", value=False)
                    new_chat_button = gr.Button("Bắt đầu cuộc trò chuyện mới")
                    gr.Markdown("### Thư viện công cụ")
                    premade_prompt_buttons = [gr.Button(prompt_name) for prompt_name in PREMADE_PROMPTS.keys()]
                    gr.Markdown("## Lịch sử trò chuyện")
                    chat_history_dropdown = gr.Dropdown(choices=[], label="Chọn lịch sử trò chuyện", interactive=True)
                    with gr.Row():
                        load_chat_button = gr.Button("Load Chat")
                        rename_chat_button = gr.Button("Rename Chat")
                    rename_chat_textbox = gr.Textbox(placeholder="Enter new chat name", visible=False)

        # ************************************************************************
        # *                         Event Handlers                          
        # 
        # *
        # ************************************************************************

        # --- Login/Registration ---
        login_button.click(login, [username, password], [login_group, chat_group, login_info, chatbot, current_chat_id, personality, login_message, chat_history_dropdown, admin_panel, selected_user, admin_chatbot, personality, model, real_name, age, gender, height, weight, job, muscle_percentage, passion, vegan_checkbox, personality_text, save_profile, hide_profile_button, show_profile_button, password_input, password_error])
        create_user_button.click(create_new_user, [username, password], [login_group, chat_group, login_info, chatbot, user_avatar, bot_avatar, login_message, user_selector, admin_panel, current_chat_id, chat_history_dropdown, personality, model])

        # --- Admin Panel ---
        refresh_button.click(lambda: None, [], [])
        user_selector.change(update_admin_view, inputs=[selected_user], outputs=[admin_chatbot])
        show_all_chats_button.click(show_all_chats, outputs=[admin_chatbot])

        # --- Profile Management ---
        save_profile.click(save_profile_info, [real_name, age, gender, height, weight, job, muscle_percentage, passion, vegan_checkbox, personality_text, login_info], [save_profile, real_name, age, gender, height, weight, job, muscle_percentage, passion, vegan_checkbox, personality_text, show_profile_button])
        hide_profile_button.click(lambda: ([gr.update(visible=False) for _ in range(11)] + [gr.update(visible=False), gr.update(visible=True)]), [], [real_name, age, gender, height, weight, job, muscle_percentage, passion, vegan_checkbox, personality_text, save_profile, hide_profile_button, show_profile_button])
        show_profile_button.click(lambda: [gr.update(visible=True), gr.update(visible=True, value="")], None, [password_input, password_error])
        password_input.submit(lambda pwd, info: ([gr.update(visible=True) for _ in range(10)] + [gr.update(visible=True), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)] if info["logged_in"] and load_user_data(info["username"]).get("password") == pwd else [gr.update(visible=False) for _ in range(10)] + [gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), gr.update(visible=True, value="Incorrect password")]) , [password_input, login_info], [real_name, age, gender, height, weight, job, muscle_percentage, passion, vegan_checkbox, personality_text, save_profile, hide_profile_button, password_input, password_error])

        # --- Chat and Input ---
        def on_submit(message, history, login_info, current_chat_id, personality_choice, model_choice, use_internet):
            history = history or []
            history.append([message, None])
            try:
                for new_history in stream_chat(message, history[:-1], login_info, personality_choice, model_choice, current_chat_id, use_internet):
                    yield new_history
            except Exception as e:
                logging.error(f"Error in on_submit: {str(e)}")
                history.append([message, "Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại."])
                yield history

        msg.submit(on_submit, [msg, chatbot, login_info, current_chat_id, personality, model, use_internet_checkbox], chatbot).then(lambda: "", None, msg)
        send.click(on_submit, [msg, chatbot, login_info, current_chat_id, personality, model, use_internet_checkbox], chatbot).then(lambda: "", None, msg)
        stop.click(stop_gen)
        prompt_helper.click(generate_better_prompt, [msg, personality], [msg])

        # --- Settings and Tools ---
        new_chat_button.click(new_chat, [login_info, personality, model], [chatbot, current_chat_id, chat_history_dropdown])
        personality.change(new_chat, [login_info, personality, model], [chatbot, current_chat_id, chat_history_dropdown])
        personality.change(lambda personality_name: gr.update(avatar_images=[None, get_avatar_path(personality_name)]), [personality], [chatbot])
        chatbot.regenerate = lambda history, idx: regenerate_response(history, idx, login_info, personality.value, model.value)
        for button, prompt_name in zip(premade_prompt_buttons, PREMADE_PROMPTS.keys()):
            button.click(add_premade_prompt, [gr.State(prompt_name), msg, chatbot], [msg, chatbot])
        load_chat_button.click(load_selected_chat, [login_info, chat_history_dropdown], [chatbot, current_chat_id])
        rename_chat_button.click(lambda: gr.update(visible=True), [], [rename_chat_textbox])
        rename_chat_textbox.submit(rename_chat, [rename_chat_textbox, current_chat_id, login_info], [chat_history_dropdown, rename_chat_textbox])

    return user_interface

if __name__ == "__main__":
    user_interface = create_user_interface()
    user_interface.launch(server_name="127.0.0.1", server_port=SERVER_PORT, share=False)
