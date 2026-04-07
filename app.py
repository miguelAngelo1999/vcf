import os
import sys
import json
import webview
import threading
import importlib
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import logging
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config['TEMPLATES_AUTO_RELOAD'] = False

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app_debug.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

import time
from updater import check_for_updates, download_and_run_installer
# This import is still good practice to encourage the correct backend
if sys.platform == 'win32':
    import webview.platforms.edgechromium


# Version for update checking
APP_VERSION = "2.9.42"

# CRITICAL FIX: Set working directory to exe location
if getattr(sys, 'frozen', False):
    # Running as PyInstaller exe
    exe_dir = os.path.dirname(sys.executable)
    os.chdir(exe_dir)
    print(f"EXE MODE: Changed working directory to: {exe_dir}")
else:
    # Running as script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"SCRIPT MODE: Working directory: {script_dir}")

from vcf_extractor import VCFProcessor
import subprocess
import configparser
import json
import ast
import os
import logging
from webview.dom import DOMEventHandler
import time
import signal # Import signal module


#  >>> Função para lidar com caminhos em modo de script e .exe
def resource_path(relative_path):
    """ Obtém o caminho absoluto para o recurso, funciona para dev e para PyInstaller """
    try:
        # PyInstaller cria uma pasta temp e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# --- Setup ---
static_folder_path = resource_path('static')
template_folder_path = resource_path('templates')
app.static_folder = static_folder_path
app.template_folder = template_folder_path

session_data = {}
session_lock = threading.Lock()

# Use AppData for user settings
if getattr(sys, 'frozen', False):
    appdata_path = os.path.expanduser("~/AppData/Local/VCF_PROCESSOR")
    os.makedirs(appdata_path, exist_ok=True)
    config_ini_path = os.path.join(appdata_path, 'config.ini')
    application_path = os.path.dirname(sys.executable)
else:
    config_ini_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    application_path = os.path.dirname(os.path.abspath(__file__))

LOG_FILENAME = os.path.join(application_path, "NAO_APAGAR.log")

# Log file location with fallback
def get_log_filename():
    import tempfile
    log_locations = [
        os.path.join(application_path, "NAO_APAGAR.log"),  # Current directory
        os.path.join(os.path.expanduser("~"), 'Documents', 'VCF_Processor_logs', 'NAO_APAGAR.log'),  # User Documents
        os.path.join(os.environ.get('PROGRAMDATA', 'C:\\ProgramData'), 'VCF_Processor', 'NAO_APAGAR.log'),  # ProgramData
        os.path.join(os.path.expanduser("~"), 'AppData', 'Local', 'VCF_Processor', 'NAO_APAGAR.log'),  # Local AppData
    ]
    
    for log_path in log_locations:
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            
            # Test if we can write to the location
            test_file = os.path.join(os.path.dirname(log_path), 'test_write.tmp')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            
            return log_path
        except (PermissionError, OSError):
            continue
    
    # Fallback to temp directory
    temp_log = os.path.join(tempfile.gettempdir(), 'VCF_Processor_NAO_APAGAR.log')
    print(f"⚠️  Warning: Using temp directory for log file: {temp_log}")
    return temp_log

# Centralized log path configuration
LOG_PATH = get_log_filename()

# Update global references to use the centralized path
LOG_FILENAME = LOG_PATH

def initialize_log_from_xlsx():
    """Initialize log from NAO_APAGAR.xlsx in Documents folder on first run"""
    if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 0:
        return
    
    docs_path = os.path.expanduser("~/Documents")
    xlsx_path = os.path.join(docs_path, "NAO_APAGAR.xlsx")
    
    if not os.path.exists(xlsx_path):
        return
    
    try:
        import pandas as pd
        df = pd.read_excel(xlsx_path)
        
        phone_columns = [col for col in df.columns if 'phone' in col.lower() or 'telefone' in col.lower() or 'numero' in col.lower()]
        
        if not phone_columns:
            phone_columns = [df.columns[0]]
        
        numbers = set()
        for col in phone_columns:
            for value in df[col].dropna():
                digits = ''.join(filter(str.isdigit, str(value)))
                if len(digits) >= 8:
                    numbers.add(int(digits))
        
        with open(LOG_PATH, 'w', encoding='utf-8') as f:
            for number in sorted(numbers):
                f.write(f"{number}\n")
        
        logging.info(f"Initialized log with {len(numbers)} numbers from {xlsx_path}")
    except Exception as e:
        logging.error(f"Failed to initialize log from xlsx: {e}")


