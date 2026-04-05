import io
import os
import sys
import re
import pandas as pd
from unidecode import unidecode
import configparser
import json
import ast
import logging
import tempfile

# Configure logging for PyInstaller builds
if getattr(sys, 'frozen', False):
    log_dir = os.path.dirname(sys.executable)
else:
    log_dir = os.path.dirname(os.path.abspath(__file__))

log_file = os.path.join(log_dir, 'vcf_debug.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def read_titles_from_config_ini():
    if getattr(sys, 'frozen', False):
        config_ini_path = os.path.join(sys._MEIPASS, 'config.ini')
    else:
        config_ini_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    
    try:
        with open(config_ini_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        titles = []
        in_titles = False
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('titles_to_remove'):
                in_titles = True
                continue
            elif in_titles:
                if stripped == ']':
                    break
                elif stripped and not stripped.startswith('#'):
                    title = stripped.strip('"').strip("'").rstrip(',')
                    if title:
                        titles.append(title)
        
        return titles
    except Exception as e:
        logging.error(f"Error reading config.ini: {e}")
        return []

class VCFProcessor:
    def __init__(self, log_file_path, titles_to_remove=None, excel_format='standard', sender_indicator='Contato Recebido'):
        # Ensure we have a writable log file path
        self.log_file_path = self._ensure_writable_log_path(log_file_path)
        logging.info(f"VCFProcessor initialized with log path: {self.log_file_path}")
        
        self.excel_format = excel_format
        self.sender_indicator = sender_indicator  # This will be updated from GUI
        self.sender_name = sender_indicator  # Default to config value, can be updated
        if titles_to_remove is None:
            try:
                titles_to_remove = read_titles_from_config_ini()
            except Exception as e:
                logging.warning(f"Could not read titles from config: {e}")
                titles_to_remove = []
        if titles_to_remove:
            self.title_pattern = r'\b(' + '|'.join(re.escape(title) for title in titles_to_remove) + r')\.?\b'
            self.title_regex = re.compile(self.title_pattern, re.IGNORECASE)
        else:
            self.title_regex = None
        self.processed_numbers_log = self._read_log()

    def _ensure_writable_log_path(self, original_path):
        """Ensure we have a writable log file path with fallbacks"""
        logging.info(f"Testing log path: {original_path}")
        
        log_locations = [
            original_path,  # Original path
            os.path.join(os.path.expanduser("~"), 'Documents', 'VCF_Processor_logs', 'NAO_APAGAR.log'),  # User Documents
            os.path.join(os.environ.get('PROGRAMDATA', 'C:\\ProgramData'), 'VCF_Processor', 'NAO_APAGAR.log'),  # ProgramData
            os.path.join(os.path.expanduser("~"), 'AppData', 'Local', 'VCF_Processor', 'NAO_APAGAR.log'),  # Local AppData
            os.path.join(tempfile.gettempdir(), 'VCF_Processor_NAO_APAGAR.log'),  # Temp directory
        ]
        
        for log_path in log_locations:
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                
                # Test if we can write to the location by actually writing to the log file
                test_content = "test_write"
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(test_content + "\n")
                
                # Remove the test line
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                with open(log_path, 'w', encoding='utf-8') as f:
                    f.writelines([line for line in lines if test_content not in line])
                
                logging.info(f"[OK] Log path is writable: {log_path}")
                return log_path
            except (PermissionError, OSError) as e:
                logging.warning(f"[WARNING] Cannot write to {log_path}: {e}")
                continue
        
        # Last resort - use temp directory with timestamp
        import time
        temp_log = os.path.join(tempfile.gettempdir(), f'VCF_Processor_{int(time.time())}.log')
        logging.warning(f"Using timestamped temp log file: {temp_log}")
        return temp_log

    def _copy_from_locked_file(self, locked_path, new_path):
        """Copy content from a locked file to a new location"""
        try:
            # Try to read the locked file (read-only access might work)
            with open(locked_path, 'r', encoding='utf-8') as source:
                content = source.read()
            
            # Write to the new location
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            with open(new_path, 'w', encoding='utf-8') as destination:
                destination.write(content)
            
            logging.info(f"[OK] Successfully copied {len(content)} characters from {locked_path} to {new_path}")
            return True
        except (PermissionError, OSError) as e:
            logging.error(f"[ERROR] Failed to copy from locked file {locked_path}: {e}")
            return False
        except Exception as e:
            logging.error(f"[ERROR] Unexpected error copying from {locked_path}: {e}")
            return False

    def _is_file_locked(self, file_path):
        """Check if a file is locked by trying to open it for writing"""
        try:
            # Try to open the file for writing (this will fail if locked)
            with open(file_path, 'a', encoding='utf-8') as f:
                pass
            return False  # If we can open it, it's not locked
        except (PermissionError, OSError):
            return True  # File is locked
        except Exception:
            return False  # Other error, assume not locked

    def _get_file_write_time(self, file_path):
        """Get the last write time of a file"""
        try:
            return os.path.getmtime(file_path)
        except (OSError, FileNotFoundError):
            return 0

    def _merge_log_files(self, old_path, new_path):
        """Merge log files intelligently based on write times and content"""
        try:
            old_time = self._get_file_write_time(old_path)
            new_time = self._get_file_write_time(new_path)
            
            # Read both files
            old_content = set()
            new_content = set()
            
            if os.path.exists(old_path):
                try:
                    with open(old_path, 'r', encoding='utf-8') as f:
                        old_content = set(line.strip() for line in f if line.strip())
                except (PermissionError, OSError) as e:
                    logging.warning(f"Could not read old log file {old_path}: {e}")
            
            if os.path.exists(new_path):
                try:
                    with open(new_path, 'r', encoding='utf-8') as f:
                        new_content = set(line.strip() for line in f if line.strip())
                except (PermissionError, OSError) as e:
                    logging.warning(f"Could not read new log file {new_path}: {e}")
            
            # Merge content (union of both sets)
            merged_content = old_content.union(new_content)
            
            # Write merged content to new location
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            with open(new_path, 'w', encoding='utf-8') as f:
                for item in sorted(merged_content):  # Sort for consistent ordering
                    f.write(f"{item}\n")
            
            logging.info(f"[OK] Merged log files: {len(old_content)} from old, {len(new_content)} from new, {len(merged_content)} total")
            logging.info(f"File times - Old: {old_time}, New: {new_time}")
            
            return True
            
        except Exception as e:
            logging.error(f"[ERROR] Error merging log files: {e}")
            return False

    def _read_vcf(self, vcf_file_path):
        try:
            if not os.path.isabs(vcf_file_path):
                vcf_file_path = os.path.abspath(vcf_file_path)
            
            if not os.path.exists(vcf_file_path):
                logging.error(f"VCF file not found: {vcf_file_path}")
                return None
            
            file_size = os.path.getsize(vcf_file_path)
            logging.info(f"Reading VCF file: {vcf_file_path} (Size: {file_size} bytes)")
            
            encodings = ['utf-8', 'utf-8-sig', 'iso-8859-1', 'cp1252', 'latin1']
            
            for encoding in encodings:
                try:
                    with open(vcf_file_path, 'r', encoding=encoding, errors='replace') as f:
                        content = f.read()
                    
                    if 'BEGIN:VCARD' in content and 'END:VCARD' in content:
                        logging.info(f"VCF file read successfully with {encoding} encoding. Content length: {len(content)}")
                        return content
                    else:
                        logging.warning(f"Invalid VCF content with {encoding} encoding")
                        continue
                        
                except UnicodeDecodeError as e:
                    logging.warning(f"Failed to read with {encoding}: {e}")
                    continue
                except Exception as e:
                    logging.error(f"Error reading with {encoding}: {e}")
                    continue
            
            try:
                with open(vcf_file_path, 'rb') as f:
                    raw_content = f.read()
                content = raw_content.decode('utf-8', errors='replace')
                if 'BEGIN:VCARD' in content and 'END:VCARD' in content:
                    logging.info("VCF file read in binary mode with UTF-8 fallback")
                    return content
            except Exception as e:
                logging.error(f"Binary mode reading failed: {e}")
            
            logging.error("Failed to read VCF file with any encoding")
            return None
            
        except Exception as e:
            logging.error(f"Critical error reading VCF file: {e}", exc_info=True)
            return None

    def _extract_contact_data(self, vcf_content):
        contacts = []
        try:
            vcf_content = vcf_content.replace('\r\n', '\n').replace('\r', '\n')
            vcard_blocks = vcf_content.split("BEGIN:VCARD")
            
            logging.info(f"Processing {len(vcard_blocks) - 1} VCF blocks")
            
            for i, block in enumerate(vcard_blocks):
                if "END:VCARD" not in block:
                    continue
                    
                name, waid = None, None
                
                try:
                    fn_patterns = [r'FN:(.+?)(?:\n|\r|$)', r'N:([^;\n\r]+)', r'NICKNAME:(.+?)(?:\n|\r|$)']
                    for pattern in fn_patterns:
                        fn_match = re.search(pattern, block, re.MULTILINE)
                        if fn_match:
                            name = fn_match.group(1).strip()
                            break
                    
                    tel_patterns = [r'TEL[^:]*:([+]?\d[\d\s\-\(\)]+)', r'waid=([^:;\s]+)', r'PHONE[^:]*:([+]?\d[\d\s\-\(\)]+)', r'X-WA-BIZ-NAME[^:]*:.*?([+]?\d{10,15})']
                    for pattern in tel_patterns:
                        matches = re.findall(pattern, block, re.MULTILINE | re.IGNORECASE)
                        if matches:
                            for match in matches:
                                cleaned = re.sub(r'[^\d+]', '', match)
                                if len(cleaned) >= 10:
                                    waid = cleaned
                                    break
                            if waid:
                                break
                    
                    if name and waid:
                        contacts.append({'name': name, 'number': waid})
                        
                except Exception as e:
                    logging.error(f"Error processing VCF block {i}: {e}")
                    continue
            
            logging.info(f"Successfully extracted {len(contacts)} contacts from VCF")
            return contacts
            
        except Exception as e:
            logging.error(f"Critical error in VCF extraction: {e}", exc_info=True)
            return []

    # <<< ALTERADO >>> Este método agora processa ambos os formatos em uma única passagem.
    def _extract_contacts_from_text(self, text_content):
        contacts = []
        logging.info("Starting combined contact data extraction from raw text.")

        # Padrão para "[OK] Miguel +55..." com grupos nomeados para clareza
        pattern1 = r"\[OK\]\s*(?P<name1>.*?)\s*(?P<number1>\+\d+)\s*foi adicionado com sucesso\s*\[OK\]"
        
        # Padrão para "Name: Rogério..." com grupos nomeados
        pattern2 = r"Name:\s*(?P<name2>.*?)\s*Number \(1\):\s*(?P<number2>.*)"

        # Combina os dois padrões com um operador OR (|)
        combined_pattern = re.compile(f"({pattern1})|({pattern2})")

        # Usa finditer para obter objetos de correspondência para cada ocorrência no texto
        for match in combined_pattern.finditer(text_content):
            # Verifica qual grupo de padrões correspondeu
            if match.group('name1') is not None:
                # É o primeiro formato
                name = match.group('name1').replace('*', '').strip()
                number = match.group('number1').strip()
                if name and number:
                    contacts.append({'name': name, 'number': number})
            elif match.group('name2') is not None:
                # É o segundo formato
                name = match.group('name2').strip()
                raw_number = match.group('number2').strip()
                if name and raw_number:
                    # Limpa o número exatamente como o código antigo fazia
                    clean_number = '+' + ''.join(filter(str.isdigit, raw_number))
                    contacts.append({'name': name, 'number': clean_number})

        logging.info(f"Finished combined text extraction. Found {len(contacts)} potential contacts.")
        return contacts

    def _clean_name(self, name):
        if not name: return ""
        ascii_name = unidecode(name)
        cleaned_name = re.sub(r'[^a-zA-Z0-9\s]+', '', ascii_name)
        if self.title_regex: cleaned_name = self.title_regex.sub('', cleaned_name)
        cleaned_name = ' '.join(cleaned_name.split())
        words = cleaned_name.split()
        return words[0].title() if words else ""

    def _clean_phone_number(self, number):
        return re.sub(r'\D', '', number) if number else ""

    def _read_log(self):
        processed_numbers = set()
        if os.path.exists(self.log_file_path):
            try:
                with open(self.log_file_path, 'r', encoding='utf-8') as f:
                    processed_numbers.update(line.strip() for line in f)
                logging.info(f"Loaded {len(processed_numbers)} processed numbers from log.")
            except Exception as e:
                logging.error(f"Error reading log file '{self.log_file_path}': {e}")
        return processed_numbers

    def remove_from_log(self, numbers_to_remove):
        # Ensure we have a writable log path before operation
        old_path = self.log_file_path
        self.log_file_path = self._ensure_writable_log_path(self.log_file_path)
        
        if old_path != self.log_file_path:
            logging.info(f"Log path changed from {old_path} to {self.log_file_path} due to permission issues")
            
            # Always check write times and merge intelligently
            if os.path.exists(old_path) and os.path.exists(self.log_file_path):
                old_time = self._get_file_write_time(old_path)
                new_time = self._get_file_write_time(self.log_file_path)
                
                if old_time > new_time:
                    logging.info(f"Old log file is more recent ({old_time} > {new_time}), merging content")
                    self._merge_log_files(old_path, self.log_file_path)
                elif new_time > old_time:
                    logging.info(f"New log file is more recent ({new_time} > {old_time}), keeping new content")
                else:
                    logging.info(f"Both log files have same timestamp, merging to ensure no data loss")
                    self._merge_log_files(old_path, self.log_file_path)
            elif os.path.exists(old_path):
                # Only old file exists, copy it
                if self._is_file_locked(old_path):
                    logging.info(f"Old log file exists and is locked, attempting to copy content")
                    if self._copy_from_locked_file(old_path, self.log_file_path):
                        logging.info(f"Successfully copied content from {old_path} to {self.log_file_path}")
                    else:
                        logging.warning(f"Could not copy content from {old_path}, starting with empty log")
                else:
                    # File exists and isn't locked, just copy it
                    self._copy_from_locked_file(old_path, self.log_file_path)
            
            # Update processed_numbers_log to point to the new log file immediately
            self.processed_numbers_log = self._read_log()
        
        if not os.path.exists(self.log_file_path) or not numbers_to_remove: return
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f: lines = f.readlines()
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                for line in lines:
                    if line.strip() not in numbers_to_remove: f.write(line)
        except (PermissionError, OSError) as e:
            logging.error(f"Failed to write to log file {self.log_file_path}: {e}")
            # Try to get a new writable path and retry
            new_path = self._ensure_writable_log_path(self.log_file_path)
            if new_path != self.log_file_path:
                logging.info(f"Retrying with new log path: {new_path}")
                self.log_file_path = new_path
                
                # Apply intelligent merging logic for the retry
                if os.path.exists(old_path) and os.path.exists(self.log_file_path):
                    old_time = self._get_file_write_time(old_path)
                    new_time = self._get_file_write_time(self.log_file_path)
                    
                    if old_time >= new_time:
                        self._merge_log_files(old_path, self.log_file_path)
                
                # Update processed_numbers_log to point to the new log file
                self.processed_numbers_log = self._read_log()
                
                # Now filter the content
                try:
                    with open(self.log_file_path, 'r', encoding='utf-8') as f: lines = f.readlines()
                    with open(self.log_file_path, 'w', encoding='utf-8') as f:
                        for line in lines:
                            if line.strip() not in numbers_to_remove: f.write(line)
                except Exception as filter_error:
                    logging.error(f"Failed to filter log content: {filter_error}")
            else:
                logging.error("No writable log path available")
        
        logging.info(f"Removed {len(numbers_to_remove)} numbers from the log.")
        self.processed_numbers_log = self._read_log()

    def _resolve_duplicate_contacts(self, contacts_group):
        if not contacts_group:
            return None
        best_contact = contacts_group[0]
        if len(contacts_group) > 1:
            max_name_length = 0
            for contact in contacts_group:
                name_length = len(contact.get('original_name', ''))
                if name_length > max_name_length:
                    max_name_length = name_length
                    best_contact = contact
        return best_contact

    def _sort_contacts_by_log(self, extracted_contacts):
        contacts_by_number = {}
        for contact in extracted_contacts:
            cleaned_number = self._clean_phone_number(contact.get('number'))
            if cleaned_number:
                contact_data = {
                    'original_name': contact.get('name', ''),
                    'original_number': contact.get('number', ''),
                    'cleaned_number': cleaned_number,
                    'cleaned_name': self._clean_name(contact.get('name'))
                }
                if cleaned_number not in contacts_by_number:
                    contacts_by_number[cleaned_number] = []
                contacts_by_number[cleaned_number].append(contact_data)
        
        unique_contacts = []
        duplicate_contacts = []
        
        for cleaned_number, contacts_group in contacts_by_number.items():
            if len(contacts_group) > 1:
                logging.info(f"Found {len(contacts_group)} contacts for number {cleaned_number} in source. Deduplicating.")
                resolved_contact = self._resolve_duplicate_contacts(contacts_group)
                if cleaned_number in self.processed_numbers_log:
                    duplicate_contacts.append(resolved_contact)
                else:
                    unique_contacts.append(resolved_contact)
            else:
                contact = contacts_group[0]
                if cleaned_number in self.processed_numbers_log:
                    duplicate_contacts.append(contact)
                else:
                    unique_contacts.append(contact)
        
        return unique_contacts, duplicate_contacts

    def get_all_contacts(self, vcf_path):
        """Get all contacts from VCF file without checking processed log (for batch processing)"""
        vcf_content = self._read_vcf(vcf_path)
        if vcf_content is None:
            return []
        extracted_contacts = self._extract_contact_data(vcf_content)
        
        # Group contacts by cleaned phone number
        contacts_by_number = defaultdict(list)
        for contact in extracted_contacts:
            cleaned_number = contact['cleaned_number']
            if cleaned_number:
                contacts_by_number[cleaned_number].append(contact)
        
        # Resolve duplicates within the same file
        all_contacts = []
        for cleaned_number, contacts_group in contacts_by_number.items():
            if len(contacts_group) > 1:
                logging.info(f"Found {len(contacts_group)} contacts for number {cleaned_number} in source. Deduplicating.")
                resolved_contact = self._resolve_duplicate_contacts(contacts_group)
                all_contacts.append(resolved_contact)
            else:
                all_contacts.append(contacts_group[0])
        
        return all_contacts

    def get_unique_and_duplicate_contacts(self, vcf_file_path):
        vcf_content = self._read_vcf(vcf_file_path)
        if vcf_content is None:
            return [], []
        extracted_contacts = self._extract_contact_data(vcf_content)
        return self._sort_contacts_by_log(extracted_contacts)

    def get_unique_and_duplicate_contacts_from_text(self, text_content):
        if not text_content or not text_content.strip():
            return [], []
        extracted_contacts = self._extract_contacts_from_text(text_content)
        return self._sort_contacts_by_log(extracted_contacts)

    def update_sender_name(self, sender_name):
        """Update the sender name for Excel output"""
        self.sender_name = sender_name
        logging.info(f"Updated sender name to: {sender_name}")

    def process_and_save(self, contacts_to_process, output_dir, base_name):
        if not contacts_to_process: return None
        output_data, newly_processed_numbers = [], set()
        for contact in contacts_to_process:
            cleaned_number = contact['cleaned_number']
            cleaned_name = self._clean_name(contact['original_name'])
            if cleaned_number:
                if self.excel_format == 'novo_programa':
                    # Novo Programa format: Primeiro nome, Sobrenome, Telefone, Etiquetas
                    # First name is the contact's full name
                    first_name = cleaned_name
                    # Both Sobrenome and Etiquetas use the sender name
                    sender_name = getattr(self, 'sender_name', self.sender_indicator)
                    
                    output_data.append({
                        'Primeiro nome': first_name,
                        'Sobrenome': sender_name,
                        'Telefone': int(cleaned_number),
                        'Etiquetas': sender_name
                    })
                else:
                    # Standard format: Number, Name
                    output_data.append({'Number': int(cleaned_number), 'Name': cleaned_name})
                newly_processed_numbers.add(cleaned_number)
        if not output_data: return None
        
        try:
            # Ensure we have a writable log path before operation
            self.log_file_path = self._ensure_writable_log_path(self.log_file_path)
            
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                for number in newly_processed_numbers: f.write(f"{number}\n")
            logging.info(f"Appended {len(newly_processed_numbers)} numbers to log.")
        except Exception as e:
            logging.error(f"Error writing to log file: {e}")

        output_df = pd.DataFrame(output_data)
        
        try:
            # Logic is now simple and direct, no more guessing
            os.makedirs(output_dir, exist_ok=True)
            output_file_path = os.path.join(output_dir, f"{base_name}.xlsx")
            
            counter = 1
            while os.path.exists(output_file_path):
                output_file_path = os.path.join(output_dir, f"{base_name}_{counter}.xlsx")
                counter += 1
            
            logging.info(f"Saving Excel file to: {output_file_path}")
            
            output_df.to_excel(output_file_path, index=False, engine='openpyxl')
            
            if os.path.exists(output_file_path):
                file_size = os.path.getsize(output_file_path)
                logging.info(f"Excel file created successfully: {output_file_path} ({file_size} bytes)")
                return output_file_path
            else:
                logging.error(f"Failed to create Excel file: {output_file_path}")
                return None
        except Exception as e:
            logging.error(f"Error saving Excel file: {e}", exc_info=True)
            return None