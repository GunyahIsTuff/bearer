import discord
from discord import app_commands
import aiohttp
import os

TOKEN = os.getenv("DISCORD_TOKEN")
API_URL = "https://gunyahjohnvr.pythonanywhere.com"

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

user_tokens = {}

# ------------------------
# HTTP SESSION (REUSED)
# ------------------------
session = None

# ------------------------
# READY EVENT
# ------------------------
@client.event
async def on_ready():
    global session

    session = aiohttp.ClientSession()

    await tree.sync()

    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Game("API Running 🚀")
    )

    print(f"Logged in as {client.user}")
    print("Commands synced")

# ------------------------
# SLASH COMMAND (FIXED)
# ------------------------
@tree.command(name="token_gen", description="Generate Auth token")
async def token_gen(interaction: discord.Interaction, username: str):
    global session

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

# ------------------------
# CLEAN SHUTDOWN HANDLING
# ------------------------
@client.event
async def on_disconnect():
    print("⚠️ Disconnected from Discord")

# ------------------------
# START BOT (IMPORTANT)
# ------------------------
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing in environment variables")

client.run(TOKEN)
