# ... (other parts of the create_user_interface function)

                    # ... (profile fields: real_name, age, gender, etc.)

                    save_profile = gr.Button("Lưu thông tin", variant="primary", visible=False)
                    hide_profile_button = gr.Button("Ẩn thông tin cá nhân")
                    show_profile_button = gr.Button("Chỉnh sửa thông tin cá nhân", visible=False)
                    password_input = gr.Textbox(label="Nhập mật khẩu", type="password", visible=False)
                    password_error = gr.Markdown(visible=False)
                    confirm_button = gr.Button("Yes, hide my info", visible=False)  # Create the confirm_button

                    # ... (other event handlers)

                    password_input.submit(
                        fn=lambda pwd, info: (
                            [gr.update(visible=True, value=load_user_data(info["username"]).get("profile", {}).get("real_name", "") if load_user_data(info["username"]) is not None else ""),
                             gr.update(visible=True, value=load_user_data(info["username"]).get("profile", {}).get("age", "") if load_user_data(info["username"]) is not None else ""),
                             gr.update(visible=True, value=load_user_data(info["username"]).get("profile", {}).get("gender", "") if load_user_data(info["username"]) is not None else ""),
                             gr.update(visible=True, value=load_user_data(info["username"]).get("profile", {}).get("height", "") if load_user_data(info["username"]) is not None else ""),
                             gr.update(visible=True, value=load_user_data(info["username"]).get("profile", {}).get("weight", "") if load_user_data(info["username"]) is not None else ""),
                             gr.update(visible=True, value=load_user_data(info["username"]).get("profile", {}).get("job", "") if load_user_data(info["username"]) is not None else ""),
                             gr.update(visible=True, value=load_user_data(info["username"]).get("profile", {}).get("muscle_percentage", "") if load_user_data(info["username"]) is not None else ""),
                             gr.update(visible=True, value=load_user_data(info["username"]).get("profile", {}).get("fat_percentage", "") if load_user_data(info["username"]) is not None else ""),
                             gr.update(visible=True, value=load_user_data(info["username"]).get("profile", {}).get("vegan", False) if load_user_data(info["username"]) is not None else False),
                             gr.update(visible=True, value=load_user_data(info["username"]).get("profile", {}).get("personality", "") if load_user_data(info["username"]) is not None else "")] +
                            [gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)]
                            if info["logged_in"] and load_user_data(info["username"]).get("password") == pwd
                            else [gr.update(visible=False) for _ in range(10)] + [gr.update(visible=False), gr.update(visible=True), gr.update(visible=True), gr.update(visible=True, value="Incorrect password")]
                        ),
                        inputs=[password_input, login_info],
                        outputs=[real_name, age, gender, height, weight, job, muscle_percentage, fat_percentage, vegan_checkbox, personality_text, save_profile, show_profile_button, password_input, password_error]
                    )

                    # ... (other event handlers)
                    confirm_button.click(
                        fn=lambda: [gr.update(visible=False) for _ in range(11)] + [gr.update(visible=True), gr.update(visible=False)],
                        inputs=[],
                        outputs=[real_name, age, gender, height, weight, job, muscle_percentage, fat_percentage, vegan_checkbox, personality_text, save_profile, show_profile_button, confirm_button]
                    )
                    # ... (rest of the create_user_interface function)