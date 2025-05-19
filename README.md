# Bachelorarbeit
# **Chatbotbasierte Museumsguides – Design und Evaluation von multiplen Gesprächsagenten in einem Gruppenchat**

Bei Fragen oder Problemen, bin ich über sahra.guerkan@student.uni-siegen.de erreichbar.

## Projektübersicht  
Das Projekt besteht aus zwei getrennten Modulen:  
1. **Einzelchat:** Ein Einzelchat zwischen Benutzer und dem Hermine Granger Chatbot.
2. **Gruppenchat:** Ein Gruppenchat zwischen drei Charakterbots (Son Goten, Hermine Granger & Leonardo da Vinci) und Benutzer.

**Voraussetzungen**
Python 3.13; alle weiteren Anforderungen sind in der Datei requirements.txt aufgeführt.

**Setup**
1. Erstelle eine Discord Application (https://www.ionos.de/digitalguide/server/knowhow/discord-bot-erstellen/).
2. Wiederhole den 1. Schritt 3 weitere Male, sodass insgesamt 4 Chatbots erstellt wurden.
3. Erstelle einen OpenAI-API (https://platform.openai.com/api-keys).
4. Ersetze die Platzhalter in den .env Dateien mit deinen eigenen Token.
5. Ersetze den Platzhalter für ALLOWED_CHANNELS in Gruppenchat/orchestrator.py und Einzelchat/Einzelagent.py mit deiner Kanal-ID.
6. Virtuelle Umgebung einrichten; Einzelchat wird über Einzelchat/Einzelagent.py & Gruppenchat über Gruppenchat/main.py ausgeführt. 
(Einzel- und Gruppenchat nicht simultan im selben Kanal ausführen, das ergibt nur Chaos)
7. Viel Spaß beim ausprobieren!


**Verwendete Internetquellen:**
1. https://coderivers.org/blog/python-randomrandom/
2. https://community.openai.com/t/help-integrating-the-assistant-api-into-a-discord-bot/620515
3. https://discordpy.readthedocs.io/en/stable/faq.html
4. https://discordpy.readthedocs.io/en/stable/logging.html#logging-setup
5. https://discordpy.readthedocs.io/en/stable/quickstart.html
6. https://docs.aiohttp.org/en/stable/client_quickstart.html
7. https://docs.python.org/3/library/asyncio-sync.html
8. https://docs.python.org/3/library/asyncio-task.html#asyncio.gather
9. https://www.geeksforgeeks.org/self-in-python-class/
10. https://docs.python.org/3/library/random.html
11. https://gist.github.com/niklak/05ca0e64152c4f18ed8c65c888e7ba46
12. https://github.com/openai/gpt-discord-bot/blob/main/src/main.py
13. https://github.com/Tech-Watt/OpenAI-Dall-3-image-generator-in-Python/blob/master/main.py
14. https://www.ionos.de/digitalguide/server/knowhow/discord-bot-erstellen/
15. https://myscale.com/blog/de/chunking-strategies-for-optimizing-llms/
16. https://platform.openai.com/docs/guides/image-generation?image-generation-model=gpt-image-1
17. https://platform.openai.com/docs/guides/images-vision?api-mode=chat 
18. https://pypi.org/project/python-dotenv/
19. https://stackoverflow.com/questions/48265247/how-to-set-the-image-of-a-discord-embedded-message-with-a-variable/48270318#4827031
