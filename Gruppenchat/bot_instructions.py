import random
import discord  # Discordmodul importieren
import logging  # Skriptfehler identifizieren
import re   #   Trennung von Strings
import os   # Zugriff auf Funktionen des Betriebssystems
import aiohttp
import base64
from dotenv import load_dotenv
from openai import AsyncOpenAI
from message_storage import storage
import json


#   Fehler im Terminal protokollieren
logging.basicConfig(level=logging.INFO)    # Nur Fehler anzeigen

#   Lädt Variablen aus der .env-Datei
load_dotenv()

#   API-Schlüssel aus der .env-Datei abrufen
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

#   Sicherstellen, dass der API-Schlüssel existiert
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY nicht gefunden! Überprüfe deine .env-Datei.")

#   OpenAI-Client mit API-Schlüssel initialisieren
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

#   Discord-Client Setup
intents = discord.Intents.default()
intents.message_content = True  # Aktiviert die Fähigkeit des Bots, Nachrichten zu lesen
client = discord.Client(intents=intents)    #   Discord-Client initialisieren

#   Funktion zur Aufteilung von langen Nachrichten in mehrere Nachrichten
#   Eine Nachricht ist maximal 2000 Zeichen lang
#   Nachrichten sollen nicht mitten im Satz/Wort geteilt werden
def split_message(text, max_length=2000):
    while len(text) > max_length:
        #   Sucht nach diesen Satzzeichen ".","!","?" nach den ersten 2000 Zeichen
        match = list(re.finditer(r"[\.\!\?\s]", text[:max_length]))
        #   Falls ein Satzende gefunden wird, wird das letzte gefundene Satzzeichen zur Texttrennung verwendet
        if match:
            split_index = max(m.start() for m in match) + 1
            yield text[:split_index].strip()    #   Gibt den Teil bis zum Satzende/ letzten Leerzeichen wieder
            text = text[split_index:].strip()   #   Der restliche Text wird erneut in der Schleife überprüft
        else:
            break
    #   Der verbleibende Text wird als letzte Nachricht gesendet
    yield text

#   Funktion zur Extraktion von Bild-Prompts
#   Bildaufforderungen werden getrennt vom Text verarbeitet
def extract_image_prompts(answer):
    #   Sucht nach allen Bildbeschreibungen in einer Nutzeranfrage
    #   Extrahiert dann alles, was zwischen "[BILD:" und "]" steht
    return re.findall(r"\[BILD:(.*?)]", answer)

#   DALLE-E generiert Bilder basierend auf den Prompts
async def generate_image(PROMPT1):
    response = await openai_client.images.generate(
        model="dall-e-3",
        prompt=PROMPT1,
        size="1024x1024",
        n=1 #   Nur ein Bild pro Prompt
    )
    return response.data[0].url #   URL des generieten Bildes wird ausgegeben

#   Funktion zum Herunterladen von Bildern
#   Lädt ein Bild von einer angegebenen URL herunter
async def download_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.read()
    return None

#   Funktion zum Erstellen und späteren Starten eines Charakterbots
def create_bot(bot_name, DISCORD_BOT_TOKEN):
    logger = logging.getLogger(f'discord.{bot_name}')
    #   Discord-Client initialiseren
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)


    @client.event
    #   Asynchrone Funktion, die aufgerufen wird, wenn der Bot startet
    async def on_ready():
        print(f" {bot_name} ist online")
        await message_loop()    #   Startet die Schleife message_loop zur Bearbeitung von eingehenden Nachrichten

    #   Asynchrone Funktion, die aufgerufen wird, wenn eine Nachricht erhalten wird
    async def message_loop():
        while True:
            #   Warte, bis Mediatorbot Auswahl getroffen hat und Nutzeranfrage zur Beantwortung freigibt
            await storage.wait_for_send_message_event()
            #print(bot_name + " aufgewacht")
            #   Prüfe, ob zur Beantwortung freigegeben
            if not await storage.wasIChosen(bot_name):
                continue    #Falls nicht, wird der Schleifendurchlauf hier abgebrochen

            #   Alle Konversationsdaten aufrufen
            data = await storage.get_all_data()
            #   Nachrichtenbegrenzung prüfen
            current_reply_count = await storage.get_reply_count(data['message_id'])
            #   Antwortenanzahl pro Nutzeranfrage auf maximal 5 setzen
            if current_reply_count >= 5:
                print("Antwortgrenze erreicht. Breche ab.")
                continue

            #   Antwortenanzahl auf bis zu 5 Antworten pro Nutzeranfrage reduzieren
            #   mindestens eine Antwort wird generiert
            #   mit 70%iger Wahrscheinlichkeit wird nach der letzten Antwort eine weitere generiert
