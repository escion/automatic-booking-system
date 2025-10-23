import os
import requests
from dotenv import load_dotenv

# Carica le variabili da .env
load_dotenv()
id_sede = os.getenv("ID_SEDE")

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
        raise RuntimeError("❌ Manca API_URL nel .env")

    try:
        resp = requests.post(url, data=form_data, timeout=timeout)
        resp.raise_for_status()  # solleva se status >= 400
        return resp.json()  # solleva se non è JSON valido
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"❌ Errore HTTP nella POST a {url}: {e}")
    except ValueError:
        raise RuntimeError(f"❌ La risposta da {url} non è JSON valido")

if __name__ == "__main__":
    giorno = "2025-10-27"
    ora_start = "20:00"
    ora_end = "21:00"
    corso = "Biomechanics"

    # Login
    body = {
        "mail": os.getenv("USERNAME"),
        "pass": os.getenv("PASSWORD"),
        "versione": "33",
        "tipo": "web",
        "langauge": "it"
    }
    login_response = do_post("/loginApp", body)
    if login_response["status"] == 2:
        # Recupero sessionId
        session_id = login_response["parametri"]["sessione"]["codice_sessione"]
        print(f"Login OK, codice sessione: [{session_id}]")

        # Recupero palinsesti in base ai parametri.
        body = {
            "id_sede": id_sede,
            "codice_sessione": session_id,
            "giorno": giorno
        }
        palinsesti_response = do_post("/palinsesti", body)
        if palinsesti_response["status"] != 2:
            raise RuntimeError(f"❌ Recupero palinsesti fallito: {palinsesti_response}")
        # print(f"Palinsesti: [{palinsesti_response}]")

        # cerca id palinsesto in base a corso, ora_start, ora_end
        palinsesto = palinsesti_response["parametri"]["lista_risultati"][0]
        id_orario_palinsesto = None
        for day in palinsesto["giorni"]:
            if id_orario_palinsesto is not None:
                break
            current_day = day["nome_giorno"]
            print(f"Analisi giorno: [{current_day}] per corso [{corso}] dalle [{ora_start}] alle [{ora_end}]")
            if day["giorno"] == giorno:
                for orario in day["orari_giorno"]:
                    if (orario["orario_inizio"] == ora_start and orario["orario_fine"] == ora_end and orario["nome_corso"] == corso):
                        id_orario_palinsesto = orario["id_orario_palinsesto"]
                        numero_posti_disponibili = orario["prenotazioni"]["numero_posti_disponibili"]
                        print(f"Id orario palinsesto: [{id_orario_palinsesto}], numeri posti disponibili: [{numero_posti_disponibili}]")
                        # non prenotabile per posti esauriti o prenotazioni non ancora aperte o altro
                        if orario["prenotazioni"]["id_disponibilita"] == "0":
                            raise RuntimeError(f'Errore: {orario["prenotazioni"]["frase"]}')
                        break

        # prenotazione
        body = {
            "id_sede": id_sede,
            "codice_sessione": session_id,
            "id_orario_palinsesto": id_orario_palinsesto,
            "giorno": giorno
        }
        #prenotazione_response = do_post("/prenotazione_new", body)
        if prenotazione_response["status"] == 2:
            print(f"✅ Prenotazione avvenuta con successo per il corso: [{corso}] il giorno: [{giorno}] dalle [{ora_start}] alle [{ora_end}]")
        else:
            raise RuntimeError(f'Prenotazione fallita, stato: [{prenotazione_response["status"]}] messaggio: [{prenotazione_response["messaggio"]}]')
    else:
        raise RuntimeError("Login fallita.")