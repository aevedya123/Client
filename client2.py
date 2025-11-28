import sys, types, os
sys.modules['audioop'] = types.ModuleType('audioop')
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot alive!", 200

def run():
    port = int(os.getenv("PORT", 8080))
    print(f"[DEBUG] Flask keep-alive running on port {port}")
    try:
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        print(f"[ERROR] Flask failed to start: {e}")

def keep_alive():
    import threading
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()

keep_alive()
import re
import json
import types
import sys
import asyncio
from datetime import datetime, timezone
from threading import Thread
sys.modules['audioop'] = types.ModuleType("audioop")

import aiohttp
import discord
from discord import Embed
from flask import Flask
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GROUP_ID = os.getenv("SERVER_ID") or os.getenv("GROUP_ID")
ROBLOX_COOKIE = os.getenv("ROBLOX_COOKIE")

# Basic validation
if not DISCORD_TOKEN or not CHANNEL_ID or not GROUP_ID or not ROBLOX_COOKIE:
    print("Missing one or more required env vars: DISCORD_TOKEN, CHANNEL_ID, SERVER_ID (or GROUP_ID), ROBLOX_COOKIE")
    raise SystemExit(1)

try:
    CHANNEL_ID = int(CHANNEL_ID)
except Exception:
    print("CHANNEL_ID must be an integer.")
    raise SystemExit(1)
BASE_POLL_INTERVAL = 60
POSTED_FILE = "posted_links.json"
SHARE_REGEX = re.compile(r"https?://(?:www\.)?roblox\.com/share\?[^)\s\"'<>]+")
MAX_SEND_PER_CYCLE = 30
EMBED_BATCH_SIZE = 10
app = Flask("keepalive")

@app.route("/")
def index():
    return "SABRS Link Bot - alive"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_flask, daemon=True).start()

intents = discord.Intents.default()
client = discord.Client(intents=intents)

def load_posted():
    if not os.path.exists(POSTED_FILE):
        return set()
    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data)
    except Exception as e:
        print(f"[{datetime.now(timezone.utc)}] Failed to load posted file: {e}")
        return set()

def save_posted(s: set):
    try:
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(s)), f, indent=2)
    except Exception as e:
        print(f"[{datetime.now(timezone.utc)}] Failed to save posted file: {e}")
class RobloxRateLimit(Exception):
    pass

async def fetch_group_wall(session, limit=50):
    """
    Fetch group wall posts from Roblox using .ROBLOSECURITY cookie.
    Returns a list of post dicts on success, [] on non-200 (after logging),
    or raises RobloxRateLimit if a 429 is received.
    """
    url = f"https://groups.roblox.com/v2/groups/{GROUP_ID}/wall/posts?limit={limit}&sortOrder=Desc"
    headers = {
        "Cookie": f".ROBLOSECURITY={ROBLOX_COOKIE}",
        "User-Agent": "SABRS-LinkBot/1.0",
        "Accept": "application/json"
    }
    try:
        async with session.get(url, headers=headers, timeout=20) as resp:
            status = resp.status
            text_snip = (await resp.text())[:800]
            if status == 200:
                try:
                    j = await resp.json()
                except Exception as e:
                    print(f"[{datetime.now(timezone.utc)}] JSON decode error: {e}. Snippet: {text_snip}")
                    return []
                return j.get("data", []) or []
            elif status == 429:
                
                print(f"[{datetime.now(timezone.utc)}] Roblox rate-limited (429). Snippet: {text_snip}")
                raise RobloxRateLimit()
            else:
                print(f"[{datetime.now(timezone.utc)}] Roblox API returned {status}. Snippet: {text_snip}")
                return []
    except asyncio.TimeoutError:
        print(f"[{datetime.now(timezone.utc)}] Timeout fetching Roblox group wall.")
        return []
    except RobloxRateLimit:
        raise
    except Exception as e:
        print(f"[{datetime.now(timezone.utc)}] Exception fetching Roblox group wall: {e}")
        return []

def extract_share_links_from_text(text: str):
    if not text:
        return []
    return SHARE_REGEX.findall(text)

