import discord
from discord import app_commands
import aiohttp
import os
import time
from aiohttp import web
import os
import asyncio

async def health(request):
    return web.Response(text="OK")

async def start_web():
    app = web.Application()
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"Health server running on port {port}")

TOKEN = os.getenv("DISCORD_TOKEN")
API_URL = "https://gunyahjohnvr.pythonanywhere.com"

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

user_tokens = {}

@client.event
async def on_ready():
    await tree.sync()
    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Game("API Running 🚀")
    )
    print(f"Logged in as {client.user}")

@tree.command(name="token_gen", description="Generate Auth token")
async def login(interaction: discord.Interaction, username: str):

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{API_URL}/token/generator",
                json={"username": username},
                timeout=10
            ) as res:

                data = await res.json()

                if "token" in data:
                    user_tokens[interaction.user.id] = data["token"]

                    await interaction.response.send_message(
                        f"✅ Token:\n```{data['token']}```",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"❌ {data}",
                        ephemeral=True
                    )

        except Exception as e:
            await interaction.response.send_message(
                f"Error: {e}",
                ephemeral=True
            )

async def main():
    await start_web()
    await client.start(TOKEN)

asyncio.run(main())

while True:
    time.sleep(60)
    print("Bot still alive")
