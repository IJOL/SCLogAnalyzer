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
