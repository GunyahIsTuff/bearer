import discord
from discord import app_commands
import requests
import os

TOKEN = os.getenv("DISCORD_TOKEN")
API_URL = "https://gunyahjohnvr.pythonanywhere.com/"

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

user_tokens = {}

@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user}")

@tree.command(name="Generate Token", description="Generate A Auth token For Gunyah Company")
async def Generate(interaction: discord.Interaction, username: str):
    try:
        res = requests.post(
            f"{API_URL}/token/generator",
            json={"username": username},
            timeout=10
        )

        data = res.json()

        if "token" in data:
            user_tokens[interaction.user.id] = data["token"]
            await interaction.response.send_message(
                f"✅ Token:\n```{data['token']}```",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"❌ {data}", ephemeral=True)

    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)

client.run(TOKEN)
