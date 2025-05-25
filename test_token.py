# test_token.py
from photo_sharing import gestore_condivisioni

# Genera un token finto
token = gestore_condivisioni.crea_condivisione(
    foto_ids=[101, 102],
    creatore="testuser",
    titolo="Test da script",
    giorni_scadenza=1
)

print("✅ Token generato:", token)