from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import csv, os, json, threading, zipfile, tempfile
from PIL import Image
from datetime import datetime
from werkzeug.utils import secure_filename
from photo_sharing import init_sharing_routes

app = Flask(__name__)
app.secret_key = 'supersegreto'
BASE_FOLDER = os.path.join('static', 'foto')
CSV_FILE = 'dati_foto.csv'
USERS_FILE = 'utenti.csv'
LOG_FILE = 'log_attivita.csv'

# Crea le cartelle necessarie e il file di log se non esistono
os.makedirs(BASE_FOLDER, exist_ok=True)
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['timestamp', 'ip', 'utente', 'evento', 'categoria', 'foto_id'])

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def carica_utenti():
    """Carica gli utenti dal file CSV"""
    utenti = []
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                if 'permessi' in row and row['permessi'].startswith('{'):
                    try:
                        row['permessi'] = json.loads(row['permessi'])
                    except json.JSONDecodeError:
                        row['permessi'] = {}
                utenti.append(row)
    return utenti

def carica_foto():
    """Carica i dati delle foto dal file CSV"""
    foto = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline='', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            headers = next(reader, None)  # Legge l'intestazione
            for row in reader:
                if len(row) >= 6 and row[0].isdigit():
                    while len(row) < 8:
                        row.append('')
                    # Converti in dizionario per compatibilità con entrambe le versioni
                    item = {
                        'id': row[0],
                        'titolo': row[1],
                        'descrizione': row[2],
                        'data': row[3],
                        'nome_file': row[4],
                        'categoria': row[5],
                        'peso_file': row[6] if len(row) > 6 else '',
                        'copertina': row[7] if len(row) > 7 else ''
                    }
                    foto.append(item)
    return foto

def salva_foto(foto_list):
    """Salva l'elenco di foto nel file CSV"""
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['id', 'titolo', 'descrizione', 'data', 'nome_file', 'categoria', 'peso_file', 'copertina']
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(foto_list)

