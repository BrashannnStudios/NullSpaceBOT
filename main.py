import os
import discord
from discord.ext import commands
from keep_alive import keep_alive
from database import init_db

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class NullSpaceBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=self.get_prefix_ci, intents=intents, help_command=None)

    async def get_prefix_ci(self, bot, message):
        # Permite que el prefijo "?" funcione sin importar mayúsculas/minúsculas en el comando
        return "?"

    async def setup_hook(self):
        await init_db()
        # Carga de extensiones (archivos sueltos, sin carpetas)
        extensions = [
            "welcome",
            "moderation",
        ]
        for ext in extensions:
            try:
                await self.load_extension(ext)
                print(f"[OK] Extensión cargada: {ext}")
            except Exception as e:
                print(f"[ERROR] No se pudo cargar {ext}: {e}")

        try:
            synced = await self.tree.sync()
            print(f"[OK] {len(synced)} slash commands sincronizados")
        except Exception as e:
            print(f"[ERROR] Sync de slash commands falló: {e}")

    async def on_ready(self):
        print(f"[READY] Conectado como {self.user} (ID: {self.user.id})")


bot = NullSpaceBot()


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    # Normaliza el comando para que ?lock, ?Lock, ?LOCK funcionen igual,
    # sin tocar los argumentos que le sigan.
    if message.content.startswith("?"):
        parts = message.content.split(" ", 1)
        cmd = parts[0][1:].lower()
        rest = f" {parts[1]}" if len(parts) > 1 else ""
        message.content = f"?{cmd}{rest}"
    await bot.process_commands(message)


if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("DISCORD_TOKEN")
    bot.run(TOKEN)
