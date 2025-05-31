from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
import pandas as pd

# Connessione al database SQL Server (Render compatibile)
def get_connection():
    url = URL.create(
        "mssql+pytds",
        username="sa",
        password="Sanmames1",
        host="136.144.220.169",
        port=1433,
        database="galleria"
    )
    engine = create_engine(url)
    return engine.connect()

def aggiorna_csv_foto():
    conn = get_connection()
    query = text("SELECT id, titolo, descrizione, data, nome_file, categoria, '' as peso_file, copertina FROM foto")
    df = pd.read_sql(query, conn)
    df.to_csv("dati_foto.csv", sep=";", index=False, encoding="utf-8")
    conn.close()

def aggiorna_csv_utenti():
    conn = get_connection()
    query = text("SELECT username, password, ruolo, permessi FROM utenti")
    df = pd.read_sql(query, conn)
    df.to_csv("utenti.csv", sep=";", index=False, encoding="utf-8")
    conn.close()

def aggiorna_csv_log():
    conn = get_connection()
    query = text("SELECT data as timestamp, ip, utente, azione as evento, categoria, '' as foto_id FROM log_attivita")
    df = pd.read_sql(query, conn)
    df.to_csv("log_attivita.csv", sep=";", index=False, encoding="utf-8")
    conn.close()
