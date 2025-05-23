# photo_sharing.py - Modulo per gestione condivisioni

import csv
import secrets
import hashlib
from datetime import datetime, timedelta
from flask import abort, render_template, jsonify, request, session
import os

class GestoreCondivisioni:
    def __init__(self, csv_path="data/token_condivisione.csv"):
        self.csv_path = csv_path
        self.ensure_csv_exists()
    
    def ensure_csv_exists(self):
        """Crea il file CSV se non esiste"""
        if not os.path.exists(self.csv_path):
            os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['token', 'foto_ids', 'scadenza', 'creatore', 'titolo', 'creato_il', 'accessi', 'attivo'])
    
    def genera_token_sicuro(self):
        """Genera un token crittograficamente sicuro"""
        random_bytes = secrets.token_bytes(32)
        timestamp = str(datetime.now().timestamp())
        return hashlib.sha256((random_bytes + timestamp.encode())).hexdigest()[:16]
    
    def crea_condivisione(self, foto_ids, creatore, titolo="", giorni_scadenza=30):
        """Crea una nuova condivisione e restituisce il token"""
        token = self.genera_token_sicuro()
        scadenza = (datetime.now() + timedelta(days=giorni_scadenza)).strftime('%Y-%m-%d %H:%M:%S')
        creato_il = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Salva nel CSV
        with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                token,
                ','.join(map(str, foto_ids)),
                scadenza,
                creatore,
                titolo,
                creato_il,
                0,  # accessi iniziali
                1   # attivo
            ])
        
        return token
    
    def valida_token(self, token):
        """Verifica la validità del token"""
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['token'] == token and row['attivo'] == '1':
                        # Verifica scadenza
                        scadenza = datetime.strptime(row['scadenza'], '%Y-%m-%d %H:%M:%S')
                        if datetime.now() <= scadenza:
                            return row
            return None
        except Exception as e:
            print(f"Errore validazione token: {e}")
            return None
    
    def incrementa_accessi(self, token):
        """Incrementa il contatore degli accessi"""
        rows = []
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            # Trova e aggiorna la riga
            for row in rows:
                if row['token'] == token:
                    row['accessi'] = str(int(row['accessi']) + 1)
                    break
            
            # Riscrive il file
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['token', 'foto_ids', 'scadenza', 'creatore', 'titolo', 'creato_il', 'accessi', 'attivo']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
                
        except Exception as e:
            print(f"Errore incremento accessi: {e}")
    
    def ottieni_foto_condivise(self, token):
        """Restituisce la lista degli ID foto per un token valido"""
        condivisione = self.valida_token(token)
        if condivisione:
            self.incrementa_accessi(token)
            return [int(id.strip()) for id in condivisione['foto_ids'].split(',')]
        return []
    
    def disattiva_token(self, token, creatore):
        """Disattiva un token (solo il creatore può farlo)"""
        rows = []
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            for row in rows:
                if row['token'] == token and row['creatore'] == creatore:
                    row['attivo'] = '0'
                    break
            
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['token', 'foto_ids', 'scadenza', 'creatore', 'titolo', 'creato_il', 'accessi', 'attivo']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
                
            return True
        except Exception as e:
            print(f"Errore disattivazione token: {e}")
            return False
    
    def lista_condivisioni_utente(self, creatore):
        """Restituisce tutte le condivisioni create da un utente"""
        condivisioni = []
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['creatore'] == creatore:
                        condivisioni.append(row)
        except Exception as e:
            print(f"Errore lista condivisioni: {e}")
        
        return condivisioni

# Istanza globale del gestore
gestore_condivisioni = GestoreCondivisioni()

# Routes Flask da aggiungere alla tua app principale

def init_sharing_routes(app, foto_manager):
    """Inizializza le route per la condivisione"""
    
    @app.route('/condividi_token/<token>')
    def visualizza_condivisione(token):
        """Pagina pubblica per visualizzare foto condivise"""
        foto_ids = gestore_condivisioni.ottieni_foto_condivise(token)
        
        if not foto_ids:
            abort(404, "Link non valido o scaduto")
        
        # Carica le foto usando il tuo sistema esistente
        foto_condivise = []
        for foto_id in foto_ids:
            foto = foto_manager.ottieni_foto_per_id(foto_id)  # Adatta al tuo sistema
            if foto:
                foto_condivise.append(foto)
        
        # Ottieni informazioni sulla condivisione
        condivisione = gestore_condivisioni.valida_token(token)
        
        return render_template('condividi_token.html', 
                             foto_list=foto_condivise,
                             condivisione=condivisione,
                             token=token)
    
    @app.route('/condividi_token/<token>/foto/<int:foto_id>')
    def serve_foto_condivisa(token, foto_id):
        """Serve una foto specifica solo se il token è valido"""
        foto_ids = gestore_condivisioni.ottieni_foto_condivise(token)
        
        if foto_id not in foto_ids:
            abort(404)
        
        # Serve il file foto (adatta al tuo sistema)
        return foto_manager.serve_foto(foto_id)  # Implementa secondo il tuo sistema
    
    @app.route('/api/condivisione/crea', methods=['POST'])
    def crea_condivisione():
        """API per creare una nuova condivisione"""
        if not session.get('username'):  # Adatta al tuo sistema di auth
            abort(401)
        
        data = request.get_json()
        foto_ids = data.get('foto_ids', [])
        titolo = data.get('titolo', '')
        giorni_scadenza = data.get('giorni_scadenza', 30)
        creatore = session.get('username')  # Adatta al tuo sistema
        
        if not foto_ids:
            return jsonify({'error': 'Nessuna foto selezionata'}), 400
        
        token = gestore_condivisioni.crea_condivisione(
            foto_ids=foto_ids,
            creatore=creatore,
            titolo=titolo,
            giorni_scadenza=giorni_scadenza
        )
        
        base_url = "http://136.144.220.169:5000"
        link_condivisione = f"{base_url}/condividi_token/{token}"
        
        return jsonify({
            'success': True,
            'token': token,
            'link': link_condivisione,
            'scadenza': (datetime.now() + timedelta(days=giorni_scadenza)).strftime('%Y-%m-%d')
        })
    
    @app.route('/api/condivisione/lista')
    def lista_condivisioni():
        """API per ottenere le condivisioni dell'utente corrente"""
        if not session.get('username'):
            abort(401)
        
        creatore = session.get('username')
        condivisioni = gestore_condivisioni.lista_condivisioni_utente(creatore)
        
        return jsonify(condivisioni)
    
    @app.route('/api/condivisione/disattiva/<token>', methods=['POST'])
    def disattiva_condivisione(token):
        """API per disattivare una condivisione"""
        if not session.get('username'):
            abort(401)
        
        creatore = session.get('username')
        success = gestore_condivisioni.disattiva_token(token, creatore)
        
        return jsonify({'success': success})

# Esempio di utilizzo nel main della tua app:
"""
# Nel tuo app.py principale, aggiungi:

from photo_sharing import init_sharing_routes

# Dopo aver creato l'app Flask
init_sharing_routes(app, foto_manager)
"""