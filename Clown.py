
from threading import Thread
from flask import Flask
import sys, types, os

fake_audioop = types.ModuleType("audioop")

# stub out the functions discord.py tries to call
def _noop(*args, **kwargs):
    return None

fake_audioop.mul = _noop
fake_audioop.add = _noop
fake_audioop.bias = _noop
fake_audioop.lin2lin = _noop
fake_audioop.ratecv = _noop
fake_audioop.tomono = _noop
fake_audioop.tostereo = _noop
fake_audioop.reverse = _noop
fake_audioop.max = lambda data, width=None: 0
fake_audioop.avg = lambda data, width=None: 0

sys.modules["audioop"] = fake_audioop

import discord
from discord.ext import commands
TOKEN=os.getenv("TOKEN")
# ------------------- Flask Keepalive -------------------
sys.modules['audioop'] = types.ModuleType('audioop')
app = Flask(__name__)

@app.route('/')
def home():
    return "bot alive!", 200

def run_flask():
    # render loves using port 10000+ but whatever, this works everywhere else
    app.run(host="0.0.0.0", port=8080)

# ------------------- Discord Bot -------------------

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

TARGET_ID = 1255781402583105609
REACTION = "🤡"

@bot.event
async def on_ready():
    print(f"logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.id == bot.user.id:
        return

    if message.author.id == TARGET_ID:
        try:
            await message.add_reaction(REACTION)
        except Exception as e:
            print("failed to react:", e)

    await bot.process_commands(message)

# ------------------- Startup -------------------

if __name__ == "__main__":
    # start flask in background
    t = Thread(target=run_flask)
    t.start()

    # start discord bot
    bot.run(TOKEN)
