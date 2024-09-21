import threading
import time
import gpt4allconnect as gpt4all
import gradioUI

# Initialize the model
gpt4all.initialize_model()

# Create and launch interfaces
user_interface = gradioUI.create_user_interface()
master_interface = gradioUI.create_master_interface()

# Launch user interface
user_thread = threading.Thread(target=lambda: user_interface.launch(server_name="127.0.0.1", server_port=7800, share=True))
user_thread.start()

# Launch master interface
master_thread = threading.Thread(target=lambda: master_interface.launch(server_name="127.0.0.1", server_port=7801))
master_thread.start()

# Keep the main thread alive
while True:
    time.sleep(1)
