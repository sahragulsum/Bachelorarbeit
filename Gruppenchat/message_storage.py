import asyncio
from typing import Dict, List, Any

#   Klasse zur Verwaltung aller Nachrichten = Zentralspeicher
#   Wird vom Mediatorbot und den Charakterbots gemeinsam genutzt
#   Für eine koordinierte Zusammenarbeit
class MessageStorage:
    def __init__(self):
        #   Alle wichtigen Daten werden hier initialisiert
        self.store = {
            "participant_message": None,   #   Nachricht (vom Nutzer oder den Charakterbots)
            "channel_id": None,     #   Channel-ID, indem die Nutzeranfrage geschickt wurde
            "image_url": None,      #   Bild-URL
            "allowed_bots": [],     #   Bots, die antworten dürfen
            "conversation_history": [],     #   Bisherige Nachrichten
            "user_history": [],     #   Alle Nutzeranfragen
            "message_id": 0,        #   ID der Nachricht
            "message_count": 0,     #   Zähler für die Antwortanzahl
            "bot_messages": []      #   Alle versendeten Botnachrichten
        }
        self.lock = asyncio.Lock()    #   exklusive Speicherzugriffe
        self.response_events = {bot: asyncio.Event() for bot in ["leonardo", "goten", "hermine"]}   #   Signal für die Beantwortung von Nachrichten
        self.send_message_events = asyncio.Event()  #   Signal zum Nachrichtenversand
        self.answers: Dict[str, str] = {}   #   Antworttexte
        self.chosen_bot: None | str = None  #   ausgewählter Bot zum Antworten
        self.last_chosen_bots = []  #   zuletzt gewählter Charakterbot
        self.user_message_event = asyncio.Event()  #   Signal zur neuen Nutzernachricht
        self.meta_selection_done = asyncio.Event() #   Signal für die fertige Bot-Auswahl
        self.bot_response_memory = {
            "leonardo": [],
            "hermine": [],
            "goten": []
        }   #   Alle finalen Botnachrichten

    #   Antworten der Bots werden als Botnachrichten gespeichert
    #   Um zwischen Nutzeranfragen und Botnachrichten zu unterscheiden
    async def store_bot_messages(self, message_text: str, received_message_id: int, sent_message_id: int,
                                 is_image=False, bot_name: str = None):
        async with self.lock:
            self.store["bot_messages"].append({
                "message_text": message_text,
                "received_message_id": received_message_id,
                "sent_message_id": sent_message_id,
                "is_image": is_image,
                "bot_name": bot_name
            })

    #   Prüfen, ob die maximale Antwortgrenze von 5 Nachrichten pro Nutzeranfrage erreicht wurde
    async def can_bot_reply(self, last_received_id):
        async with self.lock:
            max_depth=5 #   Maximal erlaubte Antwortzahl
            depth = 0   #   Initialer Zähler für die aktuelle Antwortzahl
            current_id = last_received_id   #   Startpunkt für die Zählung ist die ID der zuletzt zugestellten Nachricht
            #   Welcher Bot hat auf welche Nachricht geantwortet?
            id_lookup = {
                #   Jeder gesendeten Nachricht, wird die ID der Nachricht zugeordnet, auf die sie geantwortet hat
                msg["sent_message_id"]: msg["received_message_id"]
                for msg in self.store["bot_messages"]
            }  #   Jede Botnachricht durchläuft das
            #   Die Kette der Antworten wird rückwärts verfolgt
            while current_id in id_lookup:
                #   Bei jedem Schleifendurchlauf wird die Antworttiefe um eins erhöht
                #   Für jede Antwort auf eine Antwort, wird die Tiefe also erhöht
                depth += 1
                #   Wenn die maximale Tiefe erreicht wird, darf nicht mehr geantwortet werden
                if depth >= max_depth:
                    return False
                #   Auf welche Nachricht hat die ID der letzten Nachricht geantwortet?
                #   Tiefe der Kette wird zurückverfolgt
                current_id = id_lookup[current_id]
            return True  #  Max Tiefe noch nicht erreicht, also darf geantwortet werden

    #   Zählt die Antworten pro Nutzeranfrage
    async def get_reply_count(self, last_received_id):
        async with self.lock:
            depth = 0   #   Initialer Zähler für die aktuelle Antwortzahl
            current_id = last_received_id   #   Startpunkt für die Zählung ist die ID der zuletzt zugestellten Nachricht (Anfang: Nutzeranfrage)
            #   Jeder gesendeten Nachricht, wird die ID der Nachricht zugeordnet, auf die sie geantwortet hat
            id_lookup = {
                msg["sent_message_id"]: msg["received_message_id"]
                for msg in self.store["bot_messages"]
                if not msg.get("is_image")  #   Nur Nachrichten OHNE Bildgenerierung werden berücksichtigt
            }
            #   Die Kette der Antworten wird rückwärts verfolgt
            #   Bis die ursprüngliche Nachricht erreicht wurde, und es keine Nachricht gibt, auf die sie sich bezieht
            while current_id in id_lookup:
                depth += 1  #   Bei jedem Schleifendurchlauf wird die Antworttiefe um eins erhöht
                current_id = id_lookup[current_id]  #   Springe zur vorherigen Nachricht in der Kette
                #   Falls eine Nachricht ohne vorherige Nachricht gefunden wird, wird abgebrochen
                if current_id is None:
                    return depth
            return depth    #   Gibt die Tiefe der Kette zurück

    #   Nachrichten der Bots oder des Nutzers speichern
    async def store_participant_message(self, participant_message: str, channel_id: str, message_id: int, image_url: str = None):
        async with self.lock:
            #   Falls kein Text vorhanden ist, sondern nur ein Bild, wird die Bildinfo mit URL als Text gespeichert
            if not participant_message and image_url:
                participant_message = f"[BILD: {image_url}]"
            #print(f"[Storage] Speichere Nutzeranfrage {participant_message}")

            #   Speichern der Nachricht
            self.store["participant_message"] = participant_message #   Nachricht vom Nutzer/Bot
            self.store["channel_id"] = channel_id   #   Kanal-ID von Discord
            self.store["image_url"] = image_url #   Falls vorhanden: Bild-URL
            self.store["message_id"] = message_id   #   Eindeutige ID einer Nachricht (zur Trennung von alten/neuen Nachrichten)
            self.store["allowed_bots"] = [] #   Setzt erlaubte Bots zurück
            self.store["message_count"] = 0 #   Zähler der bisherigen Nachrichtenanzahl wird auf 0 zurückgesetzt
            #   Alle bisherigen Freigabe-Events werden gelöscht
            for event in self.response_events.values():
                event.clear()
            """ self.user_message_event.set()
            self.user_message_event.clear() """
            #print("[Storage] participant_message wurde gesetzt")
            #print(f"[Storage] {participant_message}")

        #   Das Event für den Auswahlprozess des Orchestrators wird zurückgesetzt
        await self.reset_meta_selection_task()

    #   Mediator speichert Antworten und signalisiert Freigabe für den ausgewählten Bot
    #   Event: Signal zur Freigabe der Antwort
    async def set_messages_and_notify(self, answers, chosen_bot):
        self.chosen_bot = chosen_bot    #   Speichern, welcher Bot antworten darf
        self.answers = answers  #   Speichern der generierten Antworten
        if chosen_bot:
            self.last_chosen_bots.append(chosen_bot)    #   Liste der Bots, die zuletzt geantwortet haben aktualisieren
            # Nur den letzten erlaubten Bot merken
            self.last_chosen_bots = self.last_chosen_bots[-1:]

        self.send_message_events.set()  #   Signal an ausgewählten Bot, dass er antworten darf
        self.send_message_events.clear()    #   Event wird für die nächste Antwort zurückgesetzt

    #   Prüft, ob man der Bot ist, der seine Antwort veröffentlichen darf
    async def wasIChosen(self, bot_name):
        return bot_name == self.chosen_bot

    #   Gibt die Antwort für den jeweiligen Bot zurück
    async def getMyAnswer(self, bot_name):
        return self.answers[bot_name]

    #   Signal, ob Antwort veröffentlicht werden darf & man der ausgewählte Bot ist
    async def wait_for_send_message_event(self):
        await self.send_message_events.wait()

    #   Historie aller Nutzeranfragen
    async def store_user_history(self, participant_message: str, message_id: int, image_url: str = None):
        async with self.lock:
            #   Falls kein Text vorhanden ist, sondern nur ein Bild, wird die Bildinfo mit URL als Text gespeichert
            if not participant_message and image_url:
                participant_message = f"[BILD: {image_url}]"
            #   Speichern der Nachricht
            self.store["user_history"].append({
                "message": participant_message,
                "image_url": image_url,
                "message_id": message_id
            })
            #   Liste des zuletzt gewählten Bots wird mit jeder neuen Nutzeranfrage zurückgesetzt
            self.last_chosen_bots = []

    #   Erstellt Liste der Historie aller Nutzeranfragen
    async def get_user_history(self):
        async with self.lock:
            return list(self.store["user_history"])

    #   Strukturierte Zusammenfassung aller aktuellen Informationen
    async def get_all_data(self) -> Dict[str, Any]:
        async with self.lock:
            return {
                "participant_message": self.store["participant_message"],
                "allowed_bots": list(self.store["allowed_bots"] or []),
                "message_id": self.store["message_id"],
                "conversation_history": list(self.store["conversation_history"]),
                "channel_id": self.store["channel_id"],
                "image_url": self.store["image_url"]
            }

    #   Fügt neue Nachrichten zum Gesprächsverlauf hinzu (für Bot-Gedächtnis)
    async def add_to_conversation(self, role: str, content: str):
        async with self.lock:
            if role in ["leonardo", "goten", "hermine"]:
                if any(
                        msg["message_text"] == content and msg.get("is_image")
                        for msg in self.store["bot_messages"]
                ):
                    return
            self.store["conversation_history"].append({"role": role, "content": content})

    #   Liste des bisherigen Gesprächsverlaufs
    async def get_conversation_history(self):
        async with self.lock:
            return list(self.store["conversation_history"])

    #   Neue Nutzeranfrage: Reset vom globalen Auswahl-Event
    async def reset_meta_selection_task(self):
        async with self.lock:
            self.meta_selection_done.clear()

#   Instanz des Nachrichtenspeichers
storage = MessageStorage()