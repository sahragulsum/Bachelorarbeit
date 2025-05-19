import discord
import logging
import re
import os
import json
import aiohttp
import base64
from dotenv import load_dotenv
from openai import AsyncOpenAI

#   Fehlerprotokollierung
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

#   .env laden
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv('hermine_token')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

#   Sicherstellen, dass die API-Schlüssel erfolgreich geladen wurden
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY fehlt in .env")
if not DISCORD_BOT_TOKEN:
    raise ValueError("hermine_token fehlt in .env")
else:
    print("hermine_token geladen.")

#   OpenAI-Client mit API-Schlüssel initialisieren
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

#   Discord-Client initialisieren
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

#   Liste der erlaubten Textkanäle, in denen der Bot aktiv sein darf (durch Platzhalter ersetzt)
ALLOWED_CHANNELS = [1234567890987654321, 9876543210123456789]

#   Speicher für diese Sitzung initialisieren
conversation_history = []

PROMPT1 = """
Du bist Hermine Granger, eine intelligente, belesene, loyale und mutige Hexe. 
Die Zaubererwelt ist für dich REAL, NICHT FIKTIV.
Du sprichst gewandt und beim Korrigieren anderer klingst du besserwisserisch, auch wenn es höflich gemeint war.
Antworte nur mit Bildern, wenn DER NUTZER EXPLIZIT DANACH FRAGT.
Du sagst zwar, dass du nicht gut zeichnen kannst, jedoch sehen deine Zeichnungen im Cartoon-Stil sehr ästhetisch aus.
Bei Zeichenwünschen sollst du am Ende deiner Antwort das folgende Tag eingeben: [BILD: <eine sachliche, passende Beschreibung>].
Bei mehreren Bildaufforderungen: [BILD: Erstes Bild] [BILD: Zweites Bild]…
Verschicke Bilder nur, wenn der Nutzer dies wünscht oder der Kontext das hergibt.
Versuche deine Antworten kurz zu halten. Orientiere dich an 20 Wörtern.
Du darfst auf eine Nutzeranfrage maximal 5 Antworten verschicken.
Somit kannst du den Inhalt einer ausführlichen Nachricht auf mehrere Nachrichten teilen.
Gib deine Antwort in bis zu 5 separaten Absätzen, jeweils durch zwei Zeilenumbrüche getrennt. Jeder Absatz enthält einen klaren Gedanken.
Diese Absätze werden im Chat als getrennte Nachrichten angezeigt.

Beispiel1:
Nutzer: Rosen haben Dornen, damit Insekten leichter drauf klettern können.
Hermine: Ähm.. nein 🙄 Dornen haben absolut nichts damit zu tun, dass Insekten besser klettern können, sie dienen in erster Linie dem Schutz vor Fressfeinden wie Ziegen oder andere Pflanzenfresser.
 Insekten brauchen keine Dornen, um eine Pflanze zu erklimmen – sie haben Haftstrukturen an ihren Beinen. Wirklich – ein Blick in ein ordentliches Biologiebuch könnte da helfen… 📖

Beispiel2:
Nutzer: Ron hätte doch einfach nicht mitkommen müssen. Dann wär es für Harry und dich doch viel leichter gewesen!
Hermine: Ganz sicher nicht! Ron gehört genauso zu uns wie Harry – wir sind Freunde, und Freunde lässt man nicht einfach zurück, nur weil es „leichter“ wäre.
Ohne ihn hätten wir übrigens den Stein der Weisen nie rechtzeitig erreicht - du erinnerst dich doch sicherlich an das Schachbrett?♟️
"""

#   Funktion zur Aufteilung von langen Nachrichten in mehrere Nachrichten
#   Eine Nachricht ist maximal 2000 Zeichen lang
#   Nachrichten sollen nicht mitten im Satz/Wort geteilt werden
def split_message(text, max_length=2000):
    while len(text) > max_length:
        match = list(re.finditer(r"[\.\!\?\s]", text[:max_length]))
        if match:
            split_index = max(m.start() for m in match) + 1
        else:
            split_index = max_length
        yield text[:split_index].strip()
        text = text[split_index:].strip()
    yield text

#   Funktion zur Extraktion von Bild-Prompts
#   Bildaufforderungen werden getrennt vom Text verarbeitet
def extract_image_prompts(answer):
    return re.findall(r"\[BILD:(.*?)\]", answer)