def log_evento(ip, utente, evento, categoria='', foto_id=''):
    log_path = 'log_attivita.csv'
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with open(log_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow([timestamp, ip, utente, evento, categoria, foto_id])


def genera_nuovo_id():
    """Genera un nuovo ID unico per una foto"""
    foto = carica_foto()
    if not foto:
        return 1
    id_correnti = [int(f['id']) for f in foto if f['id'].isdigit()]
    return max(id_correnti) + 1 if id_correnti else 1

def ruota_immagine(percorso_file, direzione=90):
    """Ruota un'immagine in senso orario (default) o antiorario"""
    try:
        img = Image.open(percorso_file)
        img = img.rotate(direzione, expand=True)
        img.save(percorso_file)
        return True
    except Exception as e:
        print(f"Errore nella rotazione immagine: {e}")
        return False

def formatta_data(data_str):
    """Formatta una data in formato leggibile"""
    try:
        return datetime.strptime(data_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return data_str

def utente_ha_permesso(categoria, tipo_permesso):
    """Verifica se l'utente corrente ha un determinato permesso per una categoria"""
    ruolo = session.get('ruolo')
    permessi = session.get('permessi')
    
    # Admin ha tutti i permessi
    if ruolo == 'admin':
        return True
    
    # Utente con permessi globali
    if permessi == 'ALL':
        return True
        
    # Utente con permessi specifici
    if isinstance(permessi, dict):
        if categoria in permessi and tipo_permesso in permessi[categoria]:
            return True
    
    return False

def categorie_con_permesso(tipo_permesso):
    """Restituisce le categorie a cui l'utente ha un determinato permesso"""
    ruolo = session.get('ruolo')
    permessi = session.get('permessi')
    
    if ruolo == 'admin' or permessi == 'ALL':
        # Admin o utente con permessi completi vede tutto
        return None  # Nessuna limitazione
    
    categorie = []
    if isinstance(permessi, dict):
        for cat, perms in permessi.items():
            if tipo_permesso in perms:
                categorie.append(cat)
    
    return categorie

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import csv, os, json, threading, zipfile, tempfile
from PIL import Image, ExifTags
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersegreto'
BASE_FOLDER = os.path.join('static', 'foto')
CSV_FILE = 'dati_foto.csv'
USERS_FILE = 'utenti.csv'

os.makedirs(BASE_FOLDER, exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def extract_exif_date(image_path):
    """Estrae la data EXIF di una foto se presente"""
    try:
        img = Image.open(image_path)
        exif_data = img._getexif()
        if exif_data:
            for tag, value in exif_data.items():
                tag_name = ExifTags.TAGS.get(tag)
                if tag_name == "DateTimeOriginal":
                    return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
    except Exception as e:
        print(f"Errore lettura EXIF da {image_path}: {e}")
    return None

# Funzioni come carica_utenti, carica_foto, ecc.

@app.route('/')
def index():
    tutte = carica_foto()
    
    categorie_old = {}
    categorie_principali = {}
    
    for foto in tutte:
        categoria_completa = foto['categoria']
        
        # Vecchio formato
        if utente_ha_permesso(categoria_completa, 'visualizza') or not session.get('username'):
            if categoria_completa not in categorie_old:
                categorie_old[categoria_completa] = []
            categorie_old[categoria_completa].append(foto)
        
        # Nuovo formato: categorie con /
        if '/' in categoria_completa:
            cat_principale, cat_secondaria = categoria_completa.split('/', 1)
            cat_principale = cat_principale.strip()
            cat_secondaria = cat_secondaria.strip()
            display_name = f"{cat_principale} / {cat_secondaria}"
        elif '>' in categoria_completa:
            cat_principale, cat_secondaria = categoria_completa.split('>', 1)
            cat_principale = cat_principale.strip()
            cat_secondaria = cat_secondaria.strip()
            display_name = f"{cat_principale} > {cat_secondaria}"
        else:
            cat_principale = categoria_completa
            cat_secondaria = "Principale"
            display_name = categoria_completa
        
        if utente_ha_permesso(categoria_completa, 'visualizza') or not session.get('username'):
            if cat_principale not in categorie_principali:
                categorie_principali[cat_principale] = {
                    'nome': cat_principale,
                    'sottocategorie': {}
                }
            if cat_secondaria not in categorie_principali[cat_principale]['sottocategorie']:
                categorie_principali[cat_principale]['sottocategorie'][cat_secondaria] = {
                    'nome': display_name,
                    'categoria_completa': categoria_completa,
                    'foto': []
                }
            categorie_principali[cat_principale]['sottocategorie'][cat_secondaria]['foto'].append(foto)
    
    for cat in categorie_old:
        categorie_old[cat].sort(key=lambda f: '0' if f['copertina'].strip().lower() in ('1', 'si', 'sì', 'true') else '1')

    for cat_princ in categorie_principali.values():
        for subcat in cat_princ['sottocategorie'].values():
            subcat['foto'].sort(key=lambda f: '0' if f['copertina'].strip().lower() in ('1', 'si', 'sì', 'true') else '1')
    
    return render_template('index.html', categorie=categorie_old, categorie_principali=categorie_principali)

@app.route('/categoria/<path:nome>')
def mostra_categoria(nome):
    if session.get('username') and not utente_ha_permesso(nome, 'visualizza'):
        flash("Non hai i permessi per visualizzare questa categoria")
        return redirect(url_for('index'))
    
    sort_by = request.args.get('sort', 'default')
    tutte = carica_foto()
    
    # Trova le foto dirette di questa categoria
    foto_categoria = []
    for f in [f for f in tutte if f['categoria'] == nome]:
        try:
            data_formattata = formatta_data(f['data'])
        except Exception:
            data_formattata = f['data']
        
        exif_date = None
        if sort_by == 'exif':
            path_locale = os.path.join("static", f['nome_file'])
            exif_date = extract_exif_date(path_locale)
        
        foto_categoria.append({
            'id': f['id'],
            'titolo': f['titolo'],
            'descrizione': f['descrizione'],
            'data_formattata': data_formattata,
            'data_raw': f['data'],
            'nome_file': f['nome_file'],
            'categoria': f['categoria'],
            'exif_date': exif_date,
            'id_numerico': int(f['id'])
        })
    
    # Applica ordinamento
    if sort_by == 'data':
        foto_categoria.sort(key=lambda x: x['data_raw'], reverse=True)
    elif sort_by == 'inserimento':
        foto_categoria.sort(key=lambda x: x['id_numerico'], reverse=True)
    elif sort_by == 'nome':
        foto_categoria.sort(key=lambda x: os.path.basename(x['nome_file'].lower()))
    elif sort_by == 'exif':
        foto_categoria.sort(key=lambda x: (x['exif_date'] is None, x['exif_date'] if x['exif_date'] else ''), reverse=True)

    # Prepara le foto per il template (formato compatibile)
    foto_template = []
    for f in foto_categoria:
        foto_template.append([
            f['id'],
            f['titolo'],
            f['descrizione'],
            f['data_formattata'],
            f['nome_file'],
            f['categoria']
        ])

    # NUOVA PARTE: Trova le sottocategorie
    sottocategorie = []
    
    # Cerca tutte le categorie che iniziano con questo nome + separatore
    prefisso_slash = nome + "/"
    prefisso_maggiore = nome + ">"
    
    categorie_trovate = set()
    for f in tutte:
        cat = f['categoria']
        if cat.startswith(prefisso_slash) or cat.startswith(prefisso_maggiore):
            categorie_trovate.add(cat)
    
    # Per ogni sottocategoria trovata, conta le foto e prepara i dati
    for categoria_completa in sorted(categorie_trovate):
        # Estrai il nome della sottocategoria
        if '/' in categoria_completa:
            nome_breve = categoria_completa.split('/', 1)[1].strip()
        elif '>' in categoria_completa:
            nome_breve = categoria_completa.split('>', 1)[1].strip()
        else:
            continue
        
        # Trova tutte le foto di questa sottocategoria
        foto_sottocategoria = [f for f in tutte if f['categoria'] == categoria_completa]
        num_foto = len(foto_sottocategoria)
        
        # Trova la foto copertina (se esiste)
        foto_copertina = None
        for f in foto_sottocategoria:
            if f.get('copertina', '').strip().lower() in ('1', 'si', 'sì', 'true'):
                foto_copertina = f
                break
        
        # Se non c'è una copertina specifica, prendi la prima foto
        if not foto_copertina and foto_sottocategoria:
            foto_copertina = foto_sottocategoria[0]
        
        # Aggiungi alla lista solo se ci sono foto e l'utente ha i permessi
        if num_foto > 0 and (not session.get('username') or utente_ha_permesso(categoria_completa, 'visualizza')):
            sottocategorie.append({
                'categoria_completa': categoria_completa,
                'nome_breve': nome_breve,
                'num_foto': num_foto,
                'foto_copertina': foto_copertina
            })

    return render_template('categoria.html', 
                         nome=nome, 
                         foto=foto_template, 
                         sort_by=sort_by,
                         sottocategorie=sottocategorie)

@app.route('/modifica/<id_foto>', methods=['GET', 'POST'])
def modifica(id_foto):
    if not session.get('username'):
        flash("Devi effettuare il login per modificare le foto")
        return redirect(url_for('login'))
    
    tutte = carica_foto()
    foto_dict = next((f for f in tutte if f['id'] == id_foto), None)
    
    if not foto_dict:
        flash("Foto non trovata")
        return redirect(url_for('index'))
    
    if not utente_ha_permesso(foto_dict['categoria'], 'modifica'):
        flash("Non hai i permessi per modificare questa foto")
        return redirect(url_for('mostra_categoria', nome=foto_dict['categoria']))
    
    if request.method == 'POST':
        modificato = False
        
        if request.form.get('titolo'):
            foto_dict['titolo'] = request.form.get('titolo')
            modificato = True
        
        if request.form.get('descrizione'):
            foto_dict['descrizione'] = request.form.get('descrizione')
            modificato = True
        
        if request.form.get('data'):
            foto_dict['data'] = request.form.get('data')
            modificato = True
        
        if request.form.get('categoria'):
            foto_dict['categoria'] = request.form.get('categoria')
            modificato = True
        
        if 'ruota90' in request.form:
            path_locale = os.path.join("static", foto_dict['nome_file'])
            ruota_immagine(path_locale)
            modificato = True
        
        if modificato:
            salva_foto(tutte)
            log_evento(request.remote_addr, session['username'], 'modifica', foto_dict['categoria'], id_foto)
            flash("Modifica effettuata con successo")
        else:
            flash("Nessuna modifica effettuata")
        
        return redirect(url_for('mostra_categoria', nome=foto_dict['categoria']))
    
    foto = {
        'ID': foto_dict['id'],
        'Titolo': foto_dict['titolo'],
        'Descrizione': foto_dict['descrizione'],
        'Data': foto_dict['data'],
        'Percorso': foto_dict['nome_file'],
        'Categoria': foto_dict['categoria']
    }
    
    categorie = sorted(set(f['categoria'] for f in tutte))
    return render_template('modifica.html', foto=foto, categorie=categorie)

@app.route('/aggiungi', methods=['GET', 'POST'])
def aggiungi():
    if not session.get('username'):
        flash("Devi effettuare il login per aggiungere foto")
        return redirect(url_for('login'))
    
    tutte = carica_foto()
    categorie_permesse = categorie_con_permesso('aggiungi')
    
    if categorie_permesse is not None and not categorie_permesse:
        flash("Non hai i permessi per aggiungere foto")
        return redirect(url_for('index'))
    
    categorie_esistenti = sorted(set(f['categoria'] for f in tutte))
    if categorie_permesse is not None:
        categorie_disponibili = [c for c in categorie_esistenti if c in categorie_permesse]
    else:
        categorie_disponibili = categorie_esistenti
    
    struttura_categorie = {}
    categorie_principali = []
    
    for categoria in categorie_disponibili:
        if '/' in categoria:
            cat_princ, cat_sec = categoria.split('/', 1)
            cat_princ = cat_princ.strip()
            cat_sec = cat_sec.strip()
        elif '>' in categoria:
            cat_princ, cat_sec = categoria.split('>', 1)
            cat_princ = cat_princ.strip()
            cat_sec = cat_sec.strip()
        else:
            cat_princ = categoria.strip()
            cat_sec = None
            
        if cat_princ not in categorie_principali:
            categorie_principali.append(cat_princ)
            
        if cat_princ not in struttura_categorie:
            struttura_categorie[cat_princ] = []
            
        if cat_sec and cat_sec not in struttura_categorie[cat_princ]:
            struttura_categorie[cat_princ].append(cat_sec)
    
    if request.method == 'POST':
        titolo = request.form.get('titolo', '').strip()
        descrizione = request.form.get('descrizione', '').strip()
        data = request.form.get('data', '').strip()
        
        tipo_categoria = request.form.get("tipo_categoria")
        categoria = ""

        if tipo_categoria == "esistente":
            categoria = request.form.get("categoria_esistente")
        elif tipo_categoria == "nuova_principale":
            categoria = request.form.get("nuova_categoria_principale")
        elif tipo_categoria == "nuova_sotto":
            principale = request.form.get("categoria_principale")
            separatore = request.form.get("tipo_separatore", "/")
            sottocat = request.form.get("nuova_sottocategoria")
            if principale and sottocat:
                categoria = f"{principale}{separatore}{sottocat}"

        if categoria:
            categoria = categoria.strip().replace(" > ", "/").replace(" / ", "/")

        if categorie_permesse is not None and categoria not in categorie_permesse:
            flash(f"Non hai i permessi per aggiungere foto nella categoria {categoria}")
            return redirect(url_for('aggiungi'))
        
        if not data:
            data = datetime.today().strftime('%Y-%m-%d')
        
        files = request.files.getlist('file[]')
        for file in files:
            if file and file.filename:
                nuovo_id = max([int(f['id']) for f in tutte if f['id'].isdigit()] + [0]) + 1
                filename = secure_filename(file.filename).lower()
                folder = os.path.join(BASE_FOLDER, categoria)
                os.makedirs(folder, exist_ok=True)
                
                base, ext = os.path.splitext(filename)
                counter = 1
                save_path = os.path.join(folder, filename)
                while os.path.exists(save_path):
                    filename = f"{base}_{counter}{ext}"
                    save_path = os.path.join(folder, filename)
                    counter += 1
                
                img = Image.open(file)
                img.thumbnail((1024, 1024))
                img.save(save_path, optimize=True, quality=85)
                
                peso_kb = os.path.getsize(save_path) // 1024
                relative_path = f"foto/{categoria}/{filename}"
                
                tutte.append({
                    'id': str(nuovo_id),
                    'titolo': titolo,
                    'descrizione': descrizione,
                    'data': data,
                    'nome_file': relative_path,
                    'categoria': categoria,
                    'peso_file': str(peso_kb),
                    'copertina': ''
                })
                
                log_evento(request.remote_addr, session['username'], 'aggiungi', categoria, str(nuovo_id))
        
        salva_foto(tutte)
        flash("Le foto sono state caricate con successo")
        return redirect(url_for('index'))
    
    return render_template('aggiungi.html', 
                         categorie=categorie_disponibili, 
                         struttura_categorie=struttura_categorie, 
                         categorie_principali=categorie_principali)

@app.route('/upload_massivo', methods=['GET', 'POST'])
def upload_massivo():
    if not session.get('username'):
        flash("Devi effettuare il login per caricare immagini")
        return redirect(url_for('login'))

    tutte = carica_foto()
    categorie = sorted(set(f['categoria'] for f in tutte))

    if request.method == 'POST':
        categoria = request.form.get('categoria')
        titolo = request.form.get('titolo', '').strip()
        descrizione = request.form.get('descrizione', '').strip()
        data = request.form.get('data') or datetime.today().strftime('%Y-%m-%d')
        files = request.files.getlist('file[]')

        for file in files:
            if file and file.filename:
                nuovo_id = max([int(f['id']) for f in tutte if f['id'].isdigit()] + [0]) + 1
                filename = secure_filename(file.filename).lower()
                folder = os.path.join(BASE_FOLDER, categoria)
                os.makedirs(folder, exist_ok=True)

                base, ext = os.path.splitext(filename)
                counter = 1
                save_path = os.path.join(folder, filename)
                while os.path.exists(save_path):
                    filename = f"{base}_{counter}{ext}"
                    save_path = os.path.join(folder, filename)
                    counter += 1

                img = Image.open(file)
                img.thumbnail((1024, 1024))
                img.save(save_path, optimize=True, quality=85)

                peso_kb = os.path.getsize(save_path) // 1024
                relative_path = f"foto/{categoria}/{filename}"

                tutte.append({
                    'id': str(nuovo_id),
                    'titolo': titolo,
                    'descrizione': descrizione,
                    'data': data,
                    'nome_file': relative_path,
                    'categoria': categoria,
                    'peso_file': str(peso_kb),
                    'copertina': ''
                })

        salva_foto(tutte)
        flash("Caricamento massivo completato con successo")
        return redirect(url_for('index'))

    oggi = datetime.today().strftime('%Y-%m-%d')
    return render_template('upload_massivo.html', categorie=categorie, oggi=oggi)

@app.route('/elimina/<id_foto>')
def elimina(id_foto):
    if not session.get('username'):
        flash("Devi effettuare il login per eliminare le foto")
        return redirect(url_for('login'))
    
    tutte = carica_foto()
    foto = next((f for f in tutte if f['id'] == id_foto), None)
    
    if not foto:
        flash("Foto non trovata")
        return redirect(url_for('index'))
    
    if not utente_ha_permesso(foto['categoria'], 'elimina'):
        flash("Non hai i permessi per eliminare questa foto")
        return redirect(url_for('mostra_categoria', nome=foto['categoria']))
    
    path = os.path.join('static', foto['nome_file'])
    if os.path.exists(path):
        os.remove(path)
    
    tutte = [f for f in tutte if f['id'] != id_foto]
    salva_foto(tutte)
    
    log_evento(request.remote_addr, session['username'], 'elimina', foto['categoria'], id_foto)
    flash("Foto eliminata con successo")
    return redirect(url_for('mostra_categoria', nome=foto['categoria']))

@app.route('/elimina_categoria/<nome>')
def elimina_categoria(nome):
    if not session.get('username'):
        flash("Devi effettuare il login per eliminare categorie")
        return redirect(url_for('login'))
    
    if not utente_ha_permesso(nome, 'elimina'):
        flash("Non hai i permessi per eliminare questa categoria")
        return redirect(url_for('index'))
    
    tutte = carica_foto()
    nuove = [f for f in tutte if f['categoria'] != nome]
    
    cartella = os.path.join(BASE_FOLDER, nome)
    if os.path.exists(cartella):
        import shutil
        shutil.rmtree(cartella)
    
    salva_foto(nuove)
    
    log_evento(request.remote_addr, session['username'], 'elimina_categoria', nome)
    flash("Categoria eliminata con successo")
    return redirect(url_for('index'))

@app.route('/copertina/<id_foto>')
def imposta_copertina(id_foto):
    if not session.get('username'):
        flash("Devi effettuare il login per impostare la copertina")
        return redirect(url_for('login'))
    
    tutte = carica_foto()
    foto = next((f for f in tutte if f['id'] == id_foto), None)
    
    if not foto:
        flash("Foto non trovata")
        return redirect(url_for('index'))
    
    if not utente_ha_permesso(foto['categoria'], 'modifica'):
        flash("Non hai i permessi per modificare questa categoria")
        return redirect(url_for('mostra_categoria', nome=foto['categoria']))
    
    categoria = foto['categoria']
    
    for f in tutte:
        if f['categoria'] == categoria:
            f['copertina'] = ''
    
    foto['copertina'] = '1'
    
    salva_foto(tutte)
    
    log_evento(request.remote_addr, session['username'], 'imposta_copertina', categoria, id_foto)
    flash("Copertina impostata correttamente")
    return redirect(url_for('mostra_categoria', nome=categoria))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        utenti = carica_utenti()
        
        for utente in utenti:
            if utente['username'] == username and utente['password'] == password:
                session['username'] = username
                session['ruolo'] = utente['ruolo']
                session['permessi'] = json.loads(utente['permessi']) if isinstance(utente['permessi'], str) and utente['permessi'].startswith('{') else utente['permessi']
                log_evento(request.remote_addr, username, 'login')
                flash(f"Benvenuto, {username}!")
                return redirect(url_for('index'))
        
        log_evento(request.remote_addr, username, 'tentativo_login_fallito')
        flash("Username o password non validi")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    username = session.get('username', '')
    if username:
        log_evento(request.remote_addr, username, 'logout')
    session.clear()
    flash(f"Arrivederci, {username}!")
    return redirect(url_for('index'))

@app.route('/gestione_utenti')
def gestione_utenti():
    if not session.get('username') or session.get('ruolo') != 'admin':
        flash("Solo l'amministratore può gestire gli utenti")
        return redirect(url_for('index'))
    
    # Carica utenti
    utenti = carica_utenti()
    
    # Carica tutte le categorie esistenti dalle foto
    tutte_le_foto = carica_foto()
    categorie = sorted(set(f['categoria'] for f in tutte_le_foto))
    
    # Debug: stampa i permessi per verificare il formato
    for utente in utenti:
        print(f"Utente {utente['username']}, permessi: {type(utente['permessi'])}, {utente['permessi']}")
    
    return render_template('gestione_utenti.html', utenti=utenti, categorie=categorie)


def normalizza_formato_permessi(utenti):
    """Normalizza tutti i formati dei permessi in JSON valido."""
    for u in utenti:
        if u['permessi'] == 'ALL':
            continue

        if isinstance(u['permessi'], str):
            try:
                if u['permessi'].startswith('{'):
                    try:
                        permessi_dict = json.loads(u['permessi'])
                    except:
                        permessi_dict = ast.literal_eval(u['permessi'])
                    u['permessi'] = json.dumps(permessi_dict, ensure_ascii=False)
            except Exception as e:
                print(f"Errore nella conversione dei permessi per {u['username']}: {e}")
        elif isinstance(u['permessi'], dict):
            u['permessi'] = json.dumps(u['permessi'], ensure_ascii=False)
    return utenti

@app.route('/aggiorna_permessi/<username>', methods=['POST'])
def aggiorna_permessi(username):
    if not session.get('username') or session.get('ruolo') != 'admin':
        flash("Solo l'amministratore può modificare i permessi")
        return redirect(url_for('index'))
    
    utenti = carica_utenti()
    user = next((u for u in utenti if u['username'] == username), None)
    
    if not user:
        flash("Utente non trovato")
        return redirect(url_for('gestione_utenti'))
    
    # Aggiorna i permessi
    categoria_selezionata = request.form.get('categoria')
    
    # Gestione nuova categoria
    if categoria_selezionata == 'nuova':
        categoria = request.form.get('nuova_categoria', '').strip()
        if not categoria:
            flash("Devi specificare un nome per la nuova categoria")
            return redirect(url_for('gestione_utenti'))
    else:
        categoria = categoria_selezionata
    
    azione = request.form.get('azione')  # 'aggiungi' o 'rimuovi'
    permessi_selezionati = request.form.getlist('permessi[]')  # Ottieni tutti i permessi selezionati
    
    if user['permessi'] == 'ALL':
        flash("Non è possibile modificare i permessi di un utente admin")
        return redirect(url_for('gestione_utenti'))
    
    # Ottieni il dizionario dei permessi
    permessi = user['permessi']
    if isinstance(permessi, str) and permessi.startswith('{'):
        try:
            permessi = json.loads(permessi)
        except Exception as e:
            print(f"Errore nel parsing JSON: {e}")
            permessi = {}
    
    # Debug
    print(f"Prima della modifica: {permessi}")
    
    if azione == 'aggiungi':
        if categoria not in permessi:
            permessi[categoria] = []
        # Aggiungi tutti i permessi selezionati
        for permesso in permessi_selezionati:
            if permesso not in permessi[categoria]:
                permessi[categoria].append(permesso)
    elif azione == 'rimuovi':
        # Rimuovi tutti i permessi selezionati
        for permesso in permessi_selezionati:
            if categoria in permessi and permesso in permessi[categoria]:
                permessi[categoria].remove(permesso)
        # Elimina la categoria se vuota
        if categoria in permessi and not permessi[categoria]:
            del permessi[categoria]
    
    # Debug
    print(f"Dopo la modifica: {permessi}")
    
    # Salva gli utenti con permessi normalizzati
    user['permessi'] = permessi  # Passa il dizionario, normalizza_formato_permessi lo convertirà
    with open(USERS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['username', 'password', 'ruolo', 'permessi'], delimiter=';')
        writer.writeheader()
        writer.writerows(normalizza_formato_permessi(utenti))
    
    flash("Permessi aggiornati con successo")
    return redirect(url_for('gestione_utenti'))

@app.route('/crea_utente', methods=['POST'])
def crea_utente():
    """
    Crea un nuovo utente con i permessi specificati.
    """
    if not session.get('username') or session.get('ruolo') != 'admin':
        flash("Solo l'amministratore può creare nuovi utenti")
        return redirect(url_for('index'))
    
    username = request.form.get('username')
    password = request.form.get('password')
    ruolo = request.form.get('ruolo')
    
    # Validazione dei dati
    if not username or not password or not ruolo:
        flash("Tutti i campi sono obbligatori")
        return redirect(url_for('gestione_utenti'))
    
    # Carica utenti esistenti
    utenti = carica_utenti()
    
    # Verifica che l'username non esista già
    if any(u['username'] == username for u in utenti):
        flash(f"L'username '{username}' è già in uso")
        return redirect(url_for('gestione_utenti'))
    
    # Gestione dei permessi
    if ruolo == 'admin':
        permessi = 'ALL'
    else:
        permessi = {}
        
        # Gestisci i permessi iniziali se specificati
        init_categoria = request.form.get('init_categoria')
        if init_categoria and init_categoria != '':
            # Gestione nuova categoria
            if init_categoria == 'nuova':
                nuova_categoria = request.form.get('init_nuova_categoria', '').strip()
                if nuova_categoria:
                    init_categoria = nuova_categoria
                else:
                    init_categoria = None
            
            # Aggiungi i permessi per la categoria specificata
            if init_categoria:
                init_permessi = request.form.getlist('init_permessi[]')
                if init_permessi:
                    permessi[init_categoria] = init_permessi
    
    # Crea il nuovo utente
    nuovo_utente = {
        'username': username,
        'password': password,
        'ruolo': ruolo,
        'permessi': permessi
    }
    
    # Aggiungi alla lista e salva
    utenti.append(nuovo_utente)
    
    with open(USERS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['username', 'password', 'ruolo', 'permessi'], delimiter=';')
        writer.writeheader()
        writer.writerows(normalizza_formato_permessi(utenti))
    
    flash(f"Utente '{username}' creato con successo")
    return redirect(url_for('gestione_utenti'))

@app.route('/elimina_utente/<username>', methods=['POST'])
def elimina_utente(username):
    """
    Elimina un utente dal sistema.
    """
    if not session.get('username') or session.get('ruolo') != 'admin':
        flash("Solo l'amministratore può eliminare utenti")
        return redirect(url_for('index'))
    
    # Impedisci l'eliminazione dell'utente admin o dell'utente corrente
    if username == 'admin' or username == session.get('username'):
        flash("Non puoi eliminare questo utente")
        return redirect(url_for('gestione_utenti'))
    
    # Carica gli utenti esistenti
    utenti = carica_utenti()
    
    # Filtra l'utente da eliminare
    utenti_aggiornati = [u for u in utenti if u['username'] != username]
    
    # Verifica che l'utente esistesse
    if len(utenti) == len(utenti_aggiornati):
        flash("Utente non trovato")
        return redirect(url_for('gestione_utenti'))
    
    # Salva gli utenti aggiornati
    with open(USERS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['username', 'password', 'ruolo', 'permessi'], delimiter=';')
        writer.writeheader()
        writer.writerows(normalizza_formato_permessi(utenti_aggiornati))
    
    flash(f"Utente '{username}' eliminato con successo")
    return redirect(url_for('gestione_utenti'))

@app.route('/crea_utenti_iniziali')
def crea_utenti_iniziali():
    """Funzione di utilità per creare il file utenti iniziale"""
    if os.path.exists(USERS_FILE):
        flash("Il file utenti esiste già")
        return redirect(url_for('index'))
    
    utenti = [
        {'username': 'admin', 'password': 'admin', 'ruolo': 'admin', 'permessi': 'ALL'},
        {'username': 'utente', 'password': 'utente', 'ruolo': 'utente', 'permessi': json.dumps({
            'generale': ['visualizza', 'aggiungi', 'modifica'],
            'vacanze': ['visualizza']
        })}
    ]
    
    with open(USERS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['username', 'password', 'ruolo', 'permessi'], delimiter=';')
        writer.writeheader()
        writer.writerows(normalizza_formato_permessi(utenti))
    
    flash("Utenti iniziali creati con successo")
    return redirect(url_for('index'))

@app.route('/condividi/<id_foto>')
def condividi(id_foto):
    tutte = carica_foto()
    foto = next((f for f in tutte if f['id'] == id_foto), None)
    if not foto:
        return "Foto non trovata", 404

    titolo = foto['titolo']
    descrizione = foto['descrizione']
    data = formatta_data(foto['data'])
    link = f"http://136.144.220.169:5000/static/{foto['nome_file']}"

    testo = f"Titolo: {titolo}\nDescrizione: {descrizione}\nData: {data}\nImmagine: {link}"
    return testo, 200, {'Content-Type': 'text/plain; charset=utf-8'}

@app.route('/condividi_html/<id_foto>')
def condividi_html(id_foto):
    tutte = carica_foto()
    foto = next((f for f in tutte if f['id'] == id_foto), None)
    if not foto:
        return "Foto non trovata", 404
    return render_template('condividi_foto.html', foto=foto)

@app.route('/download_image/<id_foto>')
def download_image(id_foto):
    """Fornisce l'immagine come allegato scaricabile con un nome file appropriato"""
    tutte = carica_foto()
    foto = next((f for f in tutte if f['id'] == id_foto), None)
    if not foto:
        return "Foto non trovata", 404
    
    # Percorso completo del file
    file_path = os.path.join('static', foto['nome_file'])
    
    # Nome file per il download (pulizia)
    filename = foto['titolo'].replace(' ', '_')
    if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
        # Determina l'estensione corretta dal percorso
        ext = os.path.splitext(foto['nome_file'])[1].lower()
        if not ext:
            ext = '.jpg'  # Default
        filename += ext
    
    # Invia il file come allegato (scaricabile)
    return send_file(file_path, as_attachment=True, download_name=filename)

@app.route('/condividi_diretto/<id_foto>')
def condividi_diretto(id_foto):
    """Versione migliorata della condivisione che supporta la condivisione diretta dell'immagine"""
    tutte = carica_foto()
    foto = next((f for f in tutte if f['id'] == id_foto), None)
    if not foto:
        return "Foto non trovata", 404
    
    # Creiamo un oggetto foto con un formato compatibile con il template
    foto_formattata = {
        'id': foto['id'],
        'titolo': foto['titolo'],
        'descrizione': foto['descrizione'],
        'data': formatta_data(foto['data']),
        'nome_file': foto['nome_file'],
        'categoria': foto['categoria']
    }
    
    return render_template('condividi_diretto.html', foto=foto_formattata)   

@app.route('/condividi_migliore/<id_foto>')
def condividi_migliore(id_foto):
    """Versione migliorata della condivisione con meta tag per social e istruzioni guidate"""
    tutte = carica_foto()
    foto = next((f for f in tutte if f['id'] == id_foto), None)
    if not foto:
        return "Foto non trovata", 404
    
    # Creiamo un oggetto foto con un formato compatibile con il template
    foto_formattata = {
        'id': foto['id'],
        'titolo': foto['titolo'],
        'descrizione': foto['descrizione'],
        'data': formatta_data(foto['data']),
        'nome_file': foto['nome_file'],
        'categoria': foto['categoria']
    }
    
    return render_template('condividi_migliore.html', foto=foto_formattata)

@app.route('/condividi_multiple/<ids>')
def condividi_multiple(ids):
    """Pagina di condivisione per più foto contemporaneamente"""
    if not ids:
        flash("Nessuna foto selezionata per la condivisione")
        return redirect(url_for('index'))
    
    # Separa gli ID e carica le foto
    id_list = ids.split(',')
    tutte = carica_foto()
    foto_list = []
    categorie = set()
    
    for id_foto in id_list:
        foto = next((f for f in tutte if f['id'] == id_foto), None)
        if foto:
            # Crea una copia del dizionario foto per non modificare i dati originali
            foto_copy = foto.copy()
            
            # Formatta la data se necessario
            try:
                foto_copy['data'] = formatta_data(foto['data'])
            except:
                pass
                
            foto_list.append(foto_copy)
            categorie.add(foto['categoria'])
    
    if not foto_list:
        flash("Nessuna delle foto selezionate è stata trovata")
        return redirect(url_for('index'))
    
    return render_template('condividi_multiple.html', 
                          foto_list=foto_list, 
                          ids=ids, 
                          categorie=list(categorie))

@app.route('/download_zip/<ids>')
def download_zip(ids):
    """Genera e scarica un archivio ZIP con tutte le foto selezionate"""
    if not ids:
        flash("Nessuna foto selezionata per il download")
        return redirect(url_for('index'))
    
    # Separa gli ID e carica le foto
    id_list = ids.split(',')
    tutte = carica_foto()
    foto_list = []
    
    for id_foto in id_list:
        foto = next((f for f in tutte if f['id'] == id_foto), None)
        if foto:
            foto_list.append(foto)
    
    if not foto_list:
        flash("Nessuna delle foto selezionate è stata trovata")
        return redirect(url_for('index'))
    
    # Crea un file ZIP temporaneo
    temp = tempfile.NamedTemporaryFile(delete=False)
    
    try:
        # Aggiungi tutte le foto al file ZIP
        with zipfile.ZipFile(temp.name, 'w', zipfile.ZIP_DEFLATED) as archive:
            for foto in foto_list:
                file_path = os.path.join("static", foto['nome_file'])
                if os.path.exists(file_path):
                    # Usa un nome file appropriato nella struttura dell'archivio
                    filename = os.path.basename(foto['nome_file'])
                    # Aggiungi un prefisso con la categoria per mantenere l'organizzazione
                    archive_path = os.path.join(foto['categoria'], filename)
                    archive.write(file_path, archive_path)
        
        # Invia il file ZIP al client
        return send_file(temp.name, 
                        as_attachment=True, 
                        download_name=f"galleria_foto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                        mimetype='application/zip')
    
    except Exception as e:
        print(f"Errore nella creazione del file ZIP: {e}")
        flash("Si è verificato un errore nella creazione del file ZIP")
        return redirect(url_for('index'))
    
    finally:
        # Chiudi e rimuovi il file temporaneo
        temp.close()
        try:
            os.unlink(temp.name)  # Rimuovi il file temporaneo
        except:
            pass  # Ignora eventuali errori nella rimozione

@app.route('/ricerca', methods=['GET'])
def ricerca():
    """Pagina di ricerca foto semplificata"""
    query = request.args.get('q', '').strip().lower()
    
    if not query:
        tutte = carica_foto()
        categorie = sorted(set(f['categoria'] for f in tutte))
        return render_template('ricerca.html', risultati=None, categorie=categorie)

    tutte = carica_foto()
    risultati = []

    for foto in tutte:
        if not (utente_ha_permesso(foto['categoria'], 'visualizza') or not session.get('username')):
            continue

        testo_foto = (
            foto['titolo'].lower() + ' ' + 
            foto['descrizione'].lower() + ' ' + 
            foto['categoria'].lower() + ' ' + 
            foto['nome_file'].lower() + ' ' +
            foto['data']
        )
        
        match = True
        query_parts = query.split()
        for part in query_parts:
            if part not in testo_foto:
                match = False
                break

        if match:
            try:
                data_formattata = formatta_data(foto['data'])
            except:
                data_formattata = foto['data']

            if '/' in foto['categoria']:
                cat_princ, cat_sec = foto['categoria'].split('/', 1)
                cat_display = f"{cat_princ} / {cat_sec}"
            elif '>' in foto['categoria']:
                cat_princ, cat_sec = foto['categoria'].split('>', 1)
                cat_display = f"{cat_princ} > {cat_sec}"
            else:
                cat_display = foto['categoria']

            risultati.append({
                'id': foto['id'],
                'titolo': foto['titolo'],
                'descrizione': foto['descrizione'],
                'data': data_formattata,
                'nome_file': foto['nome_file'],
                'categoria': foto['categoria'],
                'categoria_display': cat_display
            })

    risultati.sort(key=lambda x: x['data'], reverse=True)
    categorie = sorted(set(f['categoria'] for f in tutte))

    return render_template('ricerca.html',
                          risultati=risultati,
                          query=query,
                          categoria='',
                          data_inizio='',
                          data_fine='',
                          categorie=categorie,
                          num_risultati=len(risultati))

@app.route('/api/search_suggestions', methods=['GET'])
def search_suggestions():
    """API per fornire suggerimenti di auto-completamento per la ricerca"""
    query = request.args.get('q', '').strip().lower()

    if not query or len(query) < 2:
        return jsonify([])

    tutte = carica_foto()
    words = set()

    for foto in tutte:
        if not (utente_ha_permesso(foto['categoria'], 'visualizza') or not session.get('username')):
            continue

        title_words = foto['titolo'].lower().split()
        for word in title_words:
            if word.startswith(query) and len(word) > 3:
                words.add(word)

        if foto['categoria'].lower().startswith(query):
            words.add(foto['categoria'].lower())

    suggestions = sorted(list(words))[:10]
    return jsonify(suggestions)

@app.route('/download_search_results')
def download_search_results():
    """Scarica i risultati della ricerca come file ZIP"""
    query = request.args.get('q', '').strip().lower()
    categoria = request.args.get('categoria', '')
    data_inizio = request.args.get('data_inizio', '')
    data_fine = request.args.get('data_fine', '')

    tutte = carica_foto()
    foto_trovate = []

    for foto in tutte:
        if not (utente_ha_permesso(foto['categoria'], 'visualizza') or not session.get('username')):
            continue

        match = True
        if query:
            testo_foto = (
                foto['titolo'].lower() + ' ' +
                foto['descrizione'].lower() + ' ' +
                foto['categoria'].lower() + ' ' +
                foto['nome_file'].lower() + ' ' +
                foto['data']
            )
            query_parts = query.split()
            for part in query_parts:
                if part not in testo_foto:
                    match = False
                    break

        if match and categoria and categoria != 'tutte':
            if not foto['categoria'].startswith(categoria):
                match = False

        if match and data_inizio:
            try:
                data_foto = datetime.strptime(foto['data'], '%Y-%m-%d').date()
                data_min = datetime.strptime(data_inizio, '%Y-%m-%d').date()
                if data_foto < data_min:
                    match = False
            except ValueError:
                pass

        if match and data_fine:
            try:
                data_foto = datetime.strptime(foto['data'], '%Y-%m-%d').date()
                data_max = datetime.strptime(data_fine, '%Y-%m-%d').date()
                if data_foto > data_max:
                    match = False
            except ValueError:
                pass

        if match:
            foto_trovate.append(foto)

    if not foto_trovate:
        flash("Nessuna foto trovata con i criteri di ricerca specificati")
        return redirect(url_for('ricerca', q=query, categoria=categoria, data_inizio=data_inizio, data_fine=data_fine))

    temp = tempfile.NamedTemporaryFile(delete=False)

    try:
        descrizione_ricerca = []
        if query:
            descrizione_ricerca.append(f"ricerca_{query}")
        if categoria and categoria != 'tutte':
            descrizione_ricerca.append(f"cat_{categoria}")
        if data_inizio:
            descrizione_ricerca.append(f"da_{data_inizio}")
        if data_fine:
            descrizione_ricerca.append(f"a_{data_fine}")

        if not descrizione_ricerca:
            zip_name = f"galleria_risultati_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        else:
            joined = "_".join(descrizione_ricerca)
            if len(joined) > 50:
                joined = joined[:50]
            zip_name = f"galleria_{joined}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

        with zipfile.ZipFile(temp.name, 'w', zipfile.ZIP_DEFLATED) as archive:
            for foto in foto_trovate:
                file_path = os.path.join("static", foto['nome_file'])
                if os.path.exists(file_path):
                    filename = os.path.basename(foto['nome_file'])
                    archive_path = os.path.join(foto['categoria'], filename)
                    archive.write(file_path, archive_path)

                    metadata = f"Titolo: {foto['titolo']}\n"
                    metadata += f"Descrizione: {foto['descrizione']}\n"
                    metadata += f"Data: {foto['data']}\n"
                    metadata += f"Categoria: {foto['categoria']}\n"
                    metadata_filename = os.path.splitext(filename)[0] + "_info.txt"
                    metadata_path = os.path.join(foto['categoria'], metadata_filename)

                    with tempfile.NamedTemporaryFile(mode='w', delete=False) as meta_file:
                        meta_file.write(metadata)
                        meta_file.flush()
                        archive.write(meta_file.name, metadata_path)
                        os.unlink(meta_file.name)

        return send_file(temp.name,
                        as_attachment=True,
                        download_name=zip_name,
                        mimetype='application/zip')

    except Exception as e:
        print(f"Errore nella creazione del file ZIP: {e}")
        flash("Si è verificato un errore nella creazione del file ZIP")
        return redirect(url_for('ricerca', q=query, categoria=categoria, data_inizio=data_inizio, data_fine=data_fine))

    finally:
        temp.close()
        try:
            os.unlink(temp.name)
        except:
            pass

@app.route('/report_attivita')
def report_attivita():
    if not session.get('username') or session.get('ruolo') != 'admin':
        flash("Solo l'amministratore può accedere al report attività")
        return redirect(url_for('index'))

    log_path = 'log_attivita.csv'
    if not os.path.exists(log_path):
        return render_template('report_attivita.html', riepiloghi=[], messaggio="Nessuna attività registrata.")

    riepilogo_per_utente = {}

    with open(log_path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        # Salta l'intestazione se presente
        first_row = next(reader, None)
        if first_row and first_row[0] == 'timestamp':
            pass  # Era l'intestazione, continua
        else:
            # Non era l'intestazione, processa questa riga
            if first_row and len(first_row) >= 4:
                timestamp, ip, utente, evento = first_row[:4]
                categoria = first_row[4] if len(first_row) > 4 else ''
                foto_id = first_row[5] if len(first_row) > 5 else ''
                
                # Processa solo se utente non è vuoto e non è "utente"
                if utente and utente != 'utente':
                    if utente not in riepilogo_per_utente:
                        riepilogo_per_utente[utente] = {
                            'ip_utilizzati': set(),
                            'primo_accesso': timestamp,
                            'ultimo_accesso': timestamp,
                            'viste': {},
                            'modifiche': {},
                            'aggiunte': {},
                            'login': 0,
                            'logout': 0,
                            'altri_eventi': {}
                        }

                    r = riepilogo_per_utente[utente]
                    r['ip_utilizzati'].add(ip)
                    r['primo_accesso'] = min(r['primo_accesso'], timestamp)
                    r['ultimo_accesso'] = max(r['ultimo_accesso'], timestamp)

                    # Categorizza l'evento
                    if evento == 'visualizza' and categoria:
                        r['viste'][categoria] = r['viste'].get(categoria, 0) + 1
                    elif evento == 'modifica' and categoria:
                        r['modifiche'][categoria] = r['modifiche'].get(categoria, 0) + 1
                    elif evento == 'aggiungi' and categoria:
                        r['aggiunte'][categoria] = r['aggiunte'].get(categoria, 0) + 1
                    elif evento == 'login':
                        r['login'] += 1
                    elif evento == 'logout':
                        r['logout'] += 1
                    else:
                        # Altri eventi (elimina, copertina, ecc.)
                        evento_key = f"{evento}_{categoria}" if categoria else evento
                        r['altri_eventi'][evento_key] = r['altri_eventi'].get(evento_key, 0) + 1
        
        # Processa le righe rimanenti
        for row in reader:
            if len(row) < 4:
                continue
            timestamp, ip, utente, evento = row[:4]
            categoria = row[4] if len(row) > 4 else ''
            foto_id = row[5] if len(row) > 5 else ''

            # Processa solo se utente non è vuoto e non è "utente"
            if utente and utente != 'utente':
                if utente not in riepilogo_per_utente:
                    riepilogo_per_utente[utente] = {
                        'ip_utilizzati': set(),
                        'primo_accesso': timestamp,
                        'ultimo_accesso': timestamp,
                        'viste': {},
                        'modifiche': {},
                        'aggiunte': {},
                        'login': 0,
                        'logout': 0,
                        'altri_eventi': {}
                    }

                r = riepilogo_per_utente[utente]
                r['ip_utilizzati'].add(ip)
                r['primo_accesso'] = min(r['primo_accesso'], timestamp)
                r['ultimo_accesso'] = max(r['ultimo_accesso'], timestamp)

                # Categorizza l'evento
                if evento == 'visualizza' and categoria:
                    r['viste'][categoria] = r['viste'].get(categoria, 0) + 1
                elif evento == 'modifica' and categoria:
                    r['modifiche'][categoria] = r['modifiche'].get(categoria, 0) + 1
                elif evento == 'aggiungi' and categoria:
                    r['aggiunte'][categoria] = r['aggiunte'].get(categoria, 0) + 1
                elif evento == 'login':
                    r['login'] += 1
                elif evento == 'logout':
                    r['logout'] += 1
                else:
                    # Altri eventi (elimina, copertina, ecc.)
                    evento_key = f"{evento}_{categoria}" if categoria else evento
                    r['altri_eventi'][evento_key] = r['altri_eventi'].get(evento_key, 0) + 1

    # Prepara lista ordinata per il template
    riepiloghi = []
    for utente, dati in riepilogo_per_utente.items():
        riepiloghi.append({
            'utente': utente,
            'ip': ', '.join(sorted(dati['ip_utilizzati'])),
            'primo': dati['primo_accesso'],
            'ultimo': dati['ultimo_accesso'],
            'viste': dati['viste'],
            'modifiche': dati['modifiche'],
            'aggiunte': dati['aggiunte'],
            'login': dati['login'],
            'logout': dati['logout'],
            'altri_eventi': dati['altri_eventi']
        })

    return render_template('report_attivita.html', riepiloghi=riepiloghi, messaggio=None)

def extract_exif_date(image_path):
    """Estrae la data EXIF da un'immagine"""
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS

        img = Image.open(image_path)
        exif_data = img._getexif()

        if exif_data:
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'DateTimeOriginal':
                    # Formato EXIF: 'YYYY:MM:DD HH:MM:SS'
                    date_str = value.split()[0].replace(':', '-')
                    return date_str
    except Exception as e:
        print(f"Errore nell'estrazione EXIF: {e}")

    return None

if __name__ == '__main__':
    def avvia_flask():
        app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
    
    threading.Thread(target=avvia_flask, daemon=True).start()
    input("✅ Server avviato. Premi INVIO per chiudere...")