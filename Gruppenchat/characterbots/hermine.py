import os   # Zugriff auf Funktionen des Betriebssystems
from dotenv import load_dotenv
from bot_instructions import create_bot

#   Lädt Variablen von env-Datei
load_dotenv()

#   API-Schlüssel aus der .env-Datei abrufen
DISCORD_BOT_TOKEN = os.getenv('hermine_token')

bot_name = "hermine"

#   Sicherstellen, dass der API-Schlüssel existiert
if not DISCORD_BOT_TOKEN:
    print(f" Fehler: {bot_name} konnte nicht geladen werden! ")
else:
    print(f"{bot_name} geladen.")

run_bot = create_bot(bot_name, DISCORD_BOT_TOKEN)