initial_data_for_ui = {
    "vcf_path": "",
    "duplicates": []
}

def create_default_config(config_path):
    default_config = '''[Settings]
light_mode = follow
excel_format = standard
sender_indicator = Contato Recebido

[Titles]
titles_to_remove = [
    "Adv", "Advogado", "AEE", "Amigos", "Amor", "Apartamento", "Avó", "Avô", "Banco", "Bradesco", "Casa", "CEESPI", "Cel", "cell", "Clube", "Consultório", "Coord", "Coordenadora", "Coronel", "Costureira", "Cunhada", "Cunhado", "Diretor", "Dona", "Doutor", "Doutora", "DR", "Dr", "DRA", "Dra", "Empresa", "Eng", "Engenheiro", "Escritório", "Esposa", "Esposo", "Família", "Fazenda", "Filha", "Filho", "Igreja", "Ir", "Irmã", "Irmão", "meu", "Mr", "Mrs", "Ms", "Mãe", "Namorada", "Namorado", "Neta", "Neto", "new", "nome", "now", "PAE", "PAEE", "Pai", "Pessoal", "premium", "Prima", "PROF", "Prof", "Professor", "Professora", "rapaz", "Seu", "seu", "Sobrinha", "Sobrinho", "Sr", "Sra", "Sítio", "Tia", "Tio", "Trabalho", "Vó", "Vô"
]
'''
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(default_config)
        logging.info(f"Created default config at: {config_path}")
    except Exception as e:
        logging.error(f"Failed to create config: {e}")

def read_config_ini():
    if getattr(sys, 'frozen', False):
        appdata_path = os.path.expanduser("~/AppData/Local/VCF_PROCESSOR")
        config_paths = [os.path.join(appdata_path, 'config.ini'), os.path.join(sys._MEIPASS, 'config.ini'), config_ini_path]
    else:
        config_paths = [config_ini_path]
    
    for path in config_paths:
        if os.path.exists(path):
            config_ini_path_used = path
            break
    else:
        if getattr(sys, 'frozen', False):
            config_ini_path_used = os.path.join(appdata_path, 'config.ini')
        else:
            config_ini_path_used = config_ini_path
        create_default_config(config_ini_path_used)
        
    if not os.path.exists(config_ini_path_used):
        return 'static', []
        
    config = configparser.ConfigParser(allow_no_value=True)
    
    # Try to read with different encodings
    encodings = ['utf-8', 'latin-1', 'cp1252']
    lines = []
    for encoding in encodings:
        try:
            with open(config_ini_path_used, 'r', encoding=encoding) as f:
                lines = f.readlines()
            break
        except UnicodeDecodeError:
            continue
    
    if not lines:
        # Fallback to default if all encodings fail
        return 'static', []
    filtered_lines, in_titles, current_section = [], False, None
    for line in lines:
        stripped = line.strip()
        section_name = stripped
        if stripped.startswith('[') and stripped.endswith(']'):
            if section_name != current_section:
                current_section = section_name
                filtered_lines.append(line)
        elif stripped.startswith('titles_to_remove'):
            if stripped.endswith('['):
                in_titles = True
                filtered_lines.append('titles_to_remove = []\n')
            else:
                filtered_lines.append(line)
        elif not in_titles:
            filtered_lines.append(line)
    config.read_string(''.join(filtered_lines))
    light_mode = config.get('Settings', 'light_mode', fallback='static')
    excel_format = config.get('Settings', 'excel_format', fallback='standard')
    sender_indicator = config.get('Settings', 'sender_indicator', fallback='Contato Recebido')
    titles_lines, in_titles = [], False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('titles_to_remove'):
            if stripped.endswith('['):
                in_titles = True
                continue
            else:
                titles_lines.append(stripped.split('=',1)[1].strip())
        elif in_titles:
            if stripped == ']':
                in_titles = False
            else:
                clean_line = stripped.rstrip(',').strip().strip('"').strip("'")
                if clean_line:
                    titles_lines.append(clean_line)
    titles_str = '[' + ','.join(f'"{line}"' for line in titles_lines) + ']'
    try: titles = json.loads(titles_str)
    except Exception:
        try: titles = ast.literal_eval(titles_str)
        except Exception: titles = []
    return light_mode, excel_format, sender_indicator, titles

LIGHT_MODE_DEFAULT, EXCEL_FORMAT_DEFAULT, SENDER_INDICATOR_DEFAULT, TITLES_TO_REMOVE = read_config_ini()

