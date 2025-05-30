import csv
from db import get_utenti, get_foto

def esporta_utenti_csv():
    utenti = get_utenti()
    with open('utenti.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['username', 'password', 'ruolo', 'permessi'])
        for u in utenti:
            writer.writerow([u['username'], u['password'], u['ruolo'], u['permessi']])

def esporta_foto_csv():
    foto = get_foto()
    with open('dati_foto.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['id', 'titolo', 'descrizione', 'data', 'nome_file', 'categoria', 'copertina'])
        for f in foto:
            writer.writerow([f['id'], f['titolo'], f['descrizione'], f['data'], f['nome_file'], f['categoria'], f['copertina']])

if __name__ == "__main__":
    esporta_utenti_csv()
    esporta_foto_csv()
    print("✅ CSV aggiornati da database.")