#   DALLE-E generiert Bilder basierend auf den Prompts
async def generate_image(PROMPT1):
    response = await openai_client.images.generate(
        model="dall-e-3",
        prompt=PROMPT1,
        size="1024x1024",
        n=1
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

#   Event: Einzelbot Hermine wird gestartet
@client.event
async def on_ready():
    print("Hermine ist online!")

#   Verarbeitung eingehender Nutzeranfragen
@client.event
async def on_message(message):
    global conversation_history  #  Zugriff auf die globale Variable, um sie innerhalb der Funktion zu verändern
    #   Prüfen, ob Nachricht von einem selbst verfasst wurde
    if message.author == client.user:
        return  #   Nicht auf eigene Nachrichten antworten
    #   Prüfe, ob Nachricht aus einem zugelassenen Kanal kommt
    if message.channel.id not in ALLOWED_CHANNELS:
        return   # Ignoriere Nachricht, wenn nicht aus einem zugelassenen Kanal

    #   Nutzertext ohne überflüssige Leerzeichen extrahieren
    user_text = message.content.strip() if message.content else ""

    #   Übergangsnachricht verschicken
    loading_msg = await message.channel.send("Hermine denkt nach...")

    #   Erstellt einen Nachrichteneintrag für den Chatverlauf
    entry = {"role": "user", "content": []}

    #   Wenn Nutzer eine Nachricht schickt, wird sie dem erstellten Eintrag hinzugefügt
    if user_text:
        entry["content"].append({"type": "text", "text": user_text})

    #   Falls ein Bild gesendet wird
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image"):
            #   Lade das Bild als Byte-Daten herunter
            image_bytes = await download_image(attachment.url)
            if image_bytes:
                #   Wandle das Bild in einen Base64-String um für OpenAI
                b64_image = base64.b64encode(image_bytes).decode("utf-8")
                #   image_url wird dem Eintrag hinzugefügt
                entry["content"].append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}
                })

    #   Wenn die Nutzeranfrage Text oder Bild enthält, wird sie dem Gesprächsverlauf hinzugefüt
    if entry["content"]:
        conversation_history.append(entry)
        print("Nutzeranfrage: ", user_text)

    #   GPT-Aufruf mit Kontext aus der Gesprächshistorie
    messages = [{"role": "system", "content": PROMPT1}] + conversation_history

    try:
        #   OpenAI API-Aufruf
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )
        #   Extrahiere die erste Antwort
        answer = response.choices[0].message.content

        #   Bild-Tags werden aus dem Text entfernt
        text_only = re.sub(r"\[BILD:.*?\]", "", answer).strip()
        #   Antwort wird in Absätze aufgeteilt, getrennt durch zwei Zeilenumbrüche
        paragraphs = [p.strip() for p in text_only.split("\n\n") if p.strip()]

        #   Bot-Antwort auch im Konversationsspeicher merken
        conversation_history.append({
            "role": "assistant",
            "content": [{"type": "text", "text": answer}]
        })
        print("Hermines Antwort: ", answer)

        #   Lösche die Übergangsnachricht
        await loading_msg.delete()

        # Bildgenerierung
        if "[BILD:" in answer:
            #   Extrahiert Bildprompts werden als Liste in der Variablen image_prompts gespeichert
            image_prompts = extract_image_prompts(answer)
            for image_prompt in image_prompts:
                try:
                    img_url = await generate_image(image_prompt.strip())    #   Mit dem Bildprompt wird über Dall-e ein Bild generiert
                    embed = discord.Embed() #   Discord-Einbettung
                    embed.set_image(url=img_url)    #   Bild wird eingefügt
                    await message.channel.send(embed=embed) #   Nachricht wird abgesendet
                #   Fehlerbehandlung bei der Bildgenerierung
                except Exception as e:
                    logger.error(f"Bildfehler: {e}")
                    await message.channel.send(f"Fehler beim Erstellen eines Bildes: {e}")

        #   Teile die Bot-Antwort in maximal 5 Antworten auf
        for para in paragraphs[:5]:
            if len(para) > 2000:
                #   Teilantworten dürfen maximal 2000 Zeichen haben, sonst werden sie aufgeteilt
                for chunk in split_message(para):
                    await message.channel.send(chunk)
            else:
                await message.channel.send(para)

    #   Fehlerbehandlung für alle anderen Probleme bei der Verarbeitung
    except Exception as e:
        logger.error(f"Fehler: {e}")
        await loading_msg.delete()
        await message.channel.send("Es ist ein Fehler aufgetreten 😕")

client.run(DISCORD_BOT_TOKEN)