import pandas as pd
import pyodbc
from datetime import datetime

# Connessione al database MSSQL
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost\\SQLEXPRESS;"
    "DATABASE=galleria;"
    "Trusted_Connection=yes;"
)
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

def safe_str(val):
    return str(val) if pd.notna(val) else ""

# === Importa utenti.csv ===
df_utenti = pd.read_csv("utenti.csv", sep=";")
cursor.execute("DELETE FROM utenti")
for _, row in df_utenti.iterrows():
    cursor.execute(
        "INSERT INTO utenti (username, password, ruolo, categorie_visibili, permessi) VALUES (?, ?, ?, ?, ?)",
        safe_str(row["username"]), safe_str(row["password"]), safe_str(row["ruolo"]), "", safe_str(row["permessi"])
    )
conn.commit()
print("✅ utenti.csv importato")

# === Importa dati_foto.csv ===
df_foto = pd.read_csv("dati_foto.csv", sep=";")
cursor.execute("DELETE FROM foto")
for _, row in df_foto.iterrows():
    copertina_val = int(row["copertina"]) if pd.notna(row["copertina"]) else 0
    try:
        data_val = pd.to_datetime(row["data"], errors='coerce', dayfirst=True)
        data_sql = data_val.strftime('%Y-%m-%d') if pd.notna(data_val) else None
    except:
        data_sql = None
    cursor.execute(
        "INSERT INTO foto (titolo, descrizione, data, nome_file, categoria, copertina) VALUES (?, ?, ?, ?, ?, ?)",
        safe_str(row["titolo"]), safe_str(row["descrizione"]), data_sql, safe_str(row["nome_file"]), safe_str(row["categoria"]), copertina_val
    )
conn.commit()
print("✅ dati_foto.csv importato")

# === Importa log_attivita.csv ===
df_log = pd.read_csv("log_attivita.csv", sep=";")
cursor.execute("DELETE FROM log_attivita")
for _, row in df_log.iterrows():
    try:
        data_log = pd.to_datetime(row["timestamp"], errors='coerce', dayfirst=True)
        data_sql = data_log.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(data_log) else None
    except:
        data_sql = None
    cursor.execute(
        "INSERT INTO log_attivita (utente, azione, categoria, data, ip) VALUES (?, ?, ?, ?, ?)",
        safe_str(row["utente"]), safe_str(row["evento"]), safe_str(row["categoria"]), data_sql, safe_str(row["ip"])
    )
conn.commit()
print("✅ log_attivita.csv importato")

cursor.close()
conn.close()
print("✅ Importazione completata.")
