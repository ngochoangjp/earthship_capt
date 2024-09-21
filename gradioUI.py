import gradio as gr
import gpt4allconnect as gpt4all
import json

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

def create_user_interface():
    with gr.Blocks(css=custom_css) as user_interface:
        gr.Markdown("# Earthship Capt")
        username = gr.Textbox(placeholder="Enter your username", label="Username")
        chatbot = gr.Chatbot(elem_id="chatbot")
        msg = gr.Textbox(placeholder="Type your message here...", label="User Input")
        stop_btn = gr.Button("Stop Generating")

        username.submit(gpt4all.load_user_chat, inputs=[username], outputs=[chatbot])
        msg.submit(gpt4all.user_message, [msg, chatbot, username], [msg, chatbot]).then(
            gpt4all.bot_message, [chatbot, username], chatbot
        )

        stop_btn.click(gpt4all.stop_gen)

    return user_interface

def create_master_interface():
    with gr.Blocks(css=custom_css) as master_interface:
        gr.Markdown("# Master View - GPT4All Chatbot Monitor")
        
        user_selector = gr.Dropdown(choices=[], label="Select User", interactive=True)
        master_chatbot = gr.Chatbot(elem_id="master_chatbot")
        refresh_button = gr.Button("Refresh User List")
        save_button = gr.Button("Save User Data")
        load_button = gr.Button("Load Saved User Data")

        def refresh_users():
            return gr.Dropdown(choices=gpt4all.get_all_users())

        def update_master_view(selected_user):
            return gpt4all.get_user_chat(selected_user)

        def save_user_data(selected_user):
            chat_data = gpt4all.get_user_chat(selected_user)
            with open(f"{selected_user}_chat.json", "w") as f:
                json.dump(chat_data, f)
            return "User data saved successfully."

        def load_user_data():
            with open("saved_chat.json", "r") as f:
                chat_data = json.load(f)
            return chat_data

        refresh_button.click(refresh_users, outputs=[user_selector])
        user_selector.change(update_master_view, inputs=[user_selector], outputs=[master_chatbot])
        save_button.click(save_user_data, inputs=[user_selector], outputs=[])
        load_button.click(load_user_data, outputs=[master_chatbot])

    return master_interface