# Logging configuration with fallback locations
def setup_logging():
    log_locations = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_debug.log'),  # Current directory
        os.path.join(os.path.expanduser("~"), 'Documents', 'VCF_Processor_logs', 'app_debug.log'),  # User Documents
        os.path.join(os.environ.get('PROGRAMDATA', 'C:\\ProgramData'), 'VCF_Processor', 'app_debug.log'),  # ProgramData
        os.path.join(os.path.expanduser("~"), 'AppData', 'Local', 'VCF_Processor', 'app_debug.log'),  # Local AppData
    ]
    
    handlers = [logging.StreamHandler(sys.stdout)]  # Always include console output
    
    for log_path in log_locations:
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            
            # Test if we can write to the location
            test_file = os.path.join(os.path.dirname(log_path), 'test_write.tmp')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            
            # Add file handler
            handlers.append(logging.FileHandler(log_path, encoding='utf-8'))
            print(f"[OK] Logging to: {log_path}")
            break
        except (PermissionError, OSError) as e:
            print(f"[WARNING] Cannot write to {log_path}: {e}")
            continue
    
    if len(handlers) == 1:  # Only console handler
        print("[WARNING] Warning: Logging to console only due to permission issues")
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=handlers)
    return logging.getLogger(__name__)

logger = setup_logging()

def on_drag(e): pass

def on_drop(e):
    files = e['dataTransfer']['files']
    dropped_paths = []
    for file in files:
        path = file['pywebviewFullPath']
        if os.path.isfile(path) and path.lower().endswith(('.vcf',)):
            dropped_paths.append(path)
        elif os.path.isdir(path):
            dropped_paths.append(path)
    if dropped_paths:
        js_code = f"""
        var path = {json.dumps(dropped_paths[0])};
        var inputElement = document.getElementById('vcf-path');
        if (inputElement) {{
            inputElement.value = path;
            var event = new Event('droppedFileReady');
            inputElement.dispatchEvent(event);
        }} else {{
            console.error("Input element with id 'vcf-path' not found.");
        }}
        """
        window.evaluate_js(js_code)
    else:
        js_code = """
        var inputElement = document.getElementById('vcf-path');
        if (inputElement) {
            inputElement.value = '';
        }
        console.warn("No valid .vcf files or directories containing them were dropped.");
        """
        window.evaluate_js(js_code)

def bind(window):
    window.dom.document.events.dragenter += DOMEventHandler(on_drag, True, True)
    window.dom.document.events.dragstart += DOMEventHandler(on_drag, True, True)
    window.dom.document.events.dragover += DOMEventHandler(on_drag, True, True, debounce=500)
    window.dom.document.events.drop += DOMEventHandler(on_drop, True, True)
    window.events.closed += on_window_closed

def on_window_closed():
    logger.info("Webview window closed. Shutting down Flask server.")
    try:
        import requests
        requests.post('http://127.0.0.1:5000/shutdown')
    except Exception as e:
        logger.error(f"Error sending shutdown request to Flask: {e}")
    finally:
        os._exit(0)

