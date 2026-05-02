import discord
from discord import app_commands
import aiohttp
import os
import asyncio
import logging

async def main():
    await client.start(TOKEN)
    
TOKEN = os.getenv("DISCORD_TOKEN")
API_URL = "https://gunyahjohnvr.pythonanywhere.com/"

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

user_tokens = {}



async def presence_loop():
    while True:
        try:
            await client.change_presence(
                status=discord.Status.online,
                activity=discord.Game("API Online 🚀")
            )
        except Exception as e:
            print("Presence error:", e)

        await asyncio.sleep(30)


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

    try:
        await tree.sync()
        print("Commands synced")
    except Exception as e:
        print("Sync failed:", e)

    client.loop.create_task(presence_loop())


@client.event
async def on_resumed():
    print("🔄 Session resumed (no offline state)")

@client.event
async def on_disconnect():
    print("⚠️ Disconnected (reconnecting...)")

@tree.command(name="token_gen", description="Generate Auth Token")
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


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing in environment variables")

print("Starting bot...")
if __name__ == "__main__":
    asyncio.run(main())
