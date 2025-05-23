import os
import zipfile
from datetime import datetime

# File CSV da salvare nel backup
file_list = ['dati_foto.csv', 'utenti.csv']
backup_dir = 'backup'
os.makedirs(backup_dir, exist_ok=True)

# Crea il nome del file zip con data e ora
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
zip_filename = f"backup_fotoapp_{timestamp}.zip"
zip_path = os.path.join(backup_dir, zip_filename)

# Crea il file ZIP
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for file in file_list:
        if os.path.exists(file):
            zipf.write(file)

print(f"✅ Backup completato: {zip_path}")