class Api:
    def __init__(self):
        self._window = None
        self.initial_width = 800
        self.initial_height = 750
        self.processor = None  # Reference to current VCFProcessor instance

    def set_window(self, window):
        self._window = window

    def set_processor(self, processor):
        """Set the current VCFProcessor instance"""
        self.processor = processor

    def select_file(self):
        file_paths = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True, file_types=('VCF Files (*.vcf)',))
        return file_paths if file_paths else []

    def close_window(self):
        self._window.destroy()

    def minimize_window(self):
        self._window.minimize()

    def set_window_position(self, x, y):
        self._window.move(x, y)

    def open_file_path(self, path):
        """Open a file with the default system application"""
        if not path:
            logger.error(f"Error: Empty file path provided")
            return
            
        # Convert relative path to absolute path
        if path.startswith('~/Documents/'):
            # Extract the filename from the relative path
            filename = path.replace('~/Documents/', '')
            # Get the absolute Documents path
            docs_path = os.path.expanduser("~/Documents")
            path = os.path.join(docs_path, filename)
        
        if not os.path.exists(path):
            logger.error(f"Error: Cannot open file, path does not exist: {path}")
            return
        logger.info(f"Attempting to open file: {path}")
        try:
            if sys.platform == "win32": 
                os.startfile(os.path.realpath(path))
            elif sys.platform == "darwin": 
                subprocess.run(["open", path])
            else: 
                subprocess.run(["xdg-open", path])
        except Exception as e: 
            logger.error(f"Failed to open file: {e}")

    # <<< NOVO >>> Funções para obter e definir o tamanho absoluto da janela para o JS.
    def get_window_size(self):
        if self._window:
            return {'width': self._window.width, 'height': self._window.height}
        return None

    def set_window_size(self, width, height):
        if self._window:
            self._window.resize(int(width), int(height))

    # <<< NOVO >>> Função de redimensionamento instantâneo para atalhos de teclado.
    def resize_window(self, width_delta, height_delta):
        if self._window:
            new_width = self._window.width + width_delta
            new_height = self._window.height + height_delta
            self._window.resize(new_width, new_height)

    def reset_window_size(self):
        if self._window:
            self._window.resize(self.initial_width, self.initial_height)

    def open_log_file_with_notepad(self):
        # Get the current processor from session_data
        current_log_path = LOG_PATH  # Default fallback
        
        with session_lock:
            processor = session_data.get('processor')
            if processor and hasattr(processor, 'log_file_path'):
                current_log_path = processor.log_file_path
        
        # Ensure the log file exists before trying to open it
        if not os.path.exists(current_log_path):
            logger.warning(f"Log file does not exist: {current_log_path}")
            # Try to create an empty log file
            try:
                os.makedirs(os.path.dirname(current_log_path), exist_ok=True)
                with open(current_log_path, 'w', encoding='utf-8') as f:
                    pass  # Create empty file
                logger.info(f"Created empty log file: {current_log_path}")
            except Exception as e:
                logger.error(f"Failed to create log file {current_log_path}: {e}")
                return
        
        try:
            subprocess.run(["notepad.exe", current_log_path], check=True)
            logger.info(f"Opened log file with notepad: {current_log_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to open log file with notepad: {e}")
        except Exception as e:
            logger.error(f"Unexpected error opening log file: {e}")

    def check_for_updates(self):
        try:
            from updater import check_for_updates
            return check_for_updates()
        except ImportError:
            return {"update_available": False, "error": "Updater not available"}
        
    def get_app_version(self):
        """Returns the hardcoded app version to the UI."""
        return APP_VERSION

api = Api()

# --- Centralized Processing Logic ---
def process_vcf_file_logic(vcf_path, sender_name=None, excel_format=None):
    if not vcf_path or not os.path.isfile(vcf_path):
        return jsonify({"error": "Caminho do arquivo VCF é inválido ou não encontrado."}), 400
    try:
        global TITLES_TO_REMOVE
        _, EXCEL_FORMAT_DEFAULT, SENDER_INDICATOR_DEFAULT, TITLES_TO_REMOVE = read_config_ini()
        
        # Use excel format from request if provided, otherwise use config default
        actual_excel_format = excel_format if excel_format else EXCEL_FORMAT_DEFAULT
        
        processor = VCFProcessor(log_file_path=LOG_PATH, titles_to_remove=TITLES_TO_REMOVE, excel_format=actual_excel_format, sender_indicator=SENDER_INDICATOR_DEFAULT)
        
        # Update processor with sender name from GUI if provided
        if sender_name:
            processor.update_sender_name(sender_name)
        
        unique_contacts, duplicate_contacts = processor.get_unique_and_duplicate_contacts(vcf_path)
        
        if not duplicate_contacts:
            logging.info("Nenhuma duplicata encontrada. Processando contatos únicos automaticamente.")
            abs_vcf_path = os.path.abspath(vcf_path)
            output_dir = os.path.dirname(abs_vcf_path)
            base_name = os.path.splitext(os.path.basename(abs_vcf_path))[0]
            output_file = processor.process_and_save(unique_contacts, output_dir, base_name)
            return jsonify({
                "message": "Processamento concluído. Nenhuma duplicata encontrada.",
                "output_file": output_file or "None", "duplicates": []
            })
        else:
            with session_lock:
                session_data['processor'] = processor
                session_data['vcf_path'] = vcf_path
                session_data['unique_contacts'] = unique_contacts
                session_data.pop('output_base_name', None)
            return jsonify({"duplicates": duplicate_contacts})
    except Exception as e:
        logging.error(f"Erro ao processar o arquivo VCF: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index_pt-br.html', window_title="Processador de VCF",
                           initial_vcf_path=initial_data_for_ui["vcf_path"],
                           initial_duplicates=json.dumps(initial_data_for_ui["duplicates"]))

@app.route('/save_light_mode', methods=['POST'])
def save_light_mode():
    data = request.json
    light_mode = data.get('lightMode') or data.get('light_mode') or data.get('lightMode')
    if light_mode:
        try:
            if not os.path.exists(config_ini_path): create_default_config(config_ini_path)
            with open(config_ini_path, 'r', encoding='utf-8') as f: lines = f.readlines()
            for i, line in enumerate(lines):
                if line.strip().startswith('light_mode'):
                    lines[i] = f'light_mode = {light_mode}\n'; break
            else:
                for i, line in enumerate(lines):
                    if line.strip() == '[Settings]':
                        lines.insert(i+1, f'light_mode = {light_mode}\n'); break
            with open(config_ini_path, 'w', encoding='utf-8') as f: f.writelines(lines)
        except Exception as e:
            logger.error(f"Error saving light mode: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'success'})

@app.route('/save_excel_format', methods=['POST'])
def save_excel_format():
    data = request.json
    excel_format = data.get('excelFormat') or data.get('excel_format')
    if excel_format:
        try:
            if not os.path.exists(config_ini_path): create_default_config(config_ini_path)
            with open(config_ini_path, 'r', encoding='utf-8') as f: lines = f.readlines()
            for i, line in enumerate(lines):
                if line.strip().startswith('excel_format'):
                    lines[i] = f'excel_format = {excel_format}\n'; break
            else:
                for i, line in enumerate(lines):
                    if line.strip() == '[Settings]':
                        lines.insert(i+1, f'excel_format = {excel_format}\n'); break
            with open(config_ini_path, 'w', encoding='utf-8') as f: f.writelines(lines)
        except Exception as e:
            logger.error(f"Error saving excel format: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'success'})

@app.route('/check_updates', methods=['GET'])
def check_updates_route():
    # Pass the current app version to the check function
    update_info = check_for_updates(APP_VERSION) # This will now work
    return jsonify(update_info)

# In app.py

@app.route('/download_update', methods=['POST'])
def download_update_route():
    data = request.get_json()
    download_url = data.get('download_url')
    update_type = data.get('update_type', 'exe')
    password = data.get('password', '')
    if not download_url:
        return jsonify({"success": False, "error": "Download URL not provided."}), 400

    # This function now just launches the waiter and returns.
    result = download_and_run_installer(download_url, update_type, password)
    
    # If the launcher was successfully started, we now terminate our own application.
    if result.get("success"):
        def shutdown_app():
            # Wait a very short moment to ensure the HTTP response is sent.
            time.sleep(1)
            # Use the same shutdown mechanism as the old GitHub version
            try:
                import requests
                requests.post('http://127.0.0.1:5000/shutdown', timeout=5)
            except Exception as e:
                logger.error(f"Error sending shutdown request to Flask: {e}")
            finally:
                # Ensure the main Python process exits
                os._exit(0)
        
        # Run the shutdown in a separate thread so the HTTP response can be sent.
        threading.Thread(target=shutdown_app).start()

    return jsonify(result)

@app.route('/get_titles', methods=['GET'])
def get_titles():
    global TITLES_TO_REMOVE
    _, EXCEL_FORMAT_DEFAULT, SENDER_INDICATOR_DEFAULT, TITLES_TO_REMOVE = read_config_ini()
    titles = TITLES_TO_REMOVE
    titles.sort(key=str.lower)
    return jsonify({"titles": titles})

@app.route('/save_titles', methods=['POST'])
def save_titles():
    data = request.get_json()
    new_titles = data.get('titles', [])
    new_titles.sort(key=str.lower)
    try:
        if not os.path.exists(config_ini_path): create_default_config(config_ini_path)
        with open(config_ini_path, 'r', encoding='utf-8') as f: lines = f.readlines()
        start_idx, end_idx = None, None
        for i, line in enumerate(lines):
            if line.strip().startswith('titles_to_remove'): start_idx = i; break
        if start_idx is not None:
            for j in range(start_idx + 1, len(lines)):
                if lines[j].strip() == ']': end_idx = j; break
        new_titles_lines = ['titles_to_remove = [\n'] + [f'    "{title}",\n' for title in new_titles] + [']\n']
        if start_idx is not None and end_idx is not None:
            lines = lines[:start_idx] + new_titles_lines + lines[end_idx+1:]
        else:
            lines.extend(new_titles_lines)
        with open(config_ini_path, 'w', encoding='utf-8') as f: f.writelines(lines)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_processed_numbers', methods=['GET'])
def get_processed_numbers():
    try:
        with open(LOG_PATH, 'r', encoding='utf-8') as f: lines = f.readlines()
        processed_numbers = [int(line.strip()) for line in lines if line.strip().isdigit()]
        return jsonify({"numbers": processed_numbers}), 200
    except FileNotFoundError: return jsonify({"error": "Log file not found."}), 404
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/add_processed_numbers', methods=['POST'])
def add_processed_numbers():
    data = request.get_json()
    if not data or 'numbers' not in data: return jsonify({"error": "No numbers provided."}), 400
    numbers_to_add = data['numbers']
    if not isinstance(numbers_to_add, list) or not all(isinstance(num, int) for num in numbers_to_add):
        return jsonify({"error": "Invalid input format. Expected a list of integers."}), 400
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            for number in numbers_to_add: f.write(f"{number}\n")
        return jsonify({"status": "success"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/remove_processed_numbers', methods=['POST'])
def remove_processed_numbers():
    data = request.get_json()
    if not data or 'numbers' not in data: return jsonify({"error": "No numbers provided."}), 400
    numbers_to_remove = data['numbers']
    if not isinstance(numbers_to_remove, list) or not all(isinstance(num, int) for num in numbers_to_remove):
        return jsonify({"error": "Invalid input format. Expected a list of integers."}), 400
    try:
        with open(LOG_PATH, 'r', encoding='utf-8') as f: lines = f.readlines()
        with open(LOG_PATH, 'w', encoding='utf-8') as f:
            for line in lines:
                if line.strip() not in map(str, numbers_to_remove): f.write(line)
        return jsonify({"status": "success"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/get_session_data', methods=['GET'])
def get_session_data():
    with session_lock:
        if not session_data: return jsonify({"error": "No session data available."}), 404
        return jsonify(session_data), 200

@app.route('/start_vcf_processing', methods=['POST'])
def start_vcf_processing():
    data = request.get_json()
    vcf_path = data.get('vcf_path')
    sender_name = data.get('senderName', 'Contato Recebido')
    excel_format = data.get('excelFormat')
    return process_vcf_file_logic(vcf_path, sender_name, excel_format)

@app.route('/process_dropped_vcf', methods=['POST'])
def process_dropped_vcf():
    logger.info("=== PROCESS DROPPED VCF REQUEST ===")
    try:
        data = request.get_json()
        logger.info(f"Request data: {data}")
        vcf_path = data.get('vcf_path')
        sender_name = data.get('senderName', 'Contato Recebido')  # Get sender name from GUI
        excel_format = data.get('excelFormat')  # Get excel format from GUI
        logger.info(f"VCF path: {vcf_path}")
        logger.info(f"Sender name: {sender_name}")
        logger.info(f"Excel format: {excel_format}")
        result = process_vcf_file_logic(vcf_path, sender_name, excel_format)
        logger.info(f"Process result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in process_dropped_vcf: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/start_batch_processing', methods=['POST'])
def start_batch_processing():
    try:
        data = request.get_json()
        vcf_paths = data.get('vcf_paths', [])
        sender_name = data.get('senderName', 'Contato Recebido')
        excel_format = data.get('excelFormat')

        if not vcf_paths:
            return jsonify({"error": "Nenhum arquivo VCF fornecido."}), 400

        # Concatenate all VCF files into one temp file
        import tempfile
        combined_content = ""
        for vcf_path in vcf_paths:
            if os.path.isfile(vcf_path):
                with open(vcf_path, 'r', encoding='utf-8', errors='replace') as f:
                    combined_content += f.read() + "\n"

        if not combined_content.strip():
            return jsonify({"error": "Nenhum conteúdo VCF válido encontrado."}), 400

        tmp = tempfile.NamedTemporaryFile(suffix='.vcf', delete=False, mode='w', encoding='utf-8')
        tmp.write(combined_content)
        tmp.close()

        # Use same logic as single file, output to same dir as first file
        result = process_vcf_file_logic(tmp.name, sender_name, excel_format)

        # Fix output path to point to first file's directory
        try:
            result_data = result.get_json()
            if result_data.get('output_file') and result_data['output_file'] != 'None':
                output_dir = os.path.dirname(os.path.abspath(vcf_paths[0]))
                base_name = "Batch_Processados"
                global TITLES_TO_REMOVE
                _, EXCEL_FORMAT_DEFAULT, SENDER_INDICATOR_DEFAULT, TITLES_TO_REMOVE = read_config_ini()
                actual_excel_format = excel_format if excel_format else EXCEL_FORMAT_DEFAULT
                processor = VCFProcessor(log_file_path=LOG_PATH, titles_to_remove=TITLES_TO_REMOVE, excel_format=actual_excel_format, sender_indicator=SENDER_INDICATOR_DEFAULT)
                if sender_name:
                    processor.update_sender_name(sender_name)
                # Re-read session unique contacts and save to correct location
                with session_lock:
                    unique_contacts = session_data.get('unique_contacts', [])
                if unique_contacts:
                    output_file = processor.process_and_save(unique_contacts, output_dir, base_name)
                    result_data['output_file'] = output_file or 'None'
                    return jsonify(result_data)
        except Exception:
            pass

        # Also store batch paths in session for reprocess_selected
        with session_lock:
            session_data['batch_vcf_paths'] = vcf_paths
            session_data.pop('vcf_path', None)

        os.unlink(tmp.name)
        return result

    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_light_mode', methods=['GET'])
def get_light_mode():
    try:
        global LIGHT_MODE_DEFAULT
        LIGHT_MODE_DEFAULT, _, _, _ = read_config_ini()
        return jsonify({"lightMode": LIGHT_MODE_DEFAULT})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_excel_format', methods=['GET'])
def get_excel_format():
    try:
        _, EXCEL_FORMAT_DEFAULT, _, _ = read_config_ini()
        return jsonify({"excelFormat": EXCEL_FORMAT_DEFAULT})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_sender_indicator', methods=['GET'])
def get_sender_indicator():
    try:
        global TITLES_TO_REMOVE
        _, EXCEL_FORMAT_DEFAULT, SENDER_INDICATOR_DEFAULT, TITLES_TO_REMOVE = read_config_ini()
        return jsonify({"senderIndicator": SENDER_INDICATOR_DEFAULT})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/save_sender_indicator', methods=['POST'])
def save_sender_indicator():
    try:
        data = request.get_json()
        sender_indicator = data.get('senderIndicator', 'Contato Recebido')
        
        # Don't save to config - just return success for current session
        logging.info(f"Using sender indicator for current session: {sender_indicator}")
        return jsonify({"status": "success", "senderIndicator": sender_indicator})
        
    except Exception as e:
        logging.error(f"Error handling sender indicator: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/start_text_processing', methods=['POST'])
def start_text_processing():
    text_content = request.get_json().get('text_content')
    if not text_content or not text_content.strip():
        return jsonify({"error": "Nenhum texto fornecido."}), 400
    try:
        global TITLES_TO_REMOVE
        _, EXCEL_FORMAT_DEFAULT, SENDER_INDICATOR_DEFAULT, TITLES_TO_REMOVE = read_config_ini()
        processor = VCFProcessor(log_file_path=LOG_PATH, titles_to_remove=TITLES_TO_REMOVE, excel_format=EXCEL_FORMAT_DEFAULT, sender_indicator=SENDER_INDICATOR_DEFAULT)
        unique_contacts, duplicate_contacts = processor.get_unique_and_duplicate_contacts_from_text(text_content)
        
        if not duplicate_contacts:
            logging.info("Nenhuma duplicata encontrada no texto. Processando automaticamente.")
            output_dir = os.path.expanduser("~/Documents")
            base_name = "Contatos_Colados"
            output_file = processor.process_and_save(unique_contacts, output_dir, base_name)
            return jsonify({
                "message": "Processamento de texto concluído.",
                "output_file": output_file or "None", "duplicates": []
            })
        else:
            with session_lock:
                session_data['processor'] = processor
                session_data['unique_contacts'] = unique_contacts
                session_data['output_base_name'] = "Contatos_Colados"
                session_data.pop('vcf_path', None)
            return jsonify({"duplicates": duplicate_contacts})
    except Exception as e:
        logging.error(f"Erro ao processar texto: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/reprocess_selected', methods=['POST'])
def reprocess_selected():
    data = request.get_json()
    selected_to_reprocess = data.get('selected_to_reprocess', [])
    sender_name = data.get('senderName', 'Contato Recebido')  # Get sender name from GUI
    logging.info(f"Reprocessing {len(selected_to_reprocess)} selected contacts")
    with session_lock:
        processor = session_data.get('processor')
        vcf_path = session_data.get('vcf_path')
        batch_vcf_paths = session_data.get('batch_vcf_paths')
        output_base_name = session_data.get('output_base_name')
        unique_contacts = session_data.get('unique_contacts', [])
    if not processor:
        return jsonify({"error": "Session expired. Please start over."}), 400
    try:
        # Update processor with sender name from GUI
        processor.update_sender_name(sender_name)
        
        numbers_to_remove = [contact['cleaned_number'] for contact in selected_to_reprocess]
        if numbers_to_remove:
            processor.remove_from_log(numbers_to_remove)
        contacts_to_process = unique_contacts + selected_to_reprocess
        
        if vcf_path:
            abs_path = os.path.abspath(vcf_path)
            output_dir = os.path.dirname(abs_path)
            base_name = os.path.splitext(os.path.basename(abs_path))[0]
        elif batch_vcf_paths:
            output_dir = os.path.dirname(os.path.abspath(batch_vcf_paths[0]))
            base_name = "Batch_Processados"
        else:
            output_dir = os.path.expanduser("~/Documents")
            base_name = output_base_name
        
        output_file = processor.process_and_save(contacts_to_process, output_dir, base_name)
        
        with session_lock:
            session_data.clear()
        return jsonify({
            "message": "Processing complete!" if output_file else "Processing failed!",
            "output_file": output_file or "None"
        })
    except Exception as e:
        logging.error(f"Error during reprocessing: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/shutdown', methods=['POST'])
def shutdown():
    # Use Flask's built-in server shutdown function
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        # Try alternative shutdown methods for Flask's built-in server
        try:
            # Create a minimal server error to trigger shutdown
            from flask import Response
            raise RuntimeError('Server shutdown initiated')
        except:
            # If that doesn't work, use os._exit as fallback
            def shutdown_app():
                time.sleep(1)
                os._exit(0)
            threading.Thread(target=shutdown_app).start()
            return jsonify({"success": True, "message": "Shutdown initiated"})
    else:
        func()
    return 'Server shutting down...'

# --- Main Execution Block ---
def check_single_instance():
    """Check if another instance is already running"""
    import psutil
    current_pid = os.getpid()
    current_process = psutil.Process(current_pid)
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['pid'] != current_pid and proc.info['name'] == 'VCF_Processor_Fast.exe':
                return False  # Another instance found
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return True  # No other instances found

if __name__ == '__main__':
    # Check for single instance
    if not check_single_instance():
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "Another instance of VCF Processor is already running!\n\nPlease close the existing instance first.", "VCF Processor - Already Running", 0x10 | 0x0)
        sys.exit(1)
    
    initialize_log_from_xlsx()
    initial_file_path = None
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) and not sys.argv[1].startswith('-'):
         initial_file_path = sys.argv[1]

    headless_mode_successful = False
    if initial_file_path:
        print("--- Running in Headless Mode ---")
        try:
            processor = VCFProcessor(log_file_path=LOG_PATH, titles_to_remove=TITLES_TO_REMOVE, excel_format=EXCEL_FORMAT_DEFAULT, sender_indicator=SENDER_INDICATOR_DEFAULT)
            unique_contacts, duplicate_contacts = processor.get_unique_and_duplicate_contacts(initial_file_path)
            if not duplicate_contacts:
                print("No duplicates found. Processing unique contacts automatically.")
                abs_input_path = os.path.abspath(initial_file_path)
                output_dir = os.path.dirname(abs_input_path)
                base_name = os.path.splitext(os.path.basename(abs_input_path))[0]
                output_file = processor.process_and_save(unique_contacts, output_dir, base_name)
                logging.info(f"Headless processing complete. Output: {output_file or 'None'}")
                headless_mode_successful = True
            else:
                print(f"Found {len(duplicate_contacts)} duplicates. Preparing data for GUI...")
                initial_data_for_ui['vcf_path'] = initial_file_path
                initial_data_for_ui['duplicates'] = duplicate_contacts
                with session_lock:
                    session_data['processor'] = processor
                    session_data['vcf_path'] = initial_file_path
                    session_data['unique_contacts'] = unique_contacts
        except Exception as e:
             logging.error(f"An error occurred during initial headless processing: {e}", exc_info=True)
             initial_data_for_ui['vcf_path'] = initial_file_path
    
    if not headless_mode_successful:
        print("Launching GUI mode...")
        api_instance = Api()
        window = webview.create_window(
            'VCF Processor',
            app,
            js_api=api_instance,
            width=api_instance.initial_width,
            height=api_instance.initial_height,
            frameless=True,
            resizable=True,
            min_size=(600, 500)
        )
        api_instance.set_window(window)
        
        def run_flask():
            logger.info("Starting Flask server on port 5000...")
            
            # Check for single instance before starting
            if not check_single_instance():
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, "Another instance of VCF Processor is already running!\n\nPlease close the existing instance first.", "VCF Processor - Already Running", 0x10 | 0x0)
                sys.exit(1)
            
            app.run(port=5000, debug=False, use_reloader=False, threaded=True)

        flask_thread = threading.Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        
        webview.start(bind, window, debug=False, http_server=False)
    
    sys.exit(0)
