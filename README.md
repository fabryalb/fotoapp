# FotoApp 📸

Un'applicazione Flask per la gestione di una collezione fotografica personale o condivisa, con supporto a categorie, permessi utente, upload massivo e visualizzazione da browser.

## 🚀 Funzionalità principali

- 🔐 Login con ruoli (`admin`, `utente`, `ospite`)
- ✅ Sistema di permessi per ogni categoria (visualizza, aggiungi, modifica, elimina, ruota)
- 🖼️ Caricamento e modifica immagini (singolo o massivo)
- 📂 Organizzazione in categorie e sottocategorie (con supporto a `/` o `>`)
- 📸 Rotazione automatica EXIF durante la modifica
- 🔍 Ricerca e filtro immagini per titolo, descrizione, data o categoria
- 📤 Condivisione immagini tramite link diretto o pagina dedicata
- 📱 Interfaccia responsive compatibile anche da smartphone
- 🔒 Separazione utenti e permessi tramite file `utenti.csv`
- 💾 Salvataggio dei metadati in `dati_foto.csv`

## 🧑‍💻 Come eseguire in locale

Assicurati di avere Python installato, poi:

```bash
pip install -r requirements.txt
python app.py
```

## 🌐 Deploy su Render

Il progetto è già pronto per Render:

- Il file `Procfile` contiene: `web: gunicorn app:app`
- Il file `requirements.txt` include `flask`, `pillow` e `gunicorn`
- I dati sono salvati in CSV **(non persistenti su Render Free)**

## 🔁 Backup CSV

Puoi usare lo script `backup_csv.py` per creare backup locali dei file `dati_foto.csv` e `utenti.csv` in formato `.zip`.

## 📁 Struttura principale

```
fotoapp/
│
├── app.py                 # File principale Flask
├── requirements.txt       # Librerie necessarie
├── Procfile               # Per il deploy su Render
├── .gitignore             # Esclude file temporanei e sensibili
├── dati_foto.csv          # Database foto (non tracciato)
├── utenti.csv             # Elenco utenti e permessi (non tracciato)
├── templates/             # File HTML (Jinja2)
└── static/foto/           # Immagini caricate organizzate per categoria
```

## 👤 Autore

Fabrizio Alberto  
🔗 [https://github.com/fabryalb](https://github.com/fabryalb)
