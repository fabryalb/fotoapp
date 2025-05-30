from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort
import csv, os, json, threading, zipfile, tempfile
from PIL import Image, ExifTags
from datetime import datetime
from werkzeug.utils import secure_filename
from photo_sharing import init_sharing_routes, gestore_condivisioni
from db import check_login, get_foto, get_utenti, save_utenti, save_foto_db, log_attivita, elimina_foto_da_db, get_all_log_attivita, debug_database_schema, debug_specific_photo, normalizza_database, verifica_integrita_sistema, ripara_database_automatico # Assumi che queste funzioni esistano in db.py
from csv_sync import aggiorna_csv_foto, aggiorna_csv_utenti, aggiorna_csv_log


app = Flask(__name__)
app.secret_key = 'supersegreto'
BASE_FOLDER = os.path.join('static', 'foto')
# Rimosso: CSV_FILE = 'dati_foto.csv'
# Rimosso: USERS_FILE = 'utenti.csv'
# Rimosso: LOG_FILE = 'log_attivita.csv'

# Crea le cartelle necessarie e il file di log se non esistono
os.makedirs(BASE_FOLDER, exist_ok=True)
# if not os.path.exists(LOG_FILE): # Rimosso
#    with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f: # Rimosso
#        writer = csv.writer(f, delimiter=';') # Rimosso
#        writer.writerow(['timestamp', 'ip', 'utente', 'evento', 'categoria', 'foto_id']) # Rimosso


# Adapter per il foto_manager
class FotoManagerAdapter:
    def ottieni_foto_per_id(self, foto_id):
        tutte = get_foto()
        return next((f for f in tutte if f['id'] == str(foto_id)), None)

    def serve_foto(self, foto_id):
        foto = self.ottieni_foto_per_id(foto_id)
        if foto:
            return send_file(os.path.join('static', foto['nome_file']))
        abort(404)

foto_manager = FotoManagerAdapter()
init_sharing_routes(app, foto_manager)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def carica_utenti():
    """Carica gli utenti dal database tramite db.py"""
    return get_utenti() # Sostituito con la chiamata al database

def salva_foto(foto_list):
    """Salva l'elenco di foto nel database tramite db.py"""
    save_foto_db(foto_list) # Sostituito con la chiamata al database

def log_evento(ip, utente, evento, categoria='', foto_id=''):
    log_attivita(ip, utente, evento, categoria, foto_id) # Sostituito con la chiamata al database


def genera_nuovo_id():
    """Genera un nuovo ID unico per una foto"""
    foto = get_foto()
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

# from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file # Rimosso duplicato
# import csv, os, json, threading, zipfile, tempfile # Rimosso duplicato
# from PIL import Image, ExifTags # Rimosso duplicato
# from datetime import datetime # Rimosso duplicato
# from werkzeug.utils import secure_filename # Rimosso duplicato
# from photo_sharing import init_sharing_routes, gestore_condivisioni # Rimosso duplicato



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
def copertina_bool(val):
    """Interpreta il campo copertina da DB come booleano"""
    return val if isinstance(val, bool) else str(val).strip().lower() in ('1', 'si', 'sì', 'true')

@app.route('/')
def index():
    tutte = get_foto()
    
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
        categorie_old[cat].sort(key=lambda f: '0' if copertina_bool(f.get('copertina')) else '1')

    for cat_princ in categorie_principali.values():
        for subcat in cat_princ['sottocategorie'].values():
            subcat['foto'].sort(key=lambda f: '0' if copertina_bool(f.get('copertina')) else '1')

    
    return render_template('index.html', categorie=categorie_old, categorie_principali=categorie_principali)

@app.route('/categoria/<path:nome>')
def mostra_categoria(nome):
    if session.get('username') and not utente_ha_permesso(nome, 'visualizza'):
        flash("Non hai i permessi per visualizzare questa categoria")
        return redirect(url_for('index'))
    
    sort_by = request.args.get('sort', 'default')
    tutte = get_foto()
    
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
    
    prefisso_slash = nome + "/"
    prefisso_maggiore = nome + ">"
    
    categorie_trovate = set()
    for f in tutte:
        cat = f['categoria']
        if cat.startswith(prefisso_slash) or cat.startswith(prefisso_maggiore):
            categorie_trovate.add(cat)
    
    for categoria_completa in sorted(categorie_trovate):
        if '/' in categoria_completa:
            nome_breve = categoria_completa.split('/', 1)[1].strip()
        elif '>' in categoria_completa:
            nome_breve = categoria_completa.split('>', 1)[1].strip()
        else:
            continue
        
        foto_sottocategoria = [f for f in tutte if f['categoria'] == categoria_completa]
        num_foto = len(foto_sottocategoria)
        
        foto_copertina = None
        for f in foto_sottocategoria:
            val = f.get('copertina', '')
            is_copertina = val if isinstance(val, bool) else str(val).strip().lower() in ('1', 'si', 'sì', 'true')
            if is_copertina:
                foto_copertina = f
                break
        
        if not foto_copertina and foto_sottocategoria:
            foto_copertina = foto_sottocategoria[0]
        
        if num_foto > 0 and (not session.get('username') or utente_ha_permesso(categoria_completa, 'visualizza')):
            sottocategorie.append({
                'categoria_completa': categoria_completa,
                'nome_breve': nome_breve,
                'num_foto': num_foto,
                'foto_copertina': foto_copertina
            })

    # ✅ FINALE CORRETTO
    return render_template('categoria.html', 
        nome=nome, 
        foto=foto_template, 
        sort_by=sort_by,
        sottocategorie=sottocategorie,
        utente_ha_permesso=utente_ha_permesso  # <-- NECESSARIO per Jinja2
    )


@app.route('/modifica/<id_foto>', methods=['GET', 'POST'])
def modifica(id_foto):
    if not session.get('username'):
        flash("Devi effettuare il login per modificare le foto")
        return redirect(url_for('login'))
    
    tutte = get_foto()
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
            aggiorna_csv_foto() # Mantenuto salva_foto che ora punta a save_foto_db
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
    
    tutte = get_foto()
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
                print("📋 ID esistenti:", [f['id'] for f in tutte])  # DEBUG
                nuovo_id = max([int(f['id']) for f in tutte if str(f['id']).isdigit()] + [0]) + 1
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
                relative_path = f"foto/{categoria.lower()}/{filename}"
                
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
        aggiorna_csv_foto() # Mantenuto salva_foto che ora punta a save_foto_db
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

    tutte = get_foto()
    categorie = sorted(set(f['categoria'] for f in tutte))

    if request.method == 'POST':
        categoria = request.form.get('categoria')
        titolo = request.form.get('titolo', '').strip()
        descrizione = request.form.get('descrizione', '').strip()
        data = request.form.get('data') or datetime.today().strftime('%Y-%m-%d')
        files = request.files.getlist('file[]')

        for file in files:
            if file and file.filename:
                nuovo_id = max([int(f['id']) for f in tutte if str(f['id']).isdigit()] + [0]) + 1
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
                relative_path = f"foto/{categoria.lower()}/{filename}"

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
        aggiorna_csv_foto() # Mantenuto salva_foto che ora punta a save_foto_db
        flash("Caricamento massivo completato con successo")
        return redirect(url_for('index'))

    oggi = datetime.today().strftime('%Y-%m-%d')
    return render_template('upload_massivo.html', categorie=categorie, oggi=oggi)

@app.route('/elimina/<id_foto>')
def elimina(id_foto):
    if not session.get('username'):
        flash("Devi effettuare il login per eliminare le foto")
        return redirect(url_for('login'))
    
    print(f"🎯 Richiesta eliminazione per ID: '{id_foto}' (tipo: {type(id_foto)})")
    
    tutte = get_foto()  # Questa riga dovrebbe funzionare se l'import è corretto
    print(f"📋 ID disponibili nel DB: {[f['id'] for f in tutte[:5]]}...")
    
    # Cerca la foto con gestione robusta dell'ID
    foto = None
    for f in tutte:
        if str(f['id']) == str(id_foto):
            foto = f
            break
    
    if not foto:
        print(f"❌ Foto con ID '{id_foto}' non trovata")
        flash("Foto non trovata")
        return redirect(url_for('index'))
    
    print(f"✅ Foto trovata: {foto['titolo']} (categoria: {foto['categoria']})")
    
    if not utente_ha_permesso(foto['categoria'], 'elimina'):
        flash("Non hai i permessi per eliminare questa foto")
        return redirect(url_for('mostra_categoria', nome=foto['categoria']))
    
    # Costruisci il percorso del file con gestione case-insensitive
    nome_file_originale = foto['nome_file']
    path_completo = os.path.join('static', nome_file_originale)
    
    print(f"📁 Percorso file originale: {path_completo}")
    print(f"📁 File esiste (case-sensitive): {os.path.exists(path_completo)}")
    
    # Se il file non esiste con il case originale, prova a cercarlo
    if not os.path.exists(path_completo):
        print("🔍 File non trovato, ricerca case-insensitive...")
        
        dir_path = os.path.dirname(path_completo)
        nome_file = os.path.basename(nome_file_originale)
        
        print(f"📁 Directory: {dir_path}")
        print(f"📄 Nome file cercato: {nome_file}")
        
        if os.path.exists(dir_path):
            files_in_dir = os.listdir(dir_path)
            print(f"📋 File nella directory: {files_in_dir}")
            
            for file_esistente in files_in_dir:
                if file_esistente.lower() == nome_file.lower():
                    path_completo = os.path.join(dir_path, file_esistente)
                    print(f"✅ File trovato con case diverso: {path_completo}")
                    break
    
    # Elimina il file fisico se esiste
    if os.path.exists(path_completo):
        try:
            os.remove(path_completo)
            print("🗑️ File fisico eliminato con successo")
        except Exception as e:
            print(f"❌ Errore eliminazione file fisico: {e}")
            flash(f"Errore nell'eliminazione del file: {e}")
    else:
        print("⚠️ File fisico non trovato, continuo con eliminazione dal DB")
    
    # Elimina dal database
    print(f"📣 Chiamata eliminazione DB per ID '{id_foto}'")
    
    # NON mettere import qui! La funzione deve essere già importata all'inizio del file
    risultato = elimina_foto_da_db(id_foto)
    
    if risultato:
        print("✅ Eliminazione dal DB riuscita")
        try:
            aggiorna_csv_foto()
            print("📝 CSV aggiornato dopo eliminazione")
        except Exception as e:
            print(f"⚠️ Errore aggiornamento CSV: {e}")
        
        log_evento(request.remote_addr, session['username'], 'elimina', foto['categoria'], id_foto)
        flash("Foto eliminata con successo")
    else:
        print("❌ Eliminazione dal DB fallita")
        flash("Errore nell'eliminazione della foto dal database")
    
    return redirect(url_for('mostra_categoria', nome=foto['categoria']))

@app.route('/elimina_categoria/<nome>')
def elimina_categoria(nome):
    if not session.get('username'):
        flash("Devi effettuare il login per eliminare categorie")
        return redirect(url_for('login'))
    
    if not utente_ha_permesso(nome, 'elimina'):
        flash("Non hai i permessi per eliminare questa categoria")
        return redirect(url_for('index'))
    
    tutte = get_foto()
    nuove = [f for f in tutte if f['categoria'] != nome]
    
    cartella = os.path.join(BASE_FOLDER, nome)
    if os.path.exists(cartella):
        import shutil
        shutil.rmtree(cartella)
    
    salva_foto(nuove) # Mantenuto salva_foto che ora punta a save_foto_db
    
    log_evento(request.remote_addr, session['username'], 'elimina_categoria', nome)
    flash("Categoria eliminata con successo")
    return redirect(url_for('index'))

@app.route('/copertina/<id_foto>')
def imposta_copertina(id_foto):
    if not session.get('username'):
        flash("Devi effettuare il login per impostare la copertina")
        return redirect(url_for('login'))
    
    tutte = get_foto()
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
    aggiorna_csv_foto() # Mantenuto salva_foto che ora punta a save_foto_db
    
    log_evento(request.remote_addr, session['username'], 'imposta_copertina', categoria, id_foto)
    flash("Copertina impostata correttamente")
    return redirect(url_for('mostra_categoria', nome=categoria))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        
        dati_utente = check_login(username, password)
        if dati_utente:
            session["username"] = username
            session["ruolo"] = dati_utente["ruolo"]
            session["permessi"] = json.loads(dati_utente["permessi"]) if isinstance(dati_utente["permessi"], str) and dati_utente["permessi"].startswith("{") else dati_utente["permessi"]
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
    utenti = carica_utenti() # Mantenuto carica_utenti che ora punta a get_utenti
    
    # Carica tutte le categorie esistenti dalle foto
    tutte_le_foto = get_foto()
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
                        import ast # Aggiunto import per ast.literal_eval
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
    
    utenti = carica_utenti() # Mantenuto carica_utenti che ora punta a get_utenti
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
    save_utenti(normalizza_formato_permessi(utenti)) 
    aggiorna_csv_utenti() # Sostituito con la chiamata al database
    
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
    utenti = carica_utenti() # Mantenuto carica_utenti che ora punta a get_utenti
    
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
    
    save_utenti(normalizza_formato_permessi(utenti)) 
    aggiorna_csv_utenti() # Sostituito con la chiamata al database
    
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
    utenti = carica_utenti() # Mantenuto carica_utenti che ora punta a get_utenti
    
    # Filtra l'utente da eliminare
    utenti_aggiornati = [u for u in utenti if u['username'] != username]
    
    # Verifica che l'utente esistesse
    if len(utenti) == len(utenti_aggiornati):
        flash("Utente non trovato")
        return redirect(url_for('gestione_utenti'))
    
    # Salva gli utenti aggiornati
    save_utenti(normalizza_formato_permessi(utenti_aggiornati)) 
    aggiorna_csv_utenti() # Sostituito con la chiamata al database
    
    flash(f"Utente '{username}' eliminato con successo")
    return redirect(url_for('gestione_utenti'))

@app.route('/crea_utenti_iniziali')
def crea_utenti_iniziali():
    """Funzione di utilità per creare gli utenti iniziali nel database"""
    # Se il database utente è già popolato, potresti voler aggiungere un controllo qui
    # In questo esempio, lo lascio come utility per inizializzare il DB.
    
    utenti = [
        {'username': 'admin', 'password': 'admin', 'ruolo': 'admin', 'permessi': 'ALL'},
        {'username': 'utente', 'password': 'utente', 'ruolo': 'utente', 'permessi': json.dumps({
            'generale': ['visualizza', 'aggiungi', 'modifica'],
            'vacanze': ['visualizza']
        })}
    ]
    
    save_utenti(normalizza_formato_permessi(utenti)) 
    aggiorna_csv_utenti() # Sostituito con la chiamata al database
    
    flash("Utenti iniziali creati con successo")
    return redirect(url_for('index'))

@app.route('/condividi/<id_foto>')
def condividi(id_foto):
    tutte = get_foto()
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
    tutte = get_foto()
    foto = next((f for f in tutte if f['id'] == id_foto), None)
    if not foto:
        return "Foto non trovata", 404
    return render_template('condividi_foto.html', foto=foto)

@app.route('/download_image/<id_foto>')
def download_image(id_foto):
    """Fornisce l'immagine come allegato scaricabile con un nome file appropriato"""
    tutte = get_foto()
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
    tutte = get_foto()
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
    tutte = get_foto()
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
    tutte = get_foto()
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
    tutte = get_foto()
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
        tutte = get_foto()
        categorie = sorted(set(f['categoria'] for f in tutte))
        return render_template('ricerca.html', risultati=None, categorie=categorie)

    tutte = get_foto()
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

from flask import jsonify # Aggiunto per search_suggestions
@app.route('/api/search_suggestions', methods=['GET'])
def search_suggestions():
    """API per fornire suggerimenti di auto-completamento per la ricerca"""
    query = request.args.get('q', '').strip().lower()

    if not query or len(query) < 2:
        return jsonify([])

    tutte = get_foto()
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

    tutte = get_foto()
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

    # log_path = 'log_attivita.csv' # Rimosso
    # if not os.path.exists(log_path): # Rimosso
    #    return render_template('report_attivita.html', riepiloghi=[], messaggio="Nessuna attività registrata.") # Rimosso

    riepilogo_per_utente = {}
    
    # Ottieni i dati di log dal database
    
    log_data = get_all_log_attivita() # Assumi che log_attivita possa restituire tutti i log se richiamata con un flag
    
    if not log_data:
        return render_template('report_attivita.html', riepiloghi=[], messaggio="Nessuna attività registrata.")

    for row in log_data:
        # Assumiamo che le righe dal DB siano già in un formato processabile, e che log_attivita li restituisca come liste o dizionari
        # Se log_attivita restituisce i dati già come dizionari, questa parte andrà adattata
        if isinstance(row, dict):
            timestamp = row.get('timestamp')
            ip = row.get('ip')
            utente = row.get('utente')
            evento = row.get('evento')
            categoria = row.get('categoria', '')
            foto_id = row.get('foto_id', '')
        else: # Se restituisce liste (come un reader di csv)
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
@app.route('/admin')
def admin_panel():
    """Redirect al pannello admin principale"""
    if not session.get('username') or session.get('ruolo') != 'admin':
        flash("Solo l'amministratore può accedere al pannello admin")
        return redirect(url_for('index'))
    
    return redirect(url_for('admin_manutenzione'))

# Opzionale: route per accesso diretto alle funzioni più usate
@app.route('/admin/debug')
def admin_debug_quick():
    """Accesso rapido al debug database"""
    if not session.get('username') or session.get('ruolo') != 'admin':
        flash("Solo l'amministratore può accedere al debug")
        return redirect(url_for('index'))
    
    return redirect(url_for('debug_database'))

@app.route('/admin/repair')
def admin_repair_quick():
    """Accesso rapido alla riparazione automatica"""
    if not session.get('username') or session.get('ruolo') != 'admin':
        flash("Solo l'amministratore può eseguire riparazioni")
        return redirect(url_for('index'))
    
    return redirect(url_for('admin_ripara_automatico'))
@app.route('/debug/database')
def debug_database():
    if not session.get('username') or session.get('ruolo') != 'admin':
        flash("Solo l'amministratore può accedere al debug")
        return redirect(url_for('index'))
    
    
    debug_database_schema()
    
    flash("Controlla i log del server per le informazioni di debug")
    return redirect(url_for('index'))

@app.route('/debug/photo/<photo_id>')
def debug_photo(photo_id):
    if not session.get('username') or session.get('ruolo') != 'admin':
        flash("Solo l'amministratore può accedere al debug")
        return redirect(url_for('index'))
    
    
    debug_specific_photo(photo_id)
    
    flash(f"Controlla i log del server per il debug della foto {photo_id}")
    return redirect(url_for('index'))

# Aggiungi queste route al tuo app.py (prima del if __name__ == '__main__':)

@app.route('/admin/manutenzione')
def admin_manutenzione():
    """Pannello di manutenzione per l'amministratore"""
    if not session.get('username') or session.get('ruolo') != 'admin':
        flash("Solo l'amministratore può accedere alla manutenzione")
        return redirect(url_for('index'))
    
    return render_template('admin_manutenzione.html')

@app.route('/admin/normalizza_database')
def admin_normalizza_database():
    """Normalizza il database esistente"""
    if not session.get('username') or session.get('ruolo') != 'admin':
        flash("Solo l'amministratore può eseguire la normalizzazione")
        return redirect(url_for('index'))
    
    try:
        
        risultato = normalizza_database()
        
        flash(f"Normalizzazione completata! Risolti: {risultato['risolti']} problemi, "
              f"File non trovati: {len(risultato['non_trovati'])}")
        
        if risultato['non_trovati']:
            # Salva i dettagli in sessione per mostrarli
            session['file_non_trovati'] = risultato['non_trovati']
            
    except Exception as e:
        flash(f"Errore durante la normalizzazione: {e}")
        print(f"❌ Errore normalizzazione: {e}")
    
    return redirect(url_for('admin_manutenzione'))

@app.route('/admin/verifica_integrita')
def admin_verifica_integrita():
    """Verifica l'integrità del sistema"""
    if not session.get('username') or session.get('ruolo') != 'admin':
        flash("Solo l'amministratore può verificare l'integrità")
        return redirect(url_for('index'))
    
    try:
        
        risultato = verifica_integrita_sistema()
        
        flash(f"Verifica completata! DB: {risultato['file_db']} file, "
              f"Fisici: {risultato['file_fisici']} file, "
              f"Mancanti: {len(risultato['mancanti'])}, "
              f"Orfani: {len(risultato['orfani'])}")
        
        # Salva risultati in sessione
        session['verifica_risultati'] = {
            'mancanti': risultato['mancanti'][:20],  # Max 20 per sessione
            'orfani': risultato['orfani'][:20]
        }
        
    except Exception as e:
        flash(f"Errore durante la verifica: {e}")
        print(f"❌ Errore verifica: {e}")
    
    return redirect(url_for('admin_manutenzione'))

@app.route('/admin/ripara_automatico')
def admin_ripara_automatico():
    """Riparazione automatica completa"""
    if not session.get('username') or session.get('ruolo') != 'admin':
        flash("Solo l'amministratore può eseguire la riparazione")
        return redirect(url_for('index'))
    
    try:
        
        risultato = ripara_database_automatico()
        
        norm = risultato['normalizzazione']
        verif = risultato['verifica']
        
        flash(f"Riparazione completata! "
              f"Normalizzati: {norm['risolti']} file, "
              f"Mancanti: {len(verif['mancanti'])}, "
              f"Orfani: {len(verif['orfani'])}")
        
    except Exception as e:
        flash(f"Errore durante la riparazione: {e}")
        print(f"❌ Errore riparazione: {e}")
    
    return redirect(url_for('admin_manutenzione'))

@app.route('/admin/pulisci_record_orfani')
def admin_pulisci_record_orfani():
    """Rimuove i record del database per file che non esistono più"""
    if not session.get('username') or session.get('ruolo') != 'admin':
        flash("Solo l'amministratore può pulire i record orfani")
        return redirect(url_for('index'))
    
    try:
        
        risultato = verifica_integrita_sistema()
        
        file_mancanti = risultato['mancanti']
        
        if not file_mancanti:
            flash("Nessun record orfano trovato!")
            return redirect(url_for('admin_manutenzione'))
        
        # Elimina i record per file mancanti
        tutte_foto = get_foto()
        foto_da_mantenere = []
        eliminati = 0
        
        for foto in tutte_foto:
            path_completo = os.path.join('static', foto['nome_file'])
            if path_completo not in file_mancanti:
                foto_da_mantenere.append(foto)
            else:
                eliminati += 1
                print(f"🗑️ Eliminato record orfano: ID {foto['id']} - {foto['titolo']}")
        
        # Risalva solo le foto con file esistenti
        save_foto_db(foto_da_mantenere)
        try:
            aggiorna_csv_foto()
        except:
            pass  # Ignora errori CSV
        
        flash(f"Puliti {eliminati} record orfani dal database!")
        
    except Exception as e:
        flash(f"Errore durante la pulizia: {e}")
        print(f"❌ Errore pulizia: {e}")
    
    return redirect(url_for('admin_manutenzione'))

if __name__ == '__main__':
    if os.environ.get("RENDER") == "TRUE":
        # Porta fissa per Render
        app.run(host='0.0.0.0', port=5050)
    else:
        import threading
        def avvia_flask():
            app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)

        threading.Thread(target=avvia_flask, daemon=True).start()
        try:
            input("✅ Server avviato. Premi INVIO per chiudere...")
        except EOFError:
            pass

