import asyncio
from characterbots import goten, leonardo, hermine
import orchestrator

#   Hauptfunktion zur gleichzeitigen Ausführung aller Bots
async def main():
    await asyncio.gather(
        orchestrator.run_bot(),
        goten.run_bot(),
        leonardo.run_bot(),
        hermine.run_bot()
    )

#   Startpunkt des Programms
if __name__ == "__main__":
    asyncio.run(main())