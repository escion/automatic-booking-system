import os
import requests
import argparse
import time
from datetime import datetime
from dotenv import load_dotenv

# Carica le variabili da .env
load_dotenv()
id_sede = os.getenv("ID_SEDE")
max_retries = int(os.getenv("MAX_RETRIES", "5"))
sleep_seconds = int(os.getenv("RETRY_DELAY", "10"))
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

def enhanced_log(message: str):
    """
    Logga un messaggio sulla console.
    """
    print(message)
    telegram_message(message)

def telegram_message(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = "<b>🏋️ Prenotazione YAMA</b>"
    full_message = f"{title}\n[{timestamp}]\n{message}"
    if not bot_token or not chat_id:
        print("Manca TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID nel .env")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": full_message,
         "parse_mode": "HTML"
    }
    try:
        resp = requests.post(url, data=payload)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Errore nell'invio del messaggio Telegram: {e}")


def do_post(
    path: str = None,
    form_data: dict = None,
    timeout: int = 10,
) -> str:
    """
    Esegue una POST e ritorna la risposta JSON.
    Se fallisce, solleva un'eccezione e blocca lo script.
    """
    # Se non è passato un URL, lo legge dal .env
    url = os.getenv("API_URL") + path
    if not url:
        print("Manca API_URL nel .env")

    try:
        resp = requests.post(url, data=form_data, timeout=timeout)
        resp.raise_for_status()  # solleva se status >= 400
        return resp.json()  # solleva se non è JSON valido
    except requests.exceptions.RequestException as e:
        print(f"Errore HTTP nella POST a {url}: {e}")
    except ValueError:
        print(f"La risposta da {url} non è JSON valido")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script per prenotare corsi automaticamente.")
    parser.add_argument("--giorno", required=True, help="Giorno della prenotazione (YYYY-MM-DD)")
    parser.add_argument("--ora_start", required=True, help="Ora di inizio della prenotazione (HH:MM)")
    parser.add_argument("--corso", required=True, help="Nome del corso da prenotare", choices=["Hatha Yoga", "Vinyasa Yoga", "Calisthenics", "Pilates", "Biomechanics", "HandStand"])
    parser.add_argument("--mode", help="Modalità di prenotazione: read o book", choices=["read", "book"], default="read")
    parser.add_argument("--users", help="Utenti per il login", nargs="+", required=True, choices=["alessandro", "giulia", "luna"])
    args = parser.parse_args()
    
    giorno = args.giorno
    ora_start = args.ora_start
    corso = args.corso
    mode = args.mode
    users = args.users

    for user in users:

        user = user.upper()
        print(f"User: [{user}]")

        # Login
        body = {
            "mail": os.getenv(user + "_USERNAME"),
            "pass": os.getenv(user + "_PASSWORD"),
            "versione": "33",
            "tipo": "web",
            "langauge": "it"
        }
        login_response = do_post("/loginApp", body)
        if login_response["status"] == 2:
            # Recupero sessionId
            session_id = login_response["parametri"]["sessione"]["codice_sessione"]
            print(f"Login [OK], codice sessione: [{session_id}]")

            # Recupero palinsesti in base ai parametri.
            body = {
                "id_sede": id_sede,
                "codice_sessione": session_id,
                "giorno": giorno
            }
            palinsesti_response = do_post("/palinsesti", body)
            if palinsesti_response["status"] != 2:
                print(f"Recupero palinsesti fallito: {palinsesti_response}")


            # cerca id palinsesto in base a corso, ora_start
            palinsesto = palinsesti_response["parametri"]["lista_risultati"][0]
            id_orario_palinsesto = None
            bookable = False
            for day in palinsesto["giorni"]:
                if id_orario_palinsesto is not None:
                    break
                current_day = day["nome_giorno"]
                print(f"Analisi giorno: [{current_day}] per corso [{corso}] alle [{ora_start}]")
                if day["giorno"] == giorno:
                    for orario in day["orari_giorno"]:
                        if (orario["orario_inizio"] == ora_start and orario["nome_corso"] == corso):
                            id_orario_palinsesto = orario["id_orario_palinsesto"]
                            numero_posti_disponibili = orario["prenotazioni"]["numero_posti_disponibili"]
                            print(f"Id orario palinsesto: [{id_orario_palinsesto}], numeri posti disponibili: [{numero_posti_disponibili}]")
                            # non prenotabile per posti esauriti o prenotazioni non ancora aperte o altro
                            if orario["prenotazioni"]["id_disponibilita"] == "0":
                                enhanced_log(f'Errore: [{orario["prenotazioni"]["frase"]}].')
                            else:
                                bookable = True
            
            if id_orario_palinsesto is None:
                print(f"Impossibile trovare il corso [{corso}] il giorno [{giorno}] alle [{ora_start}]")
            else:
                if bookable:
                    if mode == "read":
                        print(f"Modalità [read]: prenotazione NON effettuabile.")
                    else:
                        # prenotazione con retry se per esempio alle 22.00.00 esatte non sono ancora aperte le prenotazioni
                        body = {
                            "id_sede": id_sede,
                            "codice_sessione": session_id,
                            "id_orario_palinsesto": id_orario_palinsesto,
                            "giorno": giorno
                        }
                        for retry in range(max_retries):
                            prenotazione_response = None
                            #prenotazione_response = do_post("/prenotazione_new", body)
                            if prenotazione_response["status"] == 2:
                                enhanced_log(f"Prenotazione avvenuta con successo per il corso: [{corso}] il giorno: [{giorno}] alle [{ora_start}]")
                                break
                            else:
                                enhanced_log(f'Prenotazione fallita, stato: [{prenotazione_response["status"]}] messaggio: [{prenotazione_response["messaggio"]}]. Retry {retry + 1}/{max_retries} dopo {sleep_seconds} secondi.')
                                time.sleep(sleep_seconds)
                else:
                    enhanced_log(f"Corso [{corso}] il giorno [{giorno}] alle [{ora_start}] NON prenotabile.")
        else:
            print("Login fallita.")