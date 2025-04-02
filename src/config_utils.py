import os
import sys
import json

DEFAULT_CONFIG_TEMPLATE = "config.json.template"

def prompt_for_config_values(template):
    """Prompt the user for configuration values based on a template."""
    config = template.copy()
    for key, value in template.items():
        if isinstance(value, str) and value.startswith("{?") and value.endswith("}"):
            label = value[2:-1]
            user_input = input(f"Please enter a value for {label}: ")
            config[key] = user_input
        elif isinstance(value, dict):
            config[key] = prompt_for_config_values(value)
    return config

def emit_default_config(config_path, in_gui=False, template_path=None):
    """Emit a default configuration file if it doesn't exist."""
    template_file_path = template_path or get_template_path()
    with open(template_file_path, 'r', encoding='utf-8') as template_file:
        template_config = json.load(template_file)
    if not in_gui:
        config = prompt_for_config_values(template_config)
    else:
        config = template_config
    config.pop("username", None)  # Remove username from the default config
    config['log_file_path'] = os.path.join(get_application_path(), "Game.log")
    with open(config_path, 'w', encoding='utf-8') as config_file:
        json.dump(config, config_file, indent=4)
    print(f"Default config emitted at {config_path}")

def get_template_path():
    """Get the path to the configuration template file."""
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        return os.path.join(sys._MEIPASS, DEFAULT_CONFIG_TEMPLATE)
    else:
        # Running in normal Python environment
        return os.path.join(os.path.dirname(__file__), DEFAULT_CONFIG_TEMPLATE)

def get_application_path():
    """Determine the correct application path whether running as .py or .exe."""
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle (exe)
        return os.path.dirname(sys.executable)
    else:
        # If the application is run as a Python script
        return os.path.dirname(os.path.abspath(__file__))

def renew_config():
    """Renew the config.json using the template while preserving specific values."""
    app_path = get_application_path()
    config_path = os.path.join(app_path, "config.json")
    template_path = get_template_path()  # Use get_template_path to determine the template path

    if not os.path.exists(template_path):
        print("Template file not found. Skipping config renewal.")
        return

    try:
        # Load the template
        with open(template_path, 'r', encoding='utf-8') as template_file:
            template_data = json.load(template_file)

        # Load the current config if it exists
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as config_file:
                current_config = json.load(config_file)
        else:
            current_config = {}

        # Preserve specific values
        for key in ["discord_webhook_url", "google_sheets_webhook", "log_file_path", "console_key"]:
            template_data[key] = current_config.get(key, template_data.get(key, ""))

        # Write the renewed config back to the file
        with open(config_path, 'w', encoding='utf-8') as config_file:
            json.dump(template_data, config_file, indent=4)

        print("Config renewed successfully.")
    except Exception as e:
        print(f"Error renewing config: {e}")
