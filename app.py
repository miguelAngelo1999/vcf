import os
import sys
import json
import webview
import threading
import importlib
from flask import Flask, render_template, request, jsonify
app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = False
import time

# This import is still good practice to encourage the correct backend
if sys.platform == 'win32':
    import webview.platforms.edgechromium


# Version for update checking
APP_VERSION = "2.6.1"

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

def initialize_log_from_xlsx():
    """Initialize log from NAO_APAGAR.xlsx in Documents folder on first run"""
    if os.path.exists(LOG_FILENAME) and os.path.getsize(LOG_FILENAME) > 0:
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
        
        with open(LOG_FILENAME, 'w', encoding='utf-8') as f:
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
    with open(config_ini_path_used, encoding='utf-8') as f: lines = f.readlines()
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
    return light_mode, titles

LIGHT_MODE_DEFAULT, TITLES_TO_REMOVE = read_config_ini()

app_log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_debug.log')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(app_log_file, encoding='utf-8'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

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

    def set_window(self, window):
        self._window = window

    def select_file(self):
        file_paths = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=('VCF Files (*.vcf)',))
        return file_paths[0] if file_paths else None

    def close_window(self):
        self._window.destroy()

    def minimize_window(self):
        self._window.minimize()

    def set_window_position(self, x, y):
        self._window.move(x, y)

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
        subprocess.run(["notepad.exe", LOG_FILENAME], check=True)

    def open_file_path(self, path):
        if not os.path.exists(path):
            logger.error(f"Error: Cannot open file, path does not exist: {path}")
            return
        logger.info(f"Attempting to open file: {path}")
        try:
            if sys.platform == "win32": os.startfile(os.path.realpath(path))
            elif sys.platform == "darwin": subprocess.run(["open", path])
            else: subprocess.run(["xdg-open", path])
        except Exception as e: logger.error(f"Failed to open file: {e}")

    def check_for_updates(self):
        try:
            from updater import check_for_updates
            return check_for_updates()
        except ImportError:
            return {"update_available": False, "error": "Updater not available"}

api = Api()

# --- Centralized Processing Logic ---
def process_vcf_file_logic(vcf_path):
    if not vcf_path or not os.path.isfile(vcf_path):
        return jsonify({"error": "Caminho do arquivo VCF é inválido ou não encontrado."}), 400
    try:
        global TITLES_TO_REMOVE
        _, TITLES_TO_REMOVE = read_config_ini()
        processor = VCFProcessor(log_file_path=LOG_FILENAME, titles_to_remove=TITLES_TO_REMOVE)
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

@app.route('/get_light_mode', methods=['GET'])
def get_light_mode():
    light_mode, _ = read_config_ini()
    return jsonify({'lightMode': light_mode})

@app.route('/check_updates', methods=['GET'])
def check_updates():
    try:
        from updater import check_for_updates
        return jsonify(check_for_updates())
    except Exception as e:
        return jsonify({"update_available": False, "error": str(e)})

@app.route('/get_titles', methods=['GET'])
def get_titles():
    global TITLES_TO_REMOVE
    _, TITLES_TO_REMOVE = read_config_ini()
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
        with open(LOG_FILENAME, 'r', encoding='utf-8') as f: lines = f.readlines()
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
        with open(LOG_FILENAME, 'a', encoding='utf-8') as f:
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
        with open(LOG_FILENAME, 'r', encoding='utf-8') as f: lines = f.readlines()
        with open(LOG_FILENAME, 'w', encoding='utf-8') as f:
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
    vcf_path = request.get_json().get('vcf_path')
    return process_vcf_file_logic(vcf_path)

@app.route('/process_dropped_vcf', methods=['POST'])
def process_dropped_vcf():
    vcf_path = request.get_json().get('vcf_path')
    return process_vcf_file_logic(vcf_path)

@app.route('/start_text_processing', methods=['POST'])
def start_text_processing():
    text_content = request.get_json().get('text_content')
    if not text_content or not text_content.strip():
        return jsonify({"error": "Nenhum texto fornecido."}), 400
    try:
        global TITLES_TO_REMOVE
        _, TITLES_TO_REMOVE = read_config_ini()
        processor = VCFProcessor(log_file_path=LOG_FILENAME, titles_to_remove=TITLES_TO_REMOVE)
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
    logging.info(f"Reprocessing {len(selected_to_reprocess)} selected contacts")
    with session_lock:
        processor = session_data.get('processor')
        vcf_path = session_data.get('vcf_path')
        output_base_name = session_data.get('output_base_name')
        unique_contacts = session_data.get('unique_contacts', [])
    if not processor:
        return jsonify({"error": "Session expired. Please start over."}), 400
    try:
        numbers_to_remove = [contact['cleaned_number'] for contact in selected_to_reprocess]
        if numbers_to_remove:
            processor.remove_from_log(numbers_to_remove)
        contacts_to_process = unique_contacts + selected_to_reprocess
        
        if vcf_path:
            abs_path = os.path.abspath(vcf_path)
            output_dir = os.path.dirname(abs_path)
            base_name = os.path.splitext(os.path.basename(abs_path))[0]
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
    shutdown_func = request.environ.get('werkzeug.server.shutdown')
    if shutdown_func is None: raise RuntimeError('Not running with the Werkzeug Server')
    shutdown_func()
    return 'Server shutting down...'

# --- Main Execution Block ---
if __name__ == '__main__':
    initialize_log_from_xlsx()
    initial_file_path = None
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) and not sys.argv[1].startswith('-'):
         initial_file_path = sys.argv[1]

    headless_mode_successful = False
    if initial_file_path:
        print("--- Running in Headless Mode ---")
        try:
            processor = VCFProcessor(log_file_path=LOG_FILENAME, titles_to_remove=TITLES_TO_REMOVE)
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
            app.run(port=5000, debug=False, use_reloader=False, threaded=True)

        flask_thread = threading.Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        
        webview.start(bind, window, debug=False, http_server=False)
    
    sys.exit(0)