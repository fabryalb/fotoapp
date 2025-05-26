import pyodbc
import pandas as pd

# Connessione al database
def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost\\SQLEXPRESS;"
        "DATABASE=galleria;"
        "Trusted_Connection=yes;"
    )

def aggiorna_csv_foto():
    conn = get_connection()
    query = "SELECT id, titolo, descrizione, data, nome_file, categoria, '' as peso_file, copertina FROM foto"
    df = pd.read_sql(query, conn)
    df.to_csv("dati_foto.csv", sep=";", index=False, encoding="utf-8")
    conn.close()

def aggiorna_csv_utenti():
    conn = get_connection()
    query = "SELECT username, password, ruolo, permessi FROM utenti"
    df = pd.read_sql(query, conn)
    df.to_csv("utenti.csv", sep=";", index=False, encoding="utf-8")
    conn.close()

def aggiorna_csv_log():
    conn = get_connection()
    query = "SELECT data as timestamp, ip, utente, azione as evento, categoria, '' as foto_id FROM log_attivita"
    df = pd.read_sql(query, conn)
    df.to_csv("log_attivita.csv", sep=";", index=False, encoding="utf-8")
    conn.close()
