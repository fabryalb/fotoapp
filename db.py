import os
import pyodbc
from urllib.parse import urlparse, unquote

def get_connection():
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        # Fallback locale: se la variabile non esiste, usa localhost
        db_url = "mssql+pyodbc://sa:Password@localhost:5050/fotoapp?driver=ODBC+Driver+17+for+SQL+Server"

    # Analizza la stringa DATABASE_URL
    parsed = urlparse(db_url)
    username = parsed.username
    password = parsed.password
    host = parsed.hostname
    port = parsed.port or 1433
    database = parsed.path.lstrip('/')
    driver = parsed.query.split('=')[-1] if 'driver=' in parsed.query else 'ODBC Driver 17 for SQL Server'

    connection_string = (
        f"DRIVER={{{driver}}};"
        f"SERVER={host},{port};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={unquote(password)};"
    )

    return pyodbc.connect(connection_string)
    )
def save_utenti(lista_utenti):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM utenti")
    for u in lista_utenti:
        cursor.execute(
            "INSERT INTO utenti (username, password, ruolo, permessi) VALUES (?, ?, ?, ?)",
            u["username"], u["password"], u["ruolo"], u["permessi"]
        )
    conn.commit()
    cursor.close()
    conn.close()

def get_utenti():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, password, ruolo, permessi FROM utenti")
    utenti = []
    for row in cursor.fetchall():
        utenti.append({
            "username": row.username,
            "password": row.password,
            "ruolo": row.ruolo,
            "permessi": row.permessi
        })
    cursor.close()
    conn.close()
    return utenti

def check_login(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ruolo, permessi FROM utenti WHERE username = ? AND password = ?", (username, password))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return {"ruolo": row.ruolo, "permessi": row.permessi}
    return None

def get_foto():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, titolo, descrizione, data, nome_file, categoria, copertina FROM foto")
    foto = []
    for row in cursor.fetchall():
        foto.append({
            "id": row.id,
            "titolo": row.titolo,
            "descrizione": row.descrizione,
            "data": str(row.data),
            "nome_file": row.nome_file,
            "categoria": row.categoria,
            "copertina": row.copertina
        })
    cursor.close()
    conn.close()
    return foto

def aggiungi_foto(titolo, descrizione, data, nome_file, categoria, copertina):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO foto (titolo, descrizione, data, nome_file, categoria, copertina) VALUES (?, ?, ?, ?, ?, ?)",
        (titolo, descrizione, data, nome_file, categoria, copertina)
    )
    conn.commit()
    cursor.close()
    conn.close()

def log_attivita(ip, utente, evento, categoria='', foto_id=''):
    from datetime import datetime
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        "INSERT INTO log_attivita (data, ip, utente, azione, categoria) VALUES (?, ?, ?, ?, ?)",
        (timestamp, ip, utente, evento, categoria)
    )
    conn.commit()
    cursor.close()
    conn.close()




def save_foto_db(lista_foto):
    """Sovrascrive completamente la tabella foto con i dati aggiornati"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM foto")
    for f in lista_foto:
        cursor.execute(
            "INSERT INTO foto (id, titolo, descrizione, data, nome_file, categoria, copertina) VALUES (?, ?, ?, ?, ?, ?, ?)",
            int(f["id"]), f["titolo"], f["descrizione"], f["data"], f["nome_file"], f["categoria"],
            int(f["copertina"]) if str(f["copertina"]).lower() in ("1", "true", "si", "sì") else 0
        )
    conn.commit()
    cursor.close()
    conn.close()

def get_all_log_attivita():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT data AS timestamp, ip, utente, azione AS evento, categoria FROM log_attivita")
    risultati = []
    for row in cursor.fetchall():
        risultati.append({
            "timestamp": row.timestamp,
            "ip": row.ip,
            "utente": row.utente,
            "evento": row.evento,
            "categoria": row.category if hasattr(row, 'category') else row.categoria,
            "foto_id": ""  # opzionale
        })
    cursor.close()
    conn.close()
    return risultati