async def poll_and_post_loop():
    await client.wait_until_ready()
    posted = load_posted()
    print(f"[{datetime.now(timezone.utc)}] Loaded {len(posted)} posted keys.")

    backoff = 0
    async with aiohttp.ClientSession() as session:
        while not client.is_closed():
            try:
                if backoff > 0:
                    print(f"[{datetime.now(timezone.utc)}] Backing off for {backoff}s due to previous rate limit.")
                    await asyncio.sleep(backoff)

                posts = await fetch_group_wall(session, limit=50)

                new_items = []
                for post in reversed(posts):
                    post_id = str(post.get("id") or post.get("postId") or "")
                    body = post.get("body", "") or ""
                    links = extract_share_links_from_text(body)
                    for link in links:
                        key = f"{post_id}|{link}"
                        if key not in posted:
                            new_items.append((post_id, link, post.get("created")))

                if new_items:
                    # Limit to MAX_SEND_PER_CYCLE newest links
                    limited = new_items[-MAX_SEND_PER_CYCLE:]
                    links_only = [link for (_, link, _) in limited]

                    try:
                        channel = await client.fetch_channel(CHANNEL_ID)
                    except Exception as e:
                        print(f"[{datetime.now(timezone.utc)}] Failed to fetch channel {CHANNEL_ID}: {e}")
                        channel = None

                    if channel:
                        # Send in batches
                        for i in range(0, len(links_only), EMBED_BATCH_SIZE):
                            chunk = links_only[i:i + EMBED_BATCH_SIZE]
                            # Numbered hyperlinks with spacing
                            desc_lines = [f"{idx}. [Click here!]({link})" for idx, link in enumerate(chunk, start=1)]
                            desc = "\n\n".join(desc_lines)  # double newline for spacing

                            embed = discord.Embed(
                                title="🔗 New Roblox Scammer Private Server Links",
                                description=desc,
                                color=0x311B92,
                                timestamp=datetime.now(timezone.utc)
                            )
                            embed.set_footer(text="Made by SAB-RS | Hosted by Astryx's Trading/Raiding")
                            embed.set_image(url="https://pbs.twimg.com/media/GvwdBD4XQAAL-u0.jpg")  # replace with your image link

                            try:
                                await channel.send(embed=embed)
                                print(f"[{datetime.now(timezone.utc)}] Sent embed with {len(chunk)} link(s).")
                            except Exception as e:
                                print(f"[{datetime.now(timezone.utc)}] Failed to send embed: {e}")
                                continue

                            await asyncio.sleep(1.5)
                    else:
                        print(f"[{datetime.now(timezone.utc)}] Channel unavailable; skipping this round.")

                    for post_id, link, _ in limited:
                        posted.add(f"{post_id}|{link}")
                    save_posted(posted)
                    print(f"[{datetime.now(timezone.utc)}] Updated posted store (total {len(posted)}).")
                else:
                    print(f"[{datetime.now(timezone.utc)}] No new share links found.")

                backoff = 0
                await asyncio.sleep(BASE_POLL_INTERVAL)

            except RobloxRateLimit:
                backoff = backoff * 2 if backoff else max(60, BASE_POLL_INTERVAL)
                backoff = min(backoff, 3600)  # cap at 1 hour
                print(f"[{datetime.now(timezone.utc)}] Received 429 — backing off {backoff}s.")
                await asyncio.sleep(backoff)
            except Exception as e:
                print(f"[{datetime.now(timezone.utc)}] Unexpected error in poll loop: {e}")
                await asyncio.sleep(30)

@client.event
async def on_ready():
    print(f"[{datetime.now(timezone.utc)}] ✅ Logged in as {client.user} (ID: {client.user.id})")
def start_background_tasks():
    loop = asyncio.get_event_loop()
    
    loop.create_task(poll_and_post_loop())


@client.event
async def on_connect():
    
    try:
        start_background_tasks()
    except Exception:
        pass

# ---- Run bot ----
if __name__ == "__main__":
    try:
        client.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("Shutting down.")