#            if current_reply_count >= 1:
#                continue_propability = 0.7
#                if random.random() > continue_propability:
#                    print(f"Zufällig gestoppt bei {current_reply_count}")
#                    continue

            #   Antworttext des Charakterbots holen
            answer = await storage.getMyAnswer(bot_name)
            #   Erlaubte Kanäle entsprechen den Kanälen, in denen der Mediator eine Berechtigung hat
            channel_id = data["channel_id"]
            channel = discord.utils.get(client.get_all_channels(),id=channel_id)

            #   Verarbeitung von Antworten mit Bildgenerierung
            if "[BILD:" in answer:
                #   Extrahiert Bildprompts werden als Liste in der Variablen image_prompts gespeichert
                image_prompts = extract_image_prompts(answer)
                for prompt in image_prompts:
                    #   Antwortengrenze prüfen
                    if await storage.get_reply_count(data["message_id"]) >= 5:
                        print("Antwortgrenze erreicht. Versende keine Antwort mehr.")
                        return  #   Wenn hier eine Überschreitung vorliegt, wird die Schleife abgebrochen

                    try:
                        img_url = await generate_image(prompt.strip())  #   Mit dem Bildprompt wird über Dall-e ein Bild generiert
                        embed = discord.Embed() #   Discord-Einbettung
                        embed.set_image(url=img_url)    #   Bild wird eingefügt
                        sent_message = await channel.send(embed=embed)  #   Nachricht wird abgesendet
                        #   Nachricht in den Botnachrichten-Speicher hinzufügen
                        await storage.store_bot_messages(f"[BILD: {img_url}]", data['message_id'], sent_message.id, is_image=True, bot_name=bot_name)
                        #print(f"Bot hat nachricht gespeichert {sent_message.id}")

                    #   Fehlerbehandlung bei der Bildgenerierung
                    except Exception as e:
                        logger.error(f"Fehler bei Bild {e}")
                        await channel.send(f"Fehler beim Erstellen von Bild {e}")

            #   Text ohne Bildanweisungen senden
            text_only = re.sub(r"\[BILD:.*?]", "", answer).strip()
            if text_only:
                #   Antwort wird in mehrere Nachrichten aufgeteilt, welche jeweils maximal 2000 Zeichen haben
                chunks = list(split_message(text_only))
                for chunk in chunks:
                    #   Antwortengrenze prüfen
                    if await storage.get_reply_count(data["message_id"]) >= 5:
                        print("Antwortgrenze erreicht. Keine weitere Antwort mehr.")
                        return  #   Wenn hier eine Überschreitung vorliegt, wird die Schleife abgebrochen
                    sent_message = await channel.send(chunk)    #   Nachricht wird abgesendet
                    #   Nachricht in den Botnachrichten-Speicher hinzufügen
                    await storage.store_bot_messages(chunk, data['message_id'], sent_message.id, is_image=False, bot_name=bot_name)
    #   Funktion zum Starten des Charakterbots
    async def run():
            await client.start(DISCORD_BOT_TOKEN)

    #   Gibt die Funktion zum Starten des Botprozesses zurück
    return run

