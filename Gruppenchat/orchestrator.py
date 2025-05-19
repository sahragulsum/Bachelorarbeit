import base64
import json
import discord
import logging  # Skriptfehler identifizieren
import os
import aiohttp
import random
from dotenv import load_dotenv
from openai import AsyncOpenAI
from message_storage import storage
from prompts import goten, hermine, leonardo

#   Fehler im Terminal protokollieren
logging.basicConfig(level=logging.INFO)  # Nur Fehler anzeigen
logger = logging.getLogger('discord')

#   Lader der Umgebungsvariablen (aus der .env-Datei)
load_dotenv()

#   API-Schlüssel abrufen (aus der .env-Datei)
DISCORD_BOT_TOKEN = os.getenv('meta_bot_token')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

#   Sicherstellen, dass die API-Schlüssel erfolgreich geladen wurden
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY nicht gefunden! Überprüfe deine .env-Datei.")
if not DISCORD_BOT_TOKEN:
    print(" Fehler: meta_bot_token konnte nicht geladen werden! ")
else:
    print("meta_bot_token geladen.")

#   OpenAI-Client mit API-Schlüssel initialisieren
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

#   Discord-Client initialisieren
intents = discord.Intents.default()
intents.message_content = True  #   Aktiviert die Fähigkeit des Bots, Nachrichten zu lesen
client = discord.Client(intents=intents)

#   Liste der erlaubten Textkanäle, in denen der Bot aktiv sein darf (durch Platzhalter ersetzt)
ALLOWED_CHANNELS = [1234567890987654321]


#   Funktion zum Herunterladen von Bildern
#   Lädt ein Bild von einer angegebenen url herunter
async def download_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.read()
    return None

#   Event: Mediatorbot wird gestartet
@client.event
async def on_ready():
    print("Mediator-Bot ist online.")

#   Event: Nachrichten empfangen
#   Jede Nachricht wird einzeln behandelt
@client.event
async def on_message(message):
    #   Unterscheide zwischen Bot-Nachrichten und Nutzeranfragen
    if message.author.bot:
        print(f"Orchestrator hat nachricht bekommen {message.id}: {message.content}")
        #   Falls Bot-Nachricht ein Bild enthält, wird die Bild-URL gespeichert
        #   Wenn Bots Textnachrichten inklusive Bilder schicken, werden diese als 2 Nachrichten versendet
        for embed in message.embeds:
            if embed.image and embed.image.url:
                image_url = embed.image.url
                user_text = image_url   #   Setze die Bild-URL als Textinhalt
                print(f"[Orchestrator] Bot-Bildnachricht erkannt: {image_url}")
                #   Nachricht im Teilnehmerverlauf speichern
                await storage.store_participant_message(user_text, message.channel.id, message.id, image_url=image_url)
                # await storage.store_bot_messages(message.content, received_message_id=None, sent_message_id=message.id)

    #   (Erste) Nutzeranfrage wird als (erste) Nachricht gespeichert
    else:
        await storage.add_to_conversation("user", message.content)

    #   Prüfe, ob Nachricht aus einem zugelassenen Kanal kommt
    if message.channel.id not in ALLOWED_CHANNELS:
        return  # Ignoriere Nachricht, wenn nicht aus einem zugelassenen Kanal

    #   Variable für Bild-URL wird initialisiert
    image_url = None

    #   Nutzertext ohne überflüssige Leerzeichen
    user_text = message.content.strip()

    #   Falls ein Bild gesendet wird
    if message.attachments:
        for attachment in message.attachments:
            filename = attachment.filename.lower()
            if (
                    (attachment.content_type and attachment.content_type.startswith("image"))
                    or filename.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
            ):
                image_url = attachment.url
                if not user_text:
                    user_text = image_url   #   Wenn kein Text vorhanden ist, wird die Bild-URL als Textinhalt gespeichert
                print(f"[Orchestrator] Bild gefunden: {image_url}")
                break

    #   Leere Nachrichten werden nicht beantwortet
    if not user_text and not image_url:
        print("[Orchestrator] Leere Nachricht ohne Bild – keine Antwort wird generiert.")
        return

    #   Ohne Text wird die image_url zum Textinhalt
    elif not user_text and image_url:
        # Bild ohne Text, Nutzer hat Bild gesendet – setze Platzhaltertext
        user_text = f"[BILD: {image_url}]"

    if not message.author.bot:
        #   Nur echte Nutzeranfragen im Nutzerverlauf speichern
        await storage.store_user_history(user_text, message.id, image_url=image_url)
        #   Nutzeranfrage im Teilnehmerverlauf speichern
        await storage.store_participant_message(user_text, message.channel.id, message.id, image_url=image_url)
    elif not image_url:
            #   Falls Bot-Nachricht ohne Bild
            #   Ebenfalls im Teilnehmerverlauf speichern
            await storage.store_participant_message(user_text, message.channel.id, message.id, image_url=image_url)
    print(f"User-Message wurde gespeichert: {user_text}")

    #   Bei Bildanfragen werden 40Sekunden auf Antworten der Bots gewartet
    #   Bei Textanfragen werden 10Sekunden auf Antworten der Bots gewartet
    timeout_duration = 40 if image_url else 10

    #   Nutzerverlauf laden
    user_history = await storage.get_user_history()
    all_user_history = "\n".join(f"- {r['message']}" for r in user_history)
    print("Alle bisherigen Nutzeranfragen:")
    print(all_user_history)

    #   Letzte Nutzeranfrage extrahieren
    last_user_message = all_user_history.split("\n")[-1] if all_user_history else ""

    #   Chatbots definieren
    bots = ["hermine", "leonardo", "goten"]
    #   Prompts definieren
    prompts = {"hermine": hermine, "leonardo": leonardo, "goten": goten}

    answers = {}

    #   Antwortenzähler laden
    reply_count = await storage.get_reply_count(message.id)
    #   Antwortenanzahl pro Nutzeranfrage auf maximal 5 setzen
    if reply_count >= 5:
        print(f"[Orchestrator] Max. Antworten erreicht ({reply_count}). Keine weitere Auswahl oder Generierung nötig.")
        return

    #   Antwortenanzahl auf bis zu 5 Antworten pro Nutzeranfrage reduzieren
    #   mindestens eine Antwort wird generiert
    #   mit 70%iger Wahrscheinlichkeit wird nach der letzten Antwort eine weitere generiert
#    if reply_count >= 1:
#        continue_propability = 0.7
#        if random.random() > continue_propability:
#            print(f"[Orchestrator] Zufällig gestoppt bei {reply_count}")
#            return


    for bot in bots:
        #   generateAnswer wird aufgerufen und jeder Bot generiert eine Antwort
        answer = await generateAnswer(message.content, image_url, message.channel, prompts[bot], all_user_history, last_user_message)
        answers[bot] = answer

    #   Prüfe, ob weitere Antworten überhaupt noch erlaubt sind
    can_reply = await storage.can_bot_reply(message.id)
    if not can_reply:
        return

    #   bisherige Gesprächshistorie laden
    history = await storage.get_conversation_history()

    #   die Liste der relevanten Konversation initialisieren
    relevant_conversation = []
    #   Prüfe, welcher Bot zuletzt geantwortet hat
    bot_names = ["hermine", "leonardo", "goten"]
    recent_bots = storage.last_chosen_bots or []
    last_bot = recent_bots[-1] if recent_bots else None
    print(f"Zuletzt gewählter Bot: {last_bot}")

    #   Der zuletzt antwortende Bot wird für die nächste Auswahl ausgeschlossen
    #   Vorausgesetzt es gab für die Nutzeranfrage bereits eine Antwort
    bots_to_exclude = last_bot if last_bot else set()
    #   Dictionary filtered_answers speichert nur die Antworten der Bots, die noch antworten dürfen
    filtered_answers = {
        bot: answer for bot, answer in answers.items()
        if bot not in bots_to_exclude and bot in bot_names
    }

    print(f"Gefilterte Bots: {list(filtered_answers.keys())}")


    print("--------------------------")
    print(f"Aktuelle Nachricht:\n{message.content}")
    print(f"Dazugehörige Antworten:\n{answers}")
    print("--------------------------")

    full_prompt = f"""
    Du dienst als Orchestrator in einem Gruppenchat und koordinierst, wann welcher Chatbot auf eine Nutzeranfrage antworten darf.
    Wähle zwischen den verschiedenen Antworten, die beste aus. 
    Gebe anschließend ******nur*** den Namen des Bots*** zurück, dessen Antwort am besten passt.
    z.B. "leonardo" oder "goten", "hermine"..
    Hier ist der bisherige Gesprächsverlauf:
    {json.dumps(history)}.
    {history[-1]["role"]} hat folgendes geschrieben:
    \"\"\"{message.content}\"\"\"
    Die folgenden Chatbots haben geantwortet (der letzte Bot wurde ausgeschlossen): {filtered_answers}.
    Die zuletzt gestellte Nutzerfrage: {last_user_message} sollte stets erfolgreich beantwortet werden.
    Die Unterhaltung soll zielführend, aber vor allem auch unterhaltsam sein.
    Die passendste Antwort kann auch einfach die unterhaltsamste sein, auch wenn sie inhaltlich nicht perfekt ist.
    Die letzte Antwort ist von {history[-1]["role"]} gekommen. Wähle Sie/Ihn nicht aus!
    Es wurden bereits {relevant_conversation} Antworten zu der Nutzeranfrage gesendet. 
    """

    # Orchestrator trifft Entscheidung
    try:
        decision = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": full_prompt}    #   Übergibt den Prompt zur Koordination des Gesprächs
            ]
        )
        #   Extrahiert die Antwort des Orchestrators:
        #   (nur der Name des ausgewählten Charakterbots), also {chosen}
        chosen = decision.choices[0].message.content.strip().lower()
        print(f"[Orchestrator] GPT-Auswahl-Rohtext: {chosen}")
        #   Übergibt die Auswahl {chosen}, an das Modul, dass die Berechtigung an den ausgewählten Bot weitergibt
        await storage.set_messages_and_notify(filtered_answers, chosen)

    #   Fehlerbehanldung bei der Botauswahl
    except Exception as e:
        print(f"Fehler bei der Auswahl: {e}")
        return

#   Startet den Mediatorbot, sodass er live auf Discord ist
def run_bot():
    return client.start(DISCORD_BOT_TOKEN)

#   Generierung von Antworten seitens der Charakterbots
async def generateAnswer(_message, image_url, channel, system_prompt, all_user_history, last_user_message):
    #   Bisherige Gesprächshistorie wird geladen
    conversation = await storage.get_conversation_history()
    relevant_conversation = []
    #   Finde die letzte Nutzeranfrage in der Gesprächshistorie
    last_user_index = next((i for i in reversed(range(len(conversation))) if conversation[i]["role"] == "user"),
                           None)
    if last_user_index is not None:
        for msg in conversation[last_user_index:]:
            #   Speichere alle Nachrichten ab der letzten Nutzeranfrage
            relevant_conversation.append(msg)

    #   Überprüfe, ob in der Nutzeranfrage ein Bild vorhanden ist
    if image_url:
        #   Bild herunterladen
        image_bytes = await download_image(image_url)
        if not image_bytes:
            await channel.send(content="Bild konnte nicht gelesen werden.")
            return

        #   Das heruntergeladene Bild wird in Base64 umgewandelt
        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        #   Nachricht inklusive Bild
        image_block = {
            "role": "user",
            "content": [
                {"type": "text", "text": _message},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
            ]
        }

        #   Generierung einer Antwort, wenn in der Nutzeranfrage ein Bild enthalten ist
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": (
                "Hier handelt es sich um einem Gruppenchat mit den Chatbots Leonardo da Vinci, Hermine Granger, Son Goten und einem Nutzer."
                "Antworte auf die **letzte NUTZERanfrage**. "
                f"Zuletzt gestellte Nutzerfrage: {last_user_message}."
                "Hauptziel ist, dass diese Anfrage erfolgreich beantwortet wird!!!"  
                f"Nehme in deiner Antwort Bezug auf die zuletzt gestellte Anfrage: {conversation[last_user_index]} "
                "Du darfst Antworten anderer Bots oder Folgefragen berücksichtigen, die nach der zuletzt gestellten Nutzeranfrage gepostet wurden"
                f"aber die {last_user_message} soll der Mittelpunkt deiner Antwort sein."
                f"Das ist das der Konversationskontext: {json.dumps(relevant_conversation)}"
                f"Besonders wichtig ist, was der Nutzer alles gesagt hat, merke dir das! {all_user_history}"
                "Wenn dir ein Bild zugesendet wir: beschreibe es detailliert und analysiere es, nenne den Maler und den Namen des Bildes!"
                "Halte deine Antworten kurz!! Orientiere dich an max. *20 Wörtern* als Antwortlänge."
                "Deine Antworten können von den anderen Chatbots ergänzt werden, du darfst auch deren Beiträge ergänzen."
                "Keine ständigen Gegenfragen!"
                "Bsp.1 Nutzer: Hallo! Bot: Hi."
                "Bsp.2 Nutzer: Wieso sind Rosen rot? Bot: Rosen sind rot aufgrund der Anthocyan-Pigmente."
                "Nicht immer: Nutzer: Wieso sind Rosen rot? Bot: Rosen sind rot aufgrund der Anthocyan-Pigmente. Welche Farbe magst du an Rosen am meisten?"
                "Jedoch immer: Nutzer: Wie gehts? Bot: Gut und dir?"
                "Bei Zeichenwünschen IMMER am Ende eingeben: [BILD: <eine sachliche, passende Beschreibung>]"
                "Verschicke Bilder immer mit einem weiteren Textinhalt in deinem Stil. Bsp.: Textinhalt [BILD: Bild1]"
            )},
            image_block
        ]
    else:
        #   Generierung einer Antwort, wenn kein Bild in der Nutzeranfrage enthalten ist
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": (
                "Hier handelt es sich um einem Gruppenchat mit den Chatbots Leonardo da Vinci, Hermine Granger, Son Goten und einem Nutzer."
                "Antworte auf die **letzte NUTZERanfrage**. "
                f"Zuletzt gestellte Nutzerfrage: {last_user_message}."
                "Hauptziel ist, dass diese Anfrage erfolgreich beantwortet wird!!!"
                f"Nehme in deiner Antwort Bezug auf die zuletzt gestellte Anfrage: {conversation[last_user_index]} "
                "Du darfst Antworten anderer Bots oder Folgefragen berücksichtigen, die nach der zuletzt gestellten Nutzeranfrage gepostet wurden"
                f"aber die {last_user_message} soll der Mittelpunkt deiner Antwort sein."
                f"Das ist das der Konversationskontext: {json.dumps(relevant_conversation)}"
                f"Besonders wichtig ist, was der Nutzer alles gesagt hat, merke dir das! {all_user_history}"
                "Wenn dir ein Bild zugesendet wir: beschreibe es detailliert und analysiere es, nenne den Maler und den Namen des Bildes!"
                "Halte deine Antworten kurz!! Orientiere dich an max. *20 Wörtern* als Antwortlänge."
                "Deine Antworten können von den anderen Chatbots ergänzt werden, du darfst auch deren Beiträge ergänzen."
                "Keine ständigen Gegenfragen!"
                "Bsp.1 Nutzer: Hallo! Bot: Hi."
                "Bsp.2 Nutzer: Wieso sind Rosen rot? Bot: Rosen sind rot aufgrund der Anthocyan-Pigmente."
                "Nicht immer: Nutzer: Wieso sind Rosen rot? Bot: Rosen sind rot aufgrund der Anthocyan-Pigmente. Welche Farbe magst du an Rosen am meisten?"
                "Jedoch immer: Nutzer: Wie gehts? Bot: Gut und dir?"
                "Bei Zeichenwünschen IMMER am Ende eingeben: [BILD: <eine sachliche, passende Beschreibung>]"
                "Verschicke Bilder immer mit einem weiteren Textinhalt in deinem Stil. Bsp.: Textinhalt [BILD: Bild1]"
            )},
            {"role": "user", "content": _message}
        ]
    #   OpenAI API-Aufruf
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )
    #   Extrahiere die erste Antwort
    answer = response.choices[0].message.content
    #   Gebe die Antwort aus
    return answer
