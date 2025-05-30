import pyodbc
from datetime import datetime
import os

def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost\\SQLEXPRESS;"
        "DATABASE=galleria;"
        "Trusted_Connection=yes;"
    )

def save_utenti(lista_utenti):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM utenti")
            for u in lista_utenti:
                cursor.execute(
                    "INSERT INTO utenti (username, password, ruolo, permessi) VALUES (?, ?, ?, ?)",
                    u["username"], u["password"], u["ruolo"], u["permessi"]
                )
            conn.commit()

def get_utenti():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT username, password, ruolo, permessi FROM utenti")
            return [{
                "username": row.username,
                "password": row.password,
                "ruolo": row.ruolo,
                "permessi": row.permessi
            } for row in cursor.fetchall()]

def check_login(username, password):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT ruolo, permessi FROM utenti WHERE username = ? AND password = ?", (username, password))
            row = cursor.fetchone()
            return {"ruolo": row.ruolo, "permessi": row.permessi} if row else None

def get_foto():
    """Versione migliorata che normalizza gli ID"""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, titolo, descrizione, data, nome_file, categoria, copertina FROM foto")
            return [{
                "id": str(row.id),  # Forza sempre stringa per coerenza
                "titolo": row.titolo,
                "descrizione": row.descrizione,
                "data": str(row.data),
                "nome_file": row.nome_file,
                "categoria": row.categoria,
                "copertina": row.copertina
            } for row in cursor.fetchall()]

def aggiungi_foto(titolo, descrizione, data, nome_file, categoria, copertina):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO foto (titolo, descrizione, data, nome_file, categoria, copertina) VALUES (?, ?, ?, ?, ?, ?)",
                (titolo, descrizione, data, nome_file, categoria, copertina)
            )
            conn.commit()

def log_attivita(ip, utente, evento, categoria='', foto_id=''):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO log_attivita (data, ip, utente, azione, categoria) VALUES (?, ?, ?, ?, ?)",
                (timestamp, ip, utente, evento, categoria)
            )
            conn.commit()

def save_foto_db(lista_foto):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM foto")
            for f in lista_foto:
                try:
                    data_db = datetime.strptime(f["data"], "%d/%m/%Y").strftime("%Y-%m-%d")
                except Exception:
                    try:
                        # Prova anche formato YYYY-MM-DD
                        data_db = datetime.strptime(f["data"], "%Y-%m-%d").strftime("%Y-%m-%d")
                    except Exception:
                        data_db = None
                cursor.execute(
                    "INSERT INTO foto (titolo, descrizione, data, nome_file, categoria, copertina) VALUES (?, ?, ?, ?, ?, ?)",
                    f["titolo"],
                    f["descrizione"],
                    data_db,
                    f["nome_file"],
                    f["categoria"],
                    int(f["copertina"]) if str(f["copertina"]).lower() in ("1", "true", "si", "sì") else 0
                )
            conn.commit()

def get_all_log_attivita():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT data AS timestamp, ip, utente, azione AS evento, categoria FROM log_attivita")
            return [{
                "timestamp": row.timestamp,
                "ip": row.ip,
                "utente": row.utente,
                "evento": row.evento,
                "categoria": row.categoria,
                "foto_id": ""
            } for row in cursor.fetchall()]

def elimina_foto_da_db(foto_id):
    """Elimina una foto dal database con gestione robusta degli ID"""
    print(f"🗑️ Tentativo eliminazione ID: {foto_id} (tipo: {type(foto_id)})")
    
    # Converte l'ID in modo sicuro
    try:
        if isinstance(foto_id, str):
            foto_id_int = int(foto_id)
        else:
            foto_id_int = foto_id
    except (ValueError, TypeError) as e:
        print(f"❌ Errore conversione ID '{foto_id}': {e}")
        return False
    
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Prima verifica se l'ID esiste
            cursor.execute("SELECT id, titolo, nome_file FROM foto WHERE id = ?", (foto_id_int,))
            foto_esistente = cursor.fetchone()
            
            if not foto_esistente:
                print(f"❌ Nessuna foto trovata con ID {foto_id_int}")
                # Prova anche con l'ID come stringa (nel caso la colonna sia VARCHAR)
                cursor.execute("SELECT id, titolo, nome_file FROM foto WHERE id = ?", (str(foto_id),))
                foto_esistente = cursor.fetchone()
                
                if not foto_esistente:
                    print(f"❌ Nessuna foto trovata neanche con ID stringa '{foto_id}'")
                    return False
                else:
                    print(f"✅ Foto trovata con ID stringa: {foto_esistente.titolo}")
                    # Usa l'ID stringa per l'eliminazione
                    cursor.execute("DELETE FROM foto WHERE id = ?", (str(foto_id),))
            else:
                print(f"✅ Foto trovata con ID numerico: {foto_esistente.titolo}")
                # Usa l'ID numerico per l'eliminazione
                cursor.execute("DELETE FROM foto WHERE id = ?", (foto_id_int,))
            
            # Commit delle modifiche
            rows_affected = cursor.rowcount
            conn.commit()
            
            print(f"✅ Righe eliminate: {rows_affected}")
            
            # Verifica finale
            cursor.execute("SELECT COUNT(*) FROM foto WHERE id = ? OR id = ?", (foto_id_int, str(foto_id)))
            rimanenti = cursor.fetchone()[0]
            print(f"✅ Controllo post-eliminazione: {rimanenti} righe trovate con ID {foto_id}")
            
            return rows_affected > 0

# === FUNZIONI DEBUG ===
def debug_database_schema():
    """Mostra la struttura della tabella foto (SQL Server)"""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Verifica esistenza tabella
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'foto'
            """)
            table_exists = cursor.fetchone()[0] > 0
            
            if table_exists:
                print("✅ Tabella 'foto' esiste")
                
                # Ottieni schema della tabella (SQL Server)
                cursor.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'foto'
                    ORDER BY ORDINAL_POSITION
                """)
                columns = cursor.fetchall()
                
                print("📋 Schema tabella 'foto':")
                for col in columns:
                    print(f"  - {col[0]} ({col[1]}) - Nullable: {col[2]} - Default: {col[3]}")
                
                # Conta record
                cursor.execute("SELECT COUNT(*) FROM foto")
                count = cursor.fetchone()[0]
                print(f"📊 Numero totale di foto: {count}")
                
                # Mostra alcuni esempi di ID
                cursor.execute("SELECT TOP 5 id, titolo FROM foto")
                examples = cursor.fetchall()
                print("📋 Esempi di ID nel database:")
                for ex in examples:
                    print(f"  - ID: '{ex[0]}' (tipo: {type(ex[0])}) - Titolo: {ex[1]}")
            else:
                print("❌ Tabella 'foto' non trovata!")

def debug_specific_photo(photo_id):
    """Debug di una foto specifica"""
    print(f"🔍 Debug foto con ID: '{photo_id}'")
    
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Prova con ID come intero
            try:
                id_int = int(photo_id)
                cursor.execute("SELECT * FROM foto WHERE id = ?", (id_int,))
                result_int = cursor.fetchone()
                print(f"📋 Ricerca con ID intero {id_int}: {'Trovata' if result_int else 'Non trovata'}")
                if result_int:
                    print(f"  - Dati: ID={result_int[0]}, Titolo={result_int[1]}")
            except ValueError:
                print(f"❌ Non posso convertire '{photo_id}' in intero")
            
            # Prova con ID come stringa
            cursor.execute("SELECT * FROM foto WHERE id = ?", (str(photo_id),))
            result_str = cursor.fetchone()
            print(f"📋 Ricerca con ID stringa '{photo_id}': {'Trovata' if result_str else 'Non trovata'}")
            if result_str:
                print(f"  - Dati: ID={result_str[0]}, Titolo={result_str[1]}")
            
            # Ricerca simile (LIKE)
            cursor.execute("SELECT id, titolo FROM foto WHERE CAST(id AS VARCHAR) LIKE ?", (f"%{photo_id}%",))
            similar = cursor.fetchall()
            if similar:
                print(f"📋 ID simili trovati:")
                for s in similar:
                    print(f"  - '{s[0]}' - {s[1]}")

# === FUNZIONI MANUTENZIONE ===
def trova_file_case_insensitive(nome_file_relativo):
    """
    Trova un file ignorando maiuscole/minuscole
    Restituisce il percorso completo se trovato, None altrimenti
    """
    # Percorso completo originale
    path_completo = os.path.join('static', nome_file_relativo)
    
    if os.path.exists(path_completo):
        return path_completo
    
    # Estrai directory e nome file
    dir_relativa = os.path.dirname(nome_file_relativo)
    nome_file = os.path.basename(nome_file_relativo)
    
    # Directory completa
    dir_completa = os.path.join('static', dir_relativa) if dir_relativa else 'static'
    
    if not os.path.exists(dir_completa):
        return None
    
    # Cerca ricorsivamente
    for root, dirs, files in os.walk(dir_completa):
        for file_esistente in files:
            if file_esistente.lower() == nome_file.lower():
                # Trovato! Costruisci il percorso completo
                path_trovato = os.path.join(root, file_esistente)
                return path_trovato
    
    return None

def normalizza_database():
    """
    Normalizza il database esistente per risolvere inconsistenze:
    1. Converte tutti gli ID in formato coerente
    2. Verifica e corregge i percorsi dei file
    3. Aggiorna i nomi file con case corretto
    """
    print("🔧 Inizio normalizzazione database...")
    
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # 1. Ottieni tutte le foto
            cursor.execute("SELECT id, titolo, nome_file FROM foto")
            tutte_foto = cursor.fetchall()
            
            print(f"📋 Trovate {len(tutte_foto)} foto da verificare")
            
            problemi_risolti = 0
            file_non_trovati = []
            
            for foto in tutte_foto:
                foto_id = foto[0]
                titolo = foto[1] 
                nome_file = foto[2]
                
                # 2. Verifica se il file fisico esiste
                path_originale = os.path.join('static', nome_file)
                file_esiste = os.path.exists(path_originale)
                
                print(f"🔍 ID {foto_id}: {titolo}")
                print(f"   File: {nome_file}")
                print(f"   Esiste: {file_esiste}")
                
                if not file_esiste:
                    # 3. Prova ricerca case-insensitive
                    nuovo_path = trova_file_case_insensitive(nome_file)
                    
                    if nuovo_path:
                        # Aggiorna il database con il percorso corretto
                        nuovo_nome_relativo = os.path.relpath(nuovo_path, 'static')
                        cursor.execute(
                            "UPDATE foto SET nome_file = ? WHERE id = ?", 
                            (nuovo_nome_relativo, foto_id)
                        )
                        print(f"   ✅ Corretto: {nome_file} → {nuovo_nome_relativo}")
                        problemi_risolti += 1
                    else:
                        file_non_trovati.append({
                            'id': foto_id,
                            'titolo': titolo,
                            'nome_file': nome_file
                        })
                        print(f"   ❌ File non trovato: {nome_file}")
            
            # 4. Commit delle correzioni
            conn.commit()
            
            print(f"\n📊 RISULTATI NORMALIZZAZIONE:")
            print(f"✅ Problemi risolti: {problemi_risolti}")
            print(f"❌ File non trovati: {len(file_non_trovati)}")
            
            if file_non_trovati:
                print(f"\n🚨 FILE MANCANTI:")
                for f in file_non_trovati:
                    print(f"   ID {f['id']}: {f['titolo']} → {f['nome_file']}")
            
            return {
                'risolti': problemi_risolti,
                'non_trovati': file_non_trovati
            }

def verifica_integrita_sistema():
    """
    Verifica l'integrità di tutto il sistema:
    1. Coerenza DB ↔ File fisici
    2. Duplicati
    3. File orfani
    """
    print("🔍 Verifica integrità sistema...")
    
    # 1. File nel database
    tutte_foto_db = get_foto()
    file_db = set()
    
    for foto in tutte_foto_db:
        path_completo = os.path.join('static', foto['nome_file'])
        file_db.add(path_completo)
    
    print(f"📋 File nel database: {len(file_db)}")
    
    # 2. File fisici esistenti
    file_fisici = set()
    
    for root, dirs, files in os.walk('static/foto'):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                file_fisici.add(os.path.join(root, file))
    
    print(f"📁 File fisici trovati: {len(file_fisici)}")
    
    # 3. Trova discrepanze
    file_db_mancanti = file_db - file_fisici
    file_orfani = file_fisici - file_db
    
    print(f"\n📊 RISULTATI VERIFICA:")
    print(f"❌ File nel DB ma mancanti fisicamente: {len(file_db_mancanti)}")
    print(f"🔄 File fisici non nel DB (orfani): {len(file_orfani)}")
    
    if file_db_mancanti:
        print(f"\n🚨 FILE MANCANTI:")
        for f in list(file_db_mancanti)[:10]:  # Max 10
            print(f"   {f}")
        if len(file_db_mancanti) > 10:
            print(f"   ... e altri {len(file_db_mancanti) - 10}")
    
    if file_orfani:
        print(f"\n📂 FILE ORFANI:")
        for f in list(file_orfani)[:10]:  # Max 10  
            print(f"   {f}")
        if len(file_orfani) > 10:
            print(f"   ... e altri {len(file_orfani) - 10}")
    
    return {
        'file_db': len(file_db),
        'file_fisici': len(file_fisici),
        'mancanti': list(file_db_mancanti),
        'orfani': list(file_orfani)
    }

def ripara_database_automatico():
    """
    Riparazione automatica del database:
    1. Normalizza percorsi
    2. Rimuove riferimenti a file inesistenti  
    3. Aggiorna CSV
    """
    print("🔧 Inizio riparazione automatica...")
    
    # 1. Normalizza
    risultato_norm = normalizza_database()
    
    # 2. Verifica integrità
    risultato_verifica = verifica_integrita_sistema()
    
    # 3. Rimuovi record con file mancanti (opzionale)
    if risultato_verifica['mancanti']:
        print(f"\n❓ Trovati {len(risultato_verifica['mancanti'])} record con file mancanti")
        print("   Usa pulisci_record_orfani() per rimuoverli se necessario")
    
    # 4. Aggiorna CSV se disponibile
    try:
        from csv_sync import aggiorna_csv_foto
        aggiorna_csv_foto()
        print("📝 CSV aggiornato")
    except ImportError:
        print("⚠️ Modulo csv_sync non disponibile")
    
    print("✅ Riparazione completata!")
    
    return {
        'normalizzazione': risultato_norm,
        'verifica': risultato_verifica
    }