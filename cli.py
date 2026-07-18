import os
import sys

TEMPLATE = '''import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
import random
import sqlite3
import aiohttp
import json
import io
import re
from datetime import datetime, timedelta
from typing import Optional, Literal

# ==============================================================================
#  MAKEDISCBOT - THE ULTIMATE DISCORD.PY SNIPPET LIBRARY
#  Version 0.1.4 - The biggest single-file Discord bot template ever made.
#  Every command has a UI component. Copy, paste, customize.
# ==============================================================================

# ==============================================================================
# --- SECTION 1: BOT SETUP, INTENTS, AND SUBCLASS ---
# ==============================================================================
intents = discord.Intents.all()

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=commands.DefaultHelpCommand())
        self.session = None
        self.start_time = datetime.utcnow()
        self.afk_users = {}
        self.snipe_cache = {}
        self.counting_channels = {}
        self.starboard_threshold = 3

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        self.status_rotation.start()
        # Load cogs here if using them:
        # await self.load_extension("cogs.moderation")
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} slash command(s).")
        except Exception as e:
            print(f"Sync failed: {e}")

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

    @tasks.loop(minutes=10)
    async def status_rotation(self):
        statuses = [
            discord.Activity(type=discord.ActivityType.watching, name="over the server"),
            discord.Activity(type=discord.ActivityType.playing, name="with Python"),
            discord.Activity(type=discord.ActivityType.listening, name="/help"),
            discord.Activity(type=discord.ActivityType.competing, name="code battles"),
        ]
        await self.change_presence(activity=random.choice(statuses))

bot = MyBot()

# ==============================================================================
# --- SECTION 2: DATABASE SETUP (SQLite) ---
# ==============================================================================
conn = sqlite3.connect("bot_database.db")
db = conn.cursor()
db.execute("CREATE TABLE IF NOT EXISTS economy (user_id INTEGER PRIMARY KEY, wallet INTEGER DEFAULT 0, bank INTEGER DEFAULT 0)")
db.execute("CREATE TABLE IF NOT EXISTS levels (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1)")
db.execute("CREATE TABLE IF NOT EXISTS warnings (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, guild_id INTEGER, moderator_id INTEGER, reason TEXT, timestamp TEXT)")
db.execute("CREATE TABLE IF NOT EXISTS tags (guild_id INTEGER, name TEXT, content TEXT, author_id INTEGER, uses INTEGER DEFAULT 0, PRIMARY KEY (guild_id, name))")
db.execute("CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, channel_id INTEGER, reminder TEXT, remind_at TEXT)")
db.execute("CREATE TABLE IF NOT EXISTS suggestions (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER, suggestion TEXT, status TEXT DEFAULT 'pending', msg_id INTEGER)")
db.execute("CREATE TABLE IF NOT EXISTS starboard (guild_id INTEGER, msg_id INTEGER PRIMARY KEY, star_msg_id INTEGER, stars INTEGER)")
db.execute("CREATE TABLE IF NOT EXISTS confessions (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, confession TEXT)")
db.execute("CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item TEXT, quantity INTEGER DEFAULT 1, PRIMARY KEY(user_id, item))")
db.execute("CREATE TABLE IF NOT EXISTS dailystreak (user_id INTEGER PRIMARY KEY, last_claim TEXT, streak INTEGER DEFAULT 0)")
conn.commit()

def get_wallet(uid):
    db.execute("SELECT wallet, bank FROM economy WHERE user_id=?", (uid,))
    r = db.fetchone()
    return r if r else (0, 0)

def set_wallet(uid, wallet, bank):
    db.execute("INSERT OR REPLACE INTO economy VALUES (?,?,?)", (uid, wallet, bank))
    conn.commit()

def get_xp(uid):
    db.execute("SELECT xp, level FROM levels WHERE user_id=?", (uid,))
    r = db.fetchone()
    return r if r else (0, 1)

def set_xp(uid, xp, level):
    db.execute("INSERT OR REPLACE INTO levels VALUES (?,?,?)", (uid, xp, level))
    conn.commit()

# ==============================================================================
# --- SECTION 3: EVENTS ---
# ==============================================================================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

@bot.event
async def on_member_join(member):
    ch = member.guild.system_channel
    if ch:
        embed = discord.Embed(title="Welcome!", description=f"{member.mention} just joined! We now have {member.guild.member_count} members.", color=0x2ecc71)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")
        await ch.send(embed=embed)

@bot.event
async def on_member_remove(member):
    ch = member.guild.system_channel
    if ch:
        embed = discord.Embed(title="Goodbye!", description=f"{member.display_name} left the server.", color=0xe74c3c)
        await ch.send(embed=embed)

@bot.event
async def on_message_delete(message):
    if message.author and not message.author.bot:
        bot.snipe_cache[message.channel.id] = {"content": message.content, "author": str(message.author), "avatar": message.author.display_avatar.url, "time": datetime.utcnow()}

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:
        pass  # User joined voice
    elif before.channel is not None and after.channel is None:
        pass  # User left voice

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # --- AFK Check ---
    if message.author.id in bot.afk_users:
        del bot.afk_users[message.author.id]
        await message.reply("Welcome back! I removed your AFK status.", delete_after=5)
    for user in message.mentions:
        if user.id in bot.afk_users:
            await message.reply(f"{user.display_name} is AFK: {bot.afk_users[user.id]}", delete_after=5)

    # --- XP System ---
    xp, lvl = get_xp(message.author.id)
    xp += random.randint(5, 15)
    needed = lvl * 100
    if xp >= needed:
        xp -= needed
        lvl += 1
        embed = discord.Embed(description=f"GG {message.author.mention}, you just advanced to **Level {lvl}**!", color=0xf1c40f)
        await message.channel.send(embed=embed)
    set_xp(message.author.id, xp, lvl)

    # --- Counting Channel ---
    if message.channel.id in bot.counting_channels:
        try:
            num = int(message.content)
            expected = bot.counting_channels[message.channel.id] + 1
            if num == expected:
                bot.counting_channels[message.channel.id] = num
                await message.add_reaction("\\u2705")
            else:
                bot.counting_channels[message.channel.id] = 0
                await message.reply(f"Wrong! The next number was **{expected}**. Restarting from 1.")
        except ValueError:
            pass

    # --- Starboard ---
    # (handled in on_raw_reaction_add below)

    await bot.process_commands(message)

@bot.event
async def on_raw_reaction_add(payload):
    if str(payload.emoji) != "\\u2b50":
        return
    channel = bot.get_channel(payload.channel_id)
    if not channel:
        return
    message = await channel.fetch_message(payload.message_id)
    reaction = discord.utils.get(message.reactions, emoji="\\u2b50")
    if reaction and reaction.count >= bot.starboard_threshold:
        # Find or create starboard channel
        starboard_ch = discord.utils.get(message.guild.text_channels, name="starboard")
        if starboard_ch:
            db.execute("SELECT star_msg_id FROM starboard WHERE msg_id=?", (message.id,))
            existing = db.fetchone()
            embed = discord.Embed(description=message.content, color=0xf1c40f, timestamp=message.created_at)
            embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
            embed.add_field(name="Source", value=f"[Jump to message]({message.jump_url})")
            embed.set_footer(text=f"\\u2b50 {reaction.count}")
            if message.attachments:
                embed.set_image(url=message.attachments[0].url)
            if existing:
                try:
                    star_msg = await starboard_ch.fetch_message(existing[0])
                    await star_msg.edit(embed=embed)
                except discord.NotFound:
                    pass
            else:
                star_msg = await starboard_ch.send(embed=embed)
                db.execute("INSERT OR REPLACE INTO starboard VALUES (?,?,?,?)", (message.guild.id, message.id, star_msg.id, reaction.count))
                conn.commit()

# ==============================================================================
# --- SECTION 4: MODERATION COMMANDS (20+ commands) ---
# ==============================================================================
@bot.tree.command(name="ban", description="Bans a member from the server.")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    embed = discord.Embed(title="Member Banned", description=f"{member.mention} has been banned.\\nReason: {reason}", color=0xe74c3c)
    await member.ban(reason=reason)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="unban", description="Unbans a user by ID.")
@app_commands.checks.has_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str):
    user = await bot.fetch_user(int(user_id))
    await interaction.guild.unban(user)
    await interaction.response.send_message(f"Unbanned {user.name}.")

@bot.tree.command(name="kick", description="Kicks a member.")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await member.kick(reason=reason)
    embed = discord.Embed(title="Member Kicked", description=f"{member.mention} was kicked. Reason: {reason}", color=0xe67e22)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="timeout", description="Timeouts a member.")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout_cmd(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = None):
    await member.timeout(timedelta(minutes=minutes), reason=reason)
    await interaction.response.send_message(f"Timed out {member.mention} for {minutes} minutes.")

@bot.tree.command(name="untimeout", description="Removes timeout from a member.")
@app_commands.checks.has_permissions(moderate_members=True)
async def untimeout_cmd(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(f"Removed timeout from {member.mention}.")

@bot.tree.command(name="purge", description="Bulk deletes messages.")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int, member: discord.Member = None):
    await interaction.response.defer(ephemeral=True)
    def check(m):
        return member is None or m.author == member
    deleted = await interaction.channel.purge(limit=amount, check=check)
    await interaction.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)

@bot.tree.command(name="nuke", description="Clones and deletes the channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def nuke(interaction: discord.Interaction):
    ch = interaction.channel
    new = await ch.clone(reason="Nuke command")
    await ch.delete()
    await new.send("Channel nuked!")

@bot.tree.command(name="lock", description="Locks a channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("Channel locked.")

@bot.tree.command(name="unlock", description="Unlocks a channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message("Channel unlocked.")

@bot.tree.command(name="slowmode", description="Sets slowmode delay.")
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, seconds: int):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"Slowmode set to {seconds}s.")

@bot.tree.command(name="softban", description="Bans and unbans to purge messages.")
@app_commands.checks.has_permissions(ban_members=True)
async def softban(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    await member.ban(reason=reason, delete_message_days=7)
    await interaction.guild.unban(member)
    await interaction.response.send_message(f"Softbanned {member.mention}.")

@bot.tree.command(name="warn", description="Warns a user.")
@app_commands.checks.has_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    db.execute("INSERT INTO warnings (user_id, guild_id, moderator_id, reason, timestamp) VALUES (?,?,?,?,?)",
               (member.id, interaction.guild.id, interaction.user.id, reason, str(datetime.utcnow())))
    conn.commit()
    db.execute("SELECT COUNT(*) FROM warnings WHERE user_id=? AND guild_id=?", (member.id, interaction.guild.id))
    count = db.fetchone()[0]
    embed = discord.Embed(title="Warning Issued", color=0xf39c12)
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Total Warnings", value=str(count))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="warnings", description="Shows warnings for a user.")
async def warnings(interaction: discord.Interaction, member: discord.Member):
    db.execute("SELECT id, reason, timestamp FROM warnings WHERE user_id=? AND guild_id=?", (member.id, interaction.guild.id))
    rows = db.fetchall()
    if not rows:
        return await interaction.response.send_message(f"{member.display_name} has no warnings.", ephemeral=True)
    embed = discord.Embed(title=f"Warnings for {member.display_name}", color=0xf39c12)
    for row in rows[:25]:
        embed.add_field(name=f"ID: {row[0]}", value=f"{row[1]}\\n{row[2]}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clearwarnings", description="Clears all warnings for a user.")
@app_commands.checks.has_permissions(moderate_members=True)
async def clearwarnings(interaction: discord.Interaction, member: discord.Member):
    db.execute("DELETE FROM warnings WHERE user_id=? AND guild_id=?", (member.id, interaction.guild.id))
    conn.commit()
    await interaction.response.send_message(f"Cleared all warnings for {member.mention}.")

@bot.tree.command(name="nick", description="Changes a member's nickname.")
@app_commands.checks.has_permissions(manage_nicknames=True)
async def nick(interaction: discord.Interaction, member: discord.Member, nickname: str):
    await member.edit(nick=nickname)
    await interaction.response.send_message(f"Changed {member.mention}'s nickname to **{nickname}**.")

@bot.tree.command(name="addrole", description="Adds a role to a member.")
@app_commands.checks.has_permissions(manage_roles=True)
async def addrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.add_roles(role)
    await interaction.response.send_message(f"Added {role.mention} to {member.mention}.")

@bot.tree.command(name="removerole", description="Removes a role from a member.")
@app_commands.checks.has_permissions(manage_roles=True)
async def removerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    await interaction.response.send_message(f"Removed {role.mention} from {member.mention}.")

@bot.tree.command(name="mute", description="Mutes a member by adding a Muted role.")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not role:
        role = await interaction.guild.create_role(name="Muted")
        for ch in interaction.guild.channels:
            await ch.set_permissions(role, speak=False, send_messages=False)
    await member.add_roles(role, reason=reason)
    await interaction.response.send_message(f"Muted {member.mention}.")

@bot.tree.command(name="unmute", description="Unmutes a member.")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    role = discord.utils.get(interaction.guild.roles, name="Muted")
    if role and role in member.roles:
        await member.remove_roles(role)
        await interaction.response.send_message(f"Unmuted {member.mention}.")
    else:
        await interaction.response.send_message("User is not muted.", ephemeral=True)

# ==============================================================================
# --- SECTION 5: ECONOMY COMMANDS (15+ commands) ---
# ==============================================================================
@bot.tree.command(name="balance", description="Check wallet and bank balance.")
async def balance(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    w, b = get_wallet(target.id)
    embed = discord.Embed(title=f"{target.display_name}'s Balance", color=0xf1c40f)
    embed.add_field(name="Wallet", value=f"${w:,}")
    embed.add_field(name="Bank", value=f"${b:,}")
    embed.add_field(name="Total", value=f"${w+b:,}")
    embed.set_thumbnail(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Claim your daily reward!")
@app_commands.checks.cooldown(1, 86400)
async def daily(interaction: discord.Interaction):
    db.execute("SELECT last_claim, streak FROM dailystreak WHERE user_id=?", (interaction.user.id,))
    r = db.fetchone()
    now = datetime.utcnow()
    streak = 1
    if r:
        last = datetime.fromisoformat(r[0])
        diff = (now - last).total_seconds()
        if diff < 172800:  # within 48h
            streak = r[1] + 1
    bonus = min(streak * 50, 500)
    reward = 500 + bonus
    w, b = get_wallet(interaction.user.id)
    set_wallet(interaction.user.id, w + reward, b)
    db.execute("INSERT OR REPLACE INTO dailystreak VALUES (?,?,?)", (interaction.user.id, str(now), streak))
    conn.commit()
    embed = discord.Embed(title="Daily Reward!", description=f"You received **${reward:,}**!\\nStreak: **{streak}** days (+${bonus} bonus)", color=0x2ecc71)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="work", description="Work for coins.")
@app_commands.checks.cooldown(1, 3600)
async def work(interaction: discord.Interaction):
    jobs = ["programmer", "chef", "artist", "teacher", "streamer", "uber driver", "doctor", "janitor", "DJ", "astronaut"]
    earned = random.randint(100, 500)
    w, b = get_wallet(interaction.user.id)
    set_wallet(interaction.user.id, w + earned, b)
    await interaction.response.send_message(f"You worked as a **{random.choice(jobs)}** and earned **${earned:,}**!")

@bot.tree.command(name="beg", description="Beg for money.")
@app_commands.checks.cooldown(1, 60)
async def beg(interaction: discord.Interaction):
    if random.random() < 0.6:
        earned = random.randint(10, 100)
        w, b = get_wallet(interaction.user.id)
        set_wallet(interaction.user.id, w + earned, b)
        givers = ["A kind stranger", "Elon Musk", "A lost tourist", "Your mom", "Bill Gates"]
        await interaction.response.send_message(f"{random.choice(givers)} gave you **${earned}**.")
    else:
        await interaction.response.send_message("Nobody gave you anything. Try again later.")

@bot.tree.command(name="deposit", description="Deposit money into bank.")
async def deposit(interaction: discord.Interaction, amount: int):
    w, b = get_wallet(interaction.user.id)
    if amount <= 0 or amount > w:
        return await interaction.response.send_message("Invalid amount.", ephemeral=True)
    set_wallet(interaction.user.id, w - amount, b + amount)
    await interaction.response.send_message(f"Deposited **${amount:,}** into your bank.")

@bot.tree.command(name="withdraw", description="Withdraw money from bank.")
async def withdraw(interaction: discord.Interaction, amount: int):
    w, b = get_wallet(interaction.user.id)
    if amount <= 0 or amount > b:
        return await interaction.response.send_message("Invalid amount.", ephemeral=True)
    set_wallet(interaction.user.id, w + amount, b - amount)
    await interaction.response.send_message(f"Withdrew **${amount:,}** from your bank.")

@bot.tree.command(name="transfer", description="Send money to another user.")
async def transfer(interaction: discord.Interaction, member: discord.Member, amount: int):
    if member.bot or member == interaction.user:
        return await interaction.response.send_message("Can't transfer to that user.", ephemeral=True)
    w, b = get_wallet(interaction.user.id)
    if amount <= 0 or amount > w:
        return await interaction.response.send_message("Insufficient funds.", ephemeral=True)
    tw, tb = get_wallet(member.id)
    set_wallet(interaction.user.id, w - amount, b)
    set_wallet(member.id, tw + amount, tb)
    await interaction.response.send_message(f"Sent **${amount:,}** to {member.mention}.")

@bot.tree.command(name="rob", description="Attempt to rob another user.")
@app_commands.checks.cooldown(1, 7200)
async def rob(interaction: discord.Interaction, member: discord.Member):
    if member.bot or member == interaction.user:
        return await interaction.response.send_message("Can't rob them!", ephemeral=True)
    tw, _ = get_wallet(member.id)
    if tw < 100:
        return await interaction.response.send_message("They don't have enough to rob.", ephemeral=True)
    w, b = get_wallet(interaction.user.id)
    if random.random() < 0.5:
        stolen = int(tw * random.uniform(0.1, 0.4))
        set_wallet(member.id, tw - stolen, _)
        set_wallet(interaction.user.id, w + stolen, b)
        await interaction.response.send_message(f"You stole **${stolen:,}** from {member.mention}!")
    else:
        fine = random.randint(100, 300)
        set_wallet(interaction.user.id, w - fine, b)
        await interaction.response.send_message(f"You got caught and paid a **${fine}** fine!")

@bot.tree.command(name="slots", description="Play the slot machine!")
async def slots(interaction: discord.Interaction, bet: int):
    w, b = get_wallet(interaction.user.id)
    if bet <= 0 or bet > w:
        return await interaction.response.send_message("Invalid bet.", ephemeral=True)
    emojis = ["cherry", "lemon", "seven", "diamond", "bell"]
    result = [random.choice(emojis) for _ in range(3)]
    display = " | ".join(result)
    if result[0] == result[1] == result[2]:
        winnings = bet * 10
        set_wallet(interaction.user.id, w + winnings, b)
        await interaction.response.send_message(f"[ {display} ]\\nJACKPOT! You won **${winnings:,}**!")
    elif result[0] == result[1] or result[1] == result[2]:
        winnings = bet * 2
        set_wallet(interaction.user.id, w + winnings, b)
        await interaction.response.send_message(f"[ {display} ]\\nTwo in a row! Won **${winnings:,}**!")
    else:
        set_wallet(interaction.user.id, w - bet, b)
        await interaction.response.send_message(f"[ {display} ]\\nYou lost **${bet:,}**.")

@bot.tree.command(name="coinflip", description="Gamble on a coin flip!")
async def coinflip(interaction: discord.Interaction, choice: Literal["heads", "tails"], bet: int):
    w, b = get_wallet(interaction.user.id)
    if bet <= 0 or bet > w:
        return await interaction.response.send_message("Invalid bet.", ephemeral=True)
    result = random.choice(["heads", "tails"])
    if result == choice:
        set_wallet(interaction.user.id, w + bet, b)
        await interaction.response.send_message(f"It was **{result}**! You won **${bet:,}**!")
    else:
        set_wallet(interaction.user.id, w - bet, b)
        await interaction.response.send_message(f"It was **{result}**. You lost **${bet:,}**.")

@bot.tree.command(name="leaderboard", description="Shows the richest users.")
async def leaderboard(interaction: discord.Interaction):
    db.execute("SELECT user_id, wallet+bank as total FROM economy ORDER BY total DESC LIMIT 10")
    rows = db.fetchall()
    embed = discord.Embed(title="Leaderboard - Richest Users", color=0xf1c40f)
    for i, (uid, total) in enumerate(rows, 1):
        user = bot.get_user(uid)
        name = user.display_name if user else f"User {uid}"
        embed.add_field(name=f"#{i} {name}", value=f"${total:,}", inline=False)
    await interaction.response.send_message(embed=embed)

# ==============================================================================
# --- SECTION 6: SHOP & INVENTORY ---
# ==============================================================================
SHOP_ITEMS = {"fishing_rod": 500, "laptop": 2000, "crown": 10000, "shield": 1500, "potion": 200, "sword": 3000}

@bot.tree.command(name="shop", description="View the item shop.")
async def shop(interaction: discord.Interaction):
    embed = discord.Embed(title="Item Shop", color=0x3498db)
    for item, price in SHOP_ITEMS.items():
        embed.add_field(name=item.replace("_", " ").title(), value=f"${price:,}", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="buy", description="Buy an item from the shop.")
async def buy(interaction: discord.Interaction, item: str):
    item = item.lower().replace(" ", "_")
    if item not in SHOP_ITEMS:
        return await interaction.response.send_message("Item not found.", ephemeral=True)
    price = SHOP_ITEMS[item]
    w, b = get_wallet(interaction.user.id)
    if w < price:
        return await interaction.response.send_message("Not enough money.", ephemeral=True)
    set_wallet(interaction.user.id, w - price, b)
    db.execute("INSERT INTO inventory VALUES (?,?,1) ON CONFLICT(user_id, item) DO UPDATE SET quantity=quantity+1", (interaction.user.id, item))
    conn.commit()
    await interaction.response.send_message(f"Bought **{item.replace('_',' ').title()}** for **${price:,}**!")

@bot.tree.command(name="inventory", description="View your inventory.")
async def inventory_cmd(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    db.execute("SELECT item, quantity FROM inventory WHERE user_id=?", (target.id,))
    rows = db.fetchall()
    if not rows:
        return await interaction.response.send_message(f"{target.display_name} has no items.", ephemeral=True)
    embed = discord.Embed(title=f"{target.display_name}'s Inventory", color=0x9b59b6)
    for item, qty in rows:
        embed.add_field(name=item.replace("_", " ").title(), value=f"x{qty}", inline=True)
    await interaction.response.send_message(embed=embed)

# ==============================================================================
# --- SECTION 7: FUN COMMANDS (25+ commands) ---
# ==============================================================================
@bot.tree.command(name="8ball", description="Ask the magic 8-ball.")
async def eightball(interaction: discord.Interaction, question: str):
    answers = ["Yes", "No", "Maybe", "Absolutely!", "Definitely not", "Ask again later",
               "Without a doubt", "Very doubtful", "Most likely", "Don't count on it",
               "It is certain", "My sources say no", "Outlook good", "Reply hazy, try again"]
    embed = discord.Embed(title="Magic 8-Ball", color=0x9b59b6)
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=random.choice(answers), inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="dice", description="Roll dice.")
async def dice(interaction: discord.Interaction, sides: int = 6, count: int = 1):
    results = [random.randint(1, sides) for _ in range(min(count, 20))]
    await interaction.response.send_message(f"Rolled {count}d{sides}: {results} (Total: {sum(results)})")

@bot.tree.command(name="rps", description="Rock Paper Scissors!")
async def rps(interaction: discord.Interaction, choice: Literal["rock", "paper", "scissors"]):
    bot_choice = random.choice(["rock", "paper", "scissors"])
    wins = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    if choice == bot_choice:
        result = "Tie!"
    elif wins[choice] == bot_choice:
        result = "You win!"
    else:
        result = "You lose!"
    await interaction.response.send_message(f"You: {choice} | Bot: {bot_choice} | **{result}**")

@bot.tree.command(name="choose", description="Bot picks one of your options.")
async def choose(interaction: discord.Interaction, options: str):
    opts = [o.strip() for o in options.split(",")]
    await interaction.response.send_message(f"I choose: **{random.choice(opts)}**")

@bot.tree.command(name="reverse", description="Reverses text.")
async def reverse(interaction: discord.Interaction, text: str):
    await interaction.response.send_message(text[::-1])

@bot.tree.command(name="mock", description="mOcKs YoUr TeXt.")
async def mock(interaction: discord.Interaction, text: str):
    result = "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(text))
    await interaction.response.send_message(result)

@bot.tree.command(name="emojify", description="Converts text to emoji letters.")
async def emojify(interaction: discord.Interaction, text: str):
    result = " ".join(f":regional_indicator_{c}:" if c.isalpha() else c for c in text.lower())
    await interaction.response.send_message(result)

@bot.tree.command(name="ascii", description="Converts text to ASCII art (simple).")
async def ascii_art(interaction: discord.Interaction, text: str):
    big = text.upper()[:20]
    await interaction.response.send_message(f"```\\n{big}\\n```")

@bot.tree.command(name="rate", description="Rates something out of 10.")
async def rate(interaction: discord.Interaction, thing: str):
    await interaction.response.send_message(f"I rate **{thing}** a **{random.randint(0,10)}/10**!")

@bot.tree.command(name="ship", description="Ship two users together.")
async def ship(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
    percentage = random.randint(0, 100)
    bar = "\\u2764\\ufe0f" * (percentage // 10) + "\\U0001f5a4" * (10 - percentage // 10)
    embed = discord.Embed(title="Love Calculator", description=f"{user1.mention} x {user2.mention}\\n\\n{bar} **{percentage}%**", color=0xe91e63)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pp", description="PP size command (meme).")
async def pp(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    size = "=" * random.randint(1, 15)
    await interaction.response.send_message(f"{target.display_name}'s PP size:\\n8{size}D")

@bot.tree.command(name="howgay", description="How gay is someone (meme).")
async def howgay(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    pct = random.randint(0, 100)
    await interaction.response.send_message(f"**{target.display_name}** is **{pct}%** gay :rainbow_flag:")

@bot.tree.command(name="iq", description="Check someone's IQ (meme).")
async def iq(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    score = random.randint(1, 200)
    await interaction.response.send_message(f"**{target.display_name}**'s IQ is **{score}**!")

@bot.tree.command(name="fact", description="Random fun fact.")
async def fact(interaction: discord.Interaction):
    facts = [
        "Honey never spoils.", "A group of flamingos is called a 'flamboyance'.",
        "Octopuses have three hearts.", "Bananas are berries, but strawberries are not.",
        "A day on Venus is longer than a year on Venus.", "Cows have best friends.",
        "Sharks are older than trees.", "There are more stars than grains of sand on Earth."
    ]
    await interaction.response.send_message(f"**Fun Fact:** {random.choice(facts)}")

@bot.tree.command(name="joke", description="Tells a random joke.")
async def joke(interaction: discord.Interaction):
    jokes = [
        ("Why don't scientists trust atoms?", "Because they make up everything!"),
        ("Why did the scarecrow win an award?", "He was outstanding in his field!"),
        ("Why don't eggs tell jokes?", "They'd crack each other up!"),
        ("What do you call a fake noodle?", "An impasta!"),
        ("Why did the bicycle fall over?", "It was two-tired!"),
    ]
    q, a = random.choice(jokes)
    await interaction.response.send_message(f"**{q}**\\n||{a}||")

@bot.tree.command(name="roast", description="Roasts someone (lighthearted).")
async def roast(interaction: discord.Interaction, member: discord.Member):
    roasts = [
        f"{member.mention}, you bring everyone so much joy... when you leave.",
        f"If {member.mention} was any more basic, they'd be a pH 14.",
        f"{member.mention}, your code has more bugs than a rainforest.",
        f"I'd explain it to you {member.mention}, but I left my crayons at home.",
        f"{member.mention}, you're the reason the gene pool needs a lifeguard.",
    ]
    await interaction.response.send_message(random.choice(roasts))

@bot.tree.command(name="compliment", description="Compliments someone.")
async def compliment(interaction: discord.Interaction, member: discord.Member):
    comps = [
        f"{member.mention}, you're an amazing person!",
        f"{member.mention}, your smile lights up the server!",
        f"{member.mention}, you're more fun than bubble wrap!",
        f"If {member.mention} were a vegetable, they'd be a cute-cumber!",
    ]
    await interaction.response.send_message(random.choice(comps))

@bot.tree.command(name="wanted", description="Creates a wanted poster (text).")
async def wanted(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    embed = discord.Embed(title="WANTED", description=f"**{target.display_name}**\\nReward: ${random.randint(1000,99999):,}", color=0xe67e22)
    embed.set_image(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="hack", description="Fake hacks a user (meme).")
async def hack(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer()
    steps = [
        f"Hacking {member.display_name}...",
        "Finding Discord login...",
        f"Email found: totally{member.id}@fake.com",
        "Selling data to the dark web...",
        f"Successfully hacked {member.display_name}! (jk, this is all fake)"
    ]
    msg = await interaction.followup.send(steps[0])
    for step in steps[1:]:
        await asyncio.sleep(1.5)
        await msg.edit(content=step)

# ==============================================================================
# --- SECTION 8: UTILITY COMMANDS (20+ commands) ---
# ==============================================================================
@bot.tree.command(name="ping", description="Shows bot latency.")
async def ping(interaction: discord.Interaction):
    embed = discord.Embed(title="Pong!", description=f"Latency: **{round(bot.latency * 1000)}ms**", color=0x3498db)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="uptime", description="Shows how long the bot has been running.")
async def uptime(interaction: discord.Interaction):
    delta = datetime.utcnow() - bot.start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    await interaction.response.send_message(f"Uptime: **{hours}h {minutes}m {seconds}s**")

@bot.tree.command(name="avatar", description="Gets a user's avatar.")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    embed = discord.Embed(title=f"{target.display_name}'s Avatar", color=target.color)
    embed.set_image(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="banner", description="Gets a user's banner (if they have one).")
async def banner(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    user = await bot.fetch_user(target.id)
    if user.banner:
        embed = discord.Embed(title=f"{target.display_name}'s Banner", color=target.color)
        embed.set_image(url=user.banner.url)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("This user has no banner.", ephemeral=True)

@bot.tree.command(name="userinfo", description="Detailed user info.")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    roles = [r.mention for r in target.roles[1:][:20]]
    embed = discord.Embed(title=f"User Info - {target}", color=target.color)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="ID", value=target.id)
    embed.add_field(name="Nickname", value=target.nick or "None")
    embed.add_field(name="Bot", value=str(target.bot))
    embed.add_field(name="Created", value=discord.utils.format_dt(target.created_at, "R"))
    embed.add_field(name="Joined", value=discord.utils.format_dt(target.joined_at, "R"))
    embed.add_field(name=f"Roles ({len(target.roles)-1})", value=" ".join(roles) if roles else "None", inline=False)
    embed.add_field(name="Top Role", value=target.top_role.mention)
    embed.add_field(name="Boosting", value=str(target.premium_since is not None))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Detailed server info.")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"Server Info - {guild.name}", color=0x3498db)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown")
    embed.add_field(name="Members", value=f"{guild.member_count}")
    embed.add_field(name="Channels", value=f"{len(guild.text_channels)} text, {len(guild.voice_channels)} voice")
    embed.add_field(name="Roles", value=str(len(guild.roles)))
    embed.add_field(name="Emojis", value=str(len(guild.emojis)))
    embed.add_field(name="Boosts", value=f"{guild.premium_subscription_count} (Level {guild.premium_tier})")
    embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, "R"))
    embed.add_field(name="Verification", value=str(guild.verification_level))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="roleinfo", description="Info about a role.")
async def roleinfo(interaction: discord.Interaction, role: discord.Role):
    embed = discord.Embed(title=f"Role: {role.name}", color=role.color)
    embed.add_field(name="ID", value=role.id)
    embed.add_field(name="Color", value=str(role.color))
    embed.add_field(name="Members", value=str(len(role.members)))
    embed.add_field(name="Position", value=str(role.position))
    embed.add_field(name="Mentionable", value=str(role.mentionable))
    embed.add_field(name="Hoisted", value=str(role.hoist))
    embed.add_field(name="Created", value=discord.utils.format_dt(role.created_at, "R"))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="channelinfo", description="Info about a channel.")
async def channelinfo(interaction: discord.Interaction, channel: discord.TextChannel = None):
    ch = channel or interaction.channel
    embed = discord.Embed(title=f"Channel: #{ch.name}", color=0x3498db)
    embed.add_field(name="ID", value=ch.id)
    embed.add_field(name="Topic", value=ch.topic or "None")
    embed.add_field(name="Category", value=ch.category.name if ch.category else "None")
    embed.add_field(name="Slowmode", value=f"{ch.slowmode_delay}s")
    embed.add_field(name="NSFW", value=str(ch.is_nsfw()))
    embed.add_field(name="Created", value=discord.utils.format_dt(ch.created_at, "R"))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="membercount", description="Shows member count.")
async def membercount(interaction: discord.Interaction):
    guild = interaction.guild
    bots = sum(1 for m in guild.members if m.bot)
    humans = guild.member_count - bots
    embed = discord.Embed(title="Member Count", color=0x3498db)
    embed.add_field(name="Total", value=guild.member_count)
    embed.add_field(name="Humans", value=humans)
    embed.add_field(name="Bots", value=bots)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="invite", description="Get the bot's invite link.")
async def invite_cmd(interaction: discord.Interaction):
    link = discord.utils.oauth_url(bot.user.id, permissions=discord.Permissions.administrator())
    await interaction.response.send_message(f"[Invite me!]({link})", ephemeral=True)

@bot.tree.command(name="afk", description="Set your AFK status.")
async def afk(interaction: discord.Interaction, reason: str = "AFK"):
    bot.afk_users[interaction.user.id] = reason
    await interaction.response.send_message(f"Set your AFK: **{reason}**")

@bot.tree.command(name="snipe", description="Shows the last deleted message.")
async def snipe(interaction: discord.Interaction):
    data = bot.snipe_cache.get(interaction.channel.id)
    if not data:
        return await interaction.response.send_message("Nothing to snipe!", ephemeral=True)
    embed = discord.Embed(description=data["content"], color=0xe74c3c, timestamp=data["time"])
    embed.set_author(name=data["author"], icon_url=data["avatar"])
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="poll", description="Creates a poll.")
async def poll(interaction: discord.Interaction, question: str, option1: str, option2: str, option3: str = None, option4: str = None):
    options = [o for o in [option1, option2, option3, option4] if o]
    emojis = ["1\\u20e3", "2\\u20e3", "3\\u20e3", "4\\u20e3"]
    desc = "\\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options))
    embed = discord.Embed(title=f"Poll: {question}", description=desc, color=0x3498db)
    await interaction.response.send_message("Poll created!", ephemeral=True)
    msg = await interaction.channel.send(embed=embed)
    for i in range(len(options)):
        await msg.add_reaction(emojis[i])

@bot.tree.command(name="remind", description="Sets a reminder.")
async def remind(interaction: discord.Interaction, minutes: int, reminder: str):
    await interaction.response.send_message(f"I'll remind you in {minutes} minutes!")
    await asyncio.sleep(minutes * 60)
    await interaction.channel.send(f"{interaction.user.mention} Reminder: **{reminder}**")

@bot.tree.command(name="timer", description="Sets a countdown timer.")
async def timer(interaction: discord.Interaction, seconds: int):
    if seconds > 600:
        return await interaction.response.send_message("Max 600 seconds.", ephemeral=True)
    await interaction.response.send_message(f"Timer set for {seconds} seconds!")
    await asyncio.sleep(seconds)
    await interaction.channel.send(f"{interaction.user.mention} Timer is up!")

@bot.tree.command(name="math", description="Calculate a math expression.")
async def math_cmd(interaction: discord.Interaction, expression: str):
    allowed = set("0123456789+-*/().% ")
    if not all(c in allowed for c in expression):
        return await interaction.response.send_message("Invalid expression.", ephemeral=True)
    try:
        result = eval(expression)
        await interaction.response.send_message(f"`{expression}` = **{result}**")
    except Exception:
        await interaction.response.send_message("Error in expression.", ephemeral=True)

@bot.tree.command(name="color", description="Shows info about a hex color.")
async def color_cmd(interaction: discord.Interaction, hex_code: str):
    hex_code = hex_code.strip("#")
    try:
        color = int(hex_code, 16)
        embed = discord.Embed(title=f"#{hex_code}", color=color)
        embed.add_field(name="RGB", value=f"({color >> 16}, {(color >> 8) & 0xFF}, {color & 0xFF})")
        await interaction.response.send_message(embed=embed)
    except ValueError:
        await interaction.response.send_message("Invalid hex color.", ephemeral=True)

@bot.tree.command(name="embed_builder", description="Creates a custom embed.")
async def embed_builder(interaction: discord.Interaction, title: str, description: str, color: str = "3498db"):
    try:
        c_int = int(color.strip("#"), 16)
    except ValueError:
        c_int = 0x3498db
    embed = discord.Embed(title=title, description=description, color=c_int)
    embed.set_footer(text=f"Created by {interaction.user}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="servericon", description="Gets the server icon.")
async def servericon(interaction: discord.Interaction):
    if interaction.guild.icon:
        embed = discord.Embed(title=f"{interaction.guild.name} Icon")
        embed.set_image(url=interaction.guild.icon.url)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("This server has no icon.", ephemeral=True)

@bot.tree.command(name="firstmsg", description="Gets the first message in this channel.")
async def firstmsg(interaction: discord.Interaction):
    await interaction.response.defer()
    async for msg in interaction.channel.history(limit=1, oldest_first=True):
        embed = discord.Embed(description=msg.content, timestamp=msg.created_at, color=0x3498db)
        embed.set_author(name=str(msg.author), icon_url=msg.author.display_avatar.url)
        embed.add_field(name="Jump", value=f"[Click here]({msg.jump_url})")
        await interaction.followup.send(embed=embed)

# ==============================================================================
# --- SECTION 9: TICKET SYSTEM (Full) ---
# ==============================================================================
class CloseTicketBtn(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_forever")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.delete(reason="Ticket closed")

class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="General Support", emoji="\\u2753", value="general"),
            discord.SelectOption(label="Bug Report", emoji="\\U0001f41b", value="bug"),
            discord.SelectOption(label="Suggestion", emoji="\\U0001f4a1", value="suggestion"),
            discord.SelectOption(label="Appeal", emoji="\\u2696\\ufe0f", value="appeal"),
            discord.SelectOption(label="Partnership", emoji="\\U0001f91d", value="partnership"),
        ]
        super().__init__(placeholder="Select ticket category...", options=options, custom_id="ticket_category")

    async def callback(self, interaction: discord.Interaction):
        cat = discord.utils.get(interaction.guild.categories, name="Tickets")
        if not cat:
            cat = await interaction.guild.create_category("Tickets")
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        ch = await interaction.guild.create_text_channel(f"{self.values[0]}-{interaction.user.name}", category=cat, overwrites=overwrites)
        embed = discord.Embed(title=f"Ticket: {self.values[0].title()}", description=f"{interaction.user.mention}, support will be with you shortly.", color=0x3498db)
        await ch.send(embed=embed, view=CloseTicketBtn())
        await interaction.response.send_message(f"Ticket opened: {ch.mention}", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

@bot.tree.command(name="ticket_setup", description="Admin: Create the ticket panel.")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_setup(interaction: discord.Interaction):
    embed = discord.Embed(title="Support Tickets", description="Select a category below to open a ticket.", color=0x3498db)
    await interaction.response.send_message(embed=embed, view=TicketView())

# ==============================================================================
# --- SECTION 10: GIVEAWAY SYSTEM ---
# ==============================================================================
@bot.tree.command(name="gstart", description="Starts a giveaway.")
@app_commands.checks.has_permissions(manage_guild=True)
async def gstart(interaction: discord.Interaction, prize: str, minutes: int, winners: int = 1):
    embed = discord.Embed(title="GIVEAWAY!", description=f"Prize: **{prize}**\\nWinners: **{winners}**\\nEnds: {minutes} minutes\\nReact with \\U0001f389 to enter!", color=0xf1c40f)
    await interaction.response.send_message("Giveaway started!", ephemeral=True)
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("\\U0001f389")
    await asyncio.sleep(minutes * 60)
    new_msg = await interaction.channel.fetch_message(msg.id)
    reaction = discord.utils.get(new_msg.reactions, emoji="\\U0001f389")
    users = [u async for u in reaction.users() if not u.bot]
    if users:
        chosen = random.sample(users, min(winners, len(users)))
        mentions = ", ".join(w.mention for w in chosen)
        await interaction.channel.send(f"Congratulations {mentions}! You won **{prize}**!")
    else:
        await interaction.channel.send("No one entered the giveaway.")

# ==============================================================================
# --- SECTION 11: TAG / CUSTOM COMMAND SYSTEM ---
# ==============================================================================
@bot.tree.command(name="tag_create", description="Creates a tag.")
async def tag_create(interaction: discord.Interaction, name: str, content: str):
    try:
        db.execute("INSERT INTO tags VALUES (?,?,?,?,0)", (interaction.guild.id, name.lower(), content, interaction.user.id))
        conn.commit()
        await interaction.response.send_message(f"Tag `{name}` created!")
    except sqlite3.IntegrityError:
        await interaction.response.send_message("Tag already exists.", ephemeral=True)

@bot.tree.command(name="tag", description="Sends a tag.")
async def tag_get(interaction: discord.Interaction, name: str):
    db.execute("SELECT content FROM tags WHERE guild_id=? AND name=?", (interaction.guild.id, name.lower()))
    r = db.fetchone()
    if r:
        db.execute("UPDATE tags SET uses=uses+1 WHERE guild_id=? AND name=?", (interaction.guild.id, name.lower()))
        conn.commit()
        await interaction.response.send_message(r[0])
    else:
        await interaction.response.send_message("Tag not found.", ephemeral=True)

@bot.tree.command(name="tag_delete", description="Deletes a tag.")
async def tag_delete(interaction: discord.Interaction, name: str):
    db.execute("DELETE FROM tags WHERE guild_id=? AND name=? AND author_id=?", (interaction.guild.id, name.lower(), interaction.user.id))
    conn.commit()
    await interaction.response.send_message(f"Tag `{name}` deleted (if it existed and you owned it).")

@bot.tree.command(name="tag_list", description="Lists all tags in this server.")
async def tag_list(interaction: discord.Interaction):
    db.execute("SELECT name, uses FROM tags WHERE guild_id=? ORDER BY uses DESC", (interaction.guild.id,))
    rows = db.fetchall()
    if not rows:
        return await interaction.response.send_message("No tags in this server.", ephemeral=True)
    embed = discord.Embed(title="Server Tags", color=0x3498db)
    for name, uses in rows[:25]:
        embed.add_field(name=name, value=f"{uses} uses", inline=True)
    await interaction.response.send_message(embed=embed)

# ==============================================================================
# --- SECTION 12: SUGGESTION SYSTEM ---
# ==============================================================================
class SuggestionButtons(discord.ui.View):
    def __init__(self, suggestion_id):
        super().__init__(timeout=None)
        self.suggestion_id = suggestion_id

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="approve_sug")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("No permission.", ephemeral=True)
        db.execute("UPDATE suggestions SET status='approved' WHERE id=?", (self.suggestion_id,))
        conn.commit()
        embed = interaction.message.embeds[0]
        embed.color = 0x2ecc71
        embed.set_footer(text=f"Approved by {interaction.user}")
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message("Suggestion approved!", ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="deny_sug")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("No permission.", ephemeral=True)
        db.execute("UPDATE suggestions SET status='denied' WHERE id=?", (self.suggestion_id,))
        conn.commit()
        embed = interaction.message.embeds[0]
        embed.color = 0xe74c3c
        embed.set_footer(text=f"Denied by {interaction.user}")
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message("Suggestion denied!", ephemeral=True)

@bot.tree.command(name="suggest", description="Submit a suggestion.")
async def suggest(interaction: discord.Interaction, suggestion: str):
    db.execute("INSERT INTO suggestions (guild_id, user_id, suggestion) VALUES (?,?,?)",
               (interaction.guild.id, interaction.user.id, suggestion))
    conn.commit()
    sid = db.lastrowid
    embed = discord.Embed(title=f"Suggestion #{sid}", description=suggestion, color=0xf39c12)
    embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
    embed.set_footer(text="Pending review")
    await interaction.response.send_message("Suggestion submitted!", ephemeral=True)
    msg = await interaction.channel.send(embed=embed, view=SuggestionButtons(sid))
    await msg.add_reaction("\\U0001f44d")
    await msg.add_reaction("\\U0001f44e")

# ==============================================================================
# --- SECTION 13: CONFESSION SYSTEM ---
# ==============================================================================
class ConfessionModal(discord.ui.Modal, title="Anonymous Confession"):
    confession_text = discord.ui.TextInput(label="Your Confession", style=discord.TextStyle.paragraph, placeholder="Type your confession here...", required=True, max_length=2000)

    async def on_submit(self, interaction: discord.Interaction):
        db.execute("INSERT INTO confessions (guild_id, confession) VALUES (?,?)", (interaction.guild.id, self.confession_text.value))
        conn.commit()
        cid = db.lastrowid
        embed = discord.Embed(title=f"Confession #{cid}", description=self.confession_text.value, color=0x2f3136)
        embed.set_footer(text="Anonymous")
        await interaction.response.send_message("Confession submitted!", ephemeral=True)
        await interaction.channel.send(embed=embed)

@bot.tree.command(name="confess", description="Submit an anonymous confession.")
async def confess(interaction: discord.Interaction):
    await interaction.response.send_modal(ConfessionModal())

# ==============================================================================
# --- SECTION 14: REACTION ROLES ---
# ==============================================================================
class ReactionRoleDropdown(discord.ui.Select):
    def __init__(self, roles):
        options = [discord.SelectOption(label=r.name, value=str(r.id)) for r in roles[:25]]
        super().__init__(placeholder="Pick a role...", options=options, custom_id="rr_dropdown")

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(int(self.values[0]))
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"Removed **{role.name}**.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"Added **{role.name}**.", ephemeral=True)

class ReactionRoleView(discord.ui.View):
    def __init__(self, roles):
        super().__init__(timeout=None)
        self.add_item(ReactionRoleDropdown(roles))

@bot.tree.command(name="reactionroles", description="Admin: Create a reaction role panel.")
@app_commands.checks.has_permissions(administrator=True)
async def reaction_roles(interaction: discord.Interaction, role1: discord.Role, role2: discord.Role = None, role3: discord.Role = None, role4: discord.Role = None, role5: discord.Role = None):
    roles = [r for r in [role1, role2, role3, role4, role5] if r]
    embed = discord.Embed(title="Self-Assignable Roles", description="Pick a role from the dropdown below!", color=0x3498db)
    await interaction.response.send_message(embed=embed, view=ReactionRoleView(roles))

# ==============================================================================
# --- SECTION 15: VOICE COMMANDS ---
# ==============================================================================
@bot.tree.command(name="vjoin", description="Joins voice channel.")
async def vjoin(interaction: discord.Interaction):
    if not interaction.user.voice:
        return await interaction.response.send_message("You are not in a voice channel.", ephemeral=True)
    await interaction.user.voice.channel.connect()
    await interaction.response.send_message(f"Joined **{interaction.user.voice.channel.name}**.")

@bot.tree.command(name="vleave", description="Leaves voice channel.")
async def vleave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("Disconnected.")
    else:
        await interaction.response.send_message("Not in a voice channel.", ephemeral=True)

@bot.tree.command(name="vdeafen", description="Server deafens a member.")
@app_commands.checks.has_permissions(deafen_members=True)
async def vdeafen(interaction: discord.Interaction, member: discord.Member):
    await member.edit(deafen=True)
    await interaction.response.send_message(f"Deafened {member.mention}.")

@bot.tree.command(name="vmute", description="Server mutes a member.")
@app_commands.checks.has_permissions(mute_members=True)
async def vmute(interaction: discord.Interaction, member: discord.Member):
    await member.edit(mute=True)
    await interaction.response.send_message(f"Muted {member.mention}.")

@bot.tree.command(name="vmove", description="Moves a member to another voice channel.")
@app_commands.checks.has_permissions(move_members=True)
async def vmove(interaction: discord.Interaction, member: discord.Member, channel: discord.VoiceChannel):
    await member.move_to(channel)
    await interaction.response.send_message(f"Moved {member.mention} to **{channel.name}**.")

@bot.tree.command(name="vdisconnect", description="Disconnects a member from voice.")
@app_commands.checks.has_permissions(move_members=True)
async def vdisconnect(interaction: discord.Interaction, member: discord.Member):
    await member.move_to(None)
    await interaction.response.send_message(f"Disconnected {member.mention} from voice.")

# ==============================================================================
# --- SECTION 16: LEVEL / RANK COMMANDS ---
# ==============================================================================
@bot.tree.command(name="rank", description="Shows your level and XP.")
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    xp, lvl = get_xp(target.id)
    needed = lvl * 100
    bar_filled = int((xp / needed) * 10) if needed > 0 else 0
    bar = "\\u2588" * bar_filled + "\\u2591" * (10 - bar_filled)
    embed = discord.Embed(title=f"{target.display_name}'s Rank", color=0x1abc9c)
    embed.add_field(name="Level", value=str(lvl))
    embed.add_field(name="XP", value=f"{xp}/{needed}")
    embed.add_field(name="Progress", value=f"`{bar}`", inline=False)
    embed.set_thumbnail(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="xp_leaderboard", description="XP leaderboard.")
async def xp_leaderboard(interaction: discord.Interaction):
    db.execute("SELECT user_id, level, xp FROM levels ORDER BY level DESC, xp DESC LIMIT 10")
    rows = db.fetchall()
    embed = discord.Embed(title="XP Leaderboard", color=0x1abc9c)
    for i, (uid, lvl, xp) in enumerate(rows, 1):
        user = bot.get_user(uid)
        name = user.display_name if user else f"User {uid}"
        embed.add_field(name=f"#{i} {name}", value=f"Level {lvl} | {xp} XP", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setlevel", description="Admin: Set a user's level.")
@app_commands.checks.has_permissions(administrator=True)
async def setlevel(interaction: discord.Interaction, member: discord.Member, level: int):
    xp, _ = get_xp(member.id)
    set_xp(member.id, xp, level)
    await interaction.response.send_message(f"Set {member.mention} to Level {level}.")

# ==============================================================================
# --- SECTION 17: ALL UI COMPONENTS SHOWCASE ---
# ==============================================================================

# --- Every Button Style ---
class AllButtonsView(discord.ui.View):
    @discord.ui.button(label="Primary", style=discord.ButtonStyle.primary)
    async def btn1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Primary (Blurple) clicked!", ephemeral=True)
    @discord.ui.button(label="Secondary", style=discord.ButtonStyle.secondary)
    async def btn2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Secondary (Gray) clicked!", ephemeral=True)
    @discord.ui.button(label="Success", style=discord.ButtonStyle.success)
    async def btn3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Success (Green) clicked!", ephemeral=True)
    @discord.ui.button(label="Danger", style=discord.ButtonStyle.danger)
    async def btn4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Danger (Red) clicked!", ephemeral=True)

@bot.tree.command(name="ui_buttons", description="Shows every button style.")
async def ui_buttons(interaction: discord.Interaction):
    view = AllButtonsView()
    view.add_item(discord.ui.Button(label="Link", style=discord.ButtonStyle.url, url="https://discord.com"))
    await interaction.response.send_message("All Button Styles:", view=view)

# --- Disabled Buttons ---
class DisabledButtonsView(discord.ui.View):
    @discord.ui.button(label="Disabled Primary", style=discord.ButtonStyle.primary, disabled=True)
    async def d1(self, interaction: discord.Interaction, button: discord.ui.Button): pass
    @discord.ui.button(label="Disabled Danger", style=discord.ButtonStyle.danger, disabled=True)
    async def d2(self, interaction: discord.Interaction, button: discord.ui.Button): pass
    @discord.ui.button(label="Enabled!", style=discord.ButtonStyle.success)
    async def d3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("This one works!", ephemeral=True)

@bot.tree.command(name="ui_disabled", description="Disabled button examples.")
async def ui_disabled(interaction: discord.Interaction):
    await interaction.response.send_message("Disabled vs Enabled:", view=DisabledButtonsView())

# --- Emoji Buttons ---
class EmojiButtonsView(discord.ui.View):
    @discord.ui.button(emoji="\\u2764\\ufe0f", style=discord.ButtonStyle.danger)
    async def heart(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Heart!", ephemeral=True)
    @discord.ui.button(emoji="\\u2b50", style=discord.ButtonStyle.primary)
    async def star(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Star!", ephemeral=True)
    @discord.ui.button(emoji="\\U0001f525", style=discord.ButtonStyle.secondary)
    async def fire(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Fire!", ephemeral=True)

@bot.tree.command(name="ui_emoji_buttons", description="Buttons with emojis.")
async def ui_emoji_btns(interaction: discord.Interaction):
    await interaction.response.send_message("Emoji Buttons:", view=EmojiButtonsView())

# --- Confirmation Dialog ---
class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.send_message("Confirmed!", ephemeral=True)
        self.stop()
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.send_message("Cancelled.", ephemeral=True)
        self.stop()

@bot.tree.command(name="ui_confirm", description="Confirm/Cancel dialog.")
async def ui_confirm(interaction: discord.Interaction):
    view = ConfirmView()
    await interaction.response.send_message("Are you sure?", view=view)

# --- All Select Menu Types ---
class AllSelectsView(discord.ui.View):
    @discord.ui.select(placeholder="String Select", options=[
        discord.SelectOption(label="Option A", value="a", description="First option"),
        discord.SelectOption(label="Option B", value="b", description="Second option"),
        discord.SelectOption(label="Option C", value="c", description="Third option"),
    ])
    async def string_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.send_message(f"String: {select.values[0]}", ephemeral=True)

@bot.tree.command(name="ui_selects", description="Shows string select menus.")
async def ui_selects(interaction: discord.Interaction):
    await interaction.response.send_message("String Select:", view=AllSelectsView())

class UserSelectView(discord.ui.View):
    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Pick a user...")
    async def user_sel(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        await interaction.response.send_message(f"User: {select.values[0].mention}", ephemeral=True)

@bot.tree.command(name="ui_user_select", description="User select menu.")
async def ui_user_sel(interaction: discord.Interaction):
    await interaction.response.send_message("User Select:", view=UserSelectView())

class RoleSelectView(discord.ui.View):
    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Pick a role...")
    async def role_sel(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        await interaction.response.send_message(f"Role: {select.values[0].mention}", ephemeral=True)

@bot.tree.command(name="ui_role_select", description="Role select menu.")
async def ui_role_sel(interaction: discord.Interaction):
    await interaction.response.send_message("Role Select:", view=RoleSelectView())

class ChannelSelectView(discord.ui.View):
    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="Pick a channel...", channel_types=[discord.ChannelType.text])
    async def ch_sel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        await interaction.response.send_message(f"Channel: {select.values[0].mention}", ephemeral=True)

@bot.tree.command(name="ui_channel_select", description="Channel select menu.")
async def ui_ch_sel(interaction: discord.Interaction):
    await interaction.response.send_message("Channel Select:", view=ChannelSelectView())

class MentionableSelectView(discord.ui.View):
    @discord.ui.select(cls=discord.ui.MentionableSelect, placeholder="Pick a user or role...")
    async def m_sel(self, interaction: discord.Interaction, select: discord.ui.MentionableSelect):
        await interaction.response.send_message(f"Selected: {select.values[0]}", ephemeral=True)

@bot.tree.command(name="ui_mentionable_select", description="Mentionable select (user or role).")
async def ui_m_sel(interaction: discord.Interaction):
    await interaction.response.send_message("Mentionable Select:", view=MentionableSelectView())

# --- Multi-Select ---
class MultiSelectView(discord.ui.View):
    @discord.ui.select(placeholder="Pick up to 3!", min_values=1, max_values=3, options=[
        discord.SelectOption(label="Red", value="red"),
        discord.SelectOption(label="Blue", value="blue"),
        discord.SelectOption(label="Green", value="green"),
        discord.SelectOption(label="Yellow", value="yellow"),
        discord.SelectOption(label="Purple", value="purple"),
    ])
    async def multi(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.send_message(f"You chose: {', '.join(select.values)}", ephemeral=True)

@bot.tree.command(name="ui_multi_select", description="Multi-value select menu.")
async def ui_multi(interaction: discord.Interaction):
    await interaction.response.send_message("Pick multiple:", view=MultiSelectView())

# --- Modals ---
class ShortModal(discord.ui.Modal, title="Short Input Modal"):
    answer = discord.ui.TextInput(label="Short Answer", style=discord.TextStyle.short, placeholder="Quick answer...", required=True, max_length=100)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"You said: {self.answer.value}", ephemeral=True)

@bot.tree.command(name="ui_modal_short", description="Modal with short text input.")
async def ui_modal_short(interaction: discord.Interaction):
    await interaction.response.send_modal(ShortModal())

class LongModal(discord.ui.Modal, title="Long Input Modal"):
    answer = discord.ui.TextInput(label="Long Answer", style=discord.TextStyle.paragraph, placeholder="Write a paragraph...", required=True, max_length=2000)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"You wrote:\\n{self.answer.value}", ephemeral=True)

@bot.tree.command(name="ui_modal_long", description="Modal with paragraph text input.")
async def ui_modal_long(interaction: discord.Interaction):
    await interaction.response.send_modal(LongModal())

class FeedbackModal(discord.ui.Modal, title="Feedback Form"):
    name_input = discord.ui.TextInput(label="Your Name", style=discord.TextStyle.short, required=True)
    rating = discord.ui.TextInput(label="Rating (1-10)", style=discord.TextStyle.short, required=True, max_length=2)
    feedback = discord.ui.TextInput(label="Feedback", style=discord.TextStyle.paragraph, required=False, placeholder="Optional feedback...")
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="New Feedback", color=0x2ecc71)
        embed.add_field(name="Name", value=self.name_input.value)
        embed.add_field(name="Rating", value=self.rating.value)
        embed.add_field(name="Feedback", value=self.feedback.value or "None", inline=False)
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ui_feedback", description="A full feedback form modal.")
async def ui_feedback(interaction: discord.Interaction):
    await interaction.response.send_modal(FeedbackModal())

class BugReportModal(discord.ui.Modal, title="Bug Report"):
    bug_title = discord.ui.TextInput(label="Bug Title", style=discord.TextStyle.short, required=True)
    steps = discord.ui.TextInput(label="Steps to Reproduce", style=discord.TextStyle.paragraph, required=True)
    expected = discord.ui.TextInput(label="Expected Behavior", style=discord.TextStyle.paragraph, required=False)
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title=f"Bug: {self.bug_title.value}", description=self.steps.value, color=0xe74c3c)
        if self.expected.value:
            embed.add_field(name="Expected", value=self.expected.value)
        embed.set_footer(text=f"Reported by {interaction.user}")
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ui_bugreport", description="Bug report modal.")
async def ui_bugreport(interaction: discord.Interaction):
    await interaction.response.send_modal(BugReportModal())

class ApplicationModal(discord.ui.Modal, title="Staff Application"):
    age = discord.ui.TextInput(label="Age", style=discord.TextStyle.short, required=True, max_length=3)
    timezone = discord.ui.TextInput(label="Timezone", style=discord.TextStyle.short, required=True)
    experience = discord.ui.TextInput(label="Moderation Experience", style=discord.TextStyle.paragraph, required=True)
    why = discord.ui.TextInput(label="Why should we pick you?", style=discord.TextStyle.paragraph, required=True)
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Staff Application", color=0x3498db)
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Age", value=self.age.value)
        embed.add_field(name="Timezone", value=self.timezone.value)
        embed.add_field(name="Experience", value=self.experience.value, inline=False)
        embed.add_field(name="Why", value=self.why.value, inline=False)
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ui_apply", description="Staff application modal.")
async def ui_apply(interaction: discord.Interaction):
    await interaction.response.send_modal(ApplicationModal())

# --- Paginator (Advanced) ---
class Paginator(discord.ui.View):
    def __init__(self, embeds):
        super().__init__(timeout=120)
        self.embeds = embeds
        self.current = 0
        self.update_buttons()

    def update_buttons(self):
        self.children[0].disabled = self.current == 0
        self.children[1].disabled = self.current == len(self.embeds) - 1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current], view=self)

@bot.tree.command(name="ui_paginator", description="Paginated embeds example.")
async def ui_paginator(interaction: discord.Interaction):
    embeds = [discord.Embed(title=f"Page {i+1}", description=f"Content for page {i+1}", color=0x3498db) for i in range(5)]
    view = Paginator(embeds)
    await interaction.response.send_message(embed=embeds[0], view=view)

# --- Counter Button ---
class CounterView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.count = 0
    @discord.ui.button(label="Count: 0", style=discord.ButtonStyle.primary)
    async def counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.count += 1
        button.label = f"Count: {self.count}"
        await interaction.response.edit_message(view=self)

@bot.tree.command(name="ui_counter", description="Interactive counter button.")
async def ui_counter(interaction: discord.Interaction):
    await interaction.response.send_message("Click to count:", view=CounterView())

# --- Toggle Button ---
class ToggleView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.toggled = False
    @discord.ui.button(label="OFF", style=discord.ButtonStyle.danger)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.toggled = not self.toggled
        button.label = "ON" if self.toggled else "OFF"
        button.style = discord.ButtonStyle.success if self.toggled else discord.ButtonStyle.danger
        await interaction.response.edit_message(view=self)

@bot.tree.command(name="ui_toggle", description="Toggle switch button.")
async def ui_toggle(interaction: discord.Interaction):
    await interaction.response.send_message("Toggle:", view=ToggleView())

# ==============================================================================
# --- SECTION 18: CONTEXT MENUS ---
# ==============================================================================
@bot.tree.context_menu(name="Get User Info")
async def ctx_userinfo(interaction: discord.Interaction, member: discord.Member):
    embed = discord.Embed(title=str(member), color=member.color)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined", value=discord.utils.format_dt(member.joined_at, "R"))
    embed.set_thumbnail(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.context_menu(name="Report Message")
async def ctx_report(interaction: discord.Interaction, message: discord.Message):
    embed = discord.Embed(title="Message Reported", color=0xe74c3c)
    embed.add_field(name="Author", value=str(message.author))
    embed.add_field(name="Content", value=message.content[:1024] or "No text")
    embed.add_field(name="Reported by", value=str(interaction.user))
    await interaction.response.send_message("Message reported to staff.", ephemeral=True)

@bot.tree.context_menu(name="Translate (Stub)")
async def ctx_translate(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.send_message(f"[Translation stub] Original: {message.content[:500]}", ephemeral=True)

@bot.tree.context_menu(name="Get Avatar")
async def ctx_avatar(interaction: discord.Interaction, member: discord.Member):
    embed = discord.Embed(title=f"{member.display_name}'s Avatar")
    embed.set_image(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==============================================================================
# --- SECTION 19: API COMMANDS ---
# ==============================================================================
@bot.tree.command(name="dog", description="Random dog image.")
async def dog(interaction: discord.Interaction):
    await interaction.response.defer()
    async with bot.session.get("https://dog.ceo/api/breeds/image/random") as r:
        if r.status == 200:
            data = await r.json()
            embed = discord.Embed(title="Woof!", color=0x2ecc71)
            embed.set_image(url=data["message"])
            await interaction.followup.send(embed=embed)

@bot.tree.command(name="cat", description="Random cat image.")
async def cat(interaction: discord.Interaction):
    await interaction.response.defer()
    async with bot.session.get("https://api.thecatapi.com/v1/images/search") as r:
        if r.status == 200:
            data = await r.json()
            embed = discord.Embed(title="Meow!", color=0xe91e63)
            embed.set_image(url=data[0]["url"])
            await interaction.followup.send(embed=embed)

@bot.tree.command(name="meme", description="Random meme from Reddit.")
async def meme(interaction: discord.Interaction):
    await interaction.response.defer()
    async with bot.session.get("https://meme-api.com/gimme") as r:
        if r.status == 200:
            data = await r.json()
            embed = discord.Embed(title=data["title"], url=data["postLink"], color=0xff4500)
            embed.set_image(url=data["url"])
            embed.set_footer(text=f"r/{data['subreddit']} | {data['ups']} upvotes")
            await interaction.followup.send(embed=embed)

# ==============================================================================
# --- SECTION 20: COUNTING CHANNEL ---
# ==============================================================================
@bot.tree.command(name="counting_setup", description="Admin: Set up counting in this channel.")
@app_commands.checks.has_permissions(administrator=True)
async def counting_setup(interaction: discord.Interaction):
    bot.counting_channels[interaction.channel.id] = 0
    await interaction.response.send_message("Counting enabled! Start at **1**.")

# ==============================================================================
# --- SECTION 21: CHANNEL MANAGEMENT ---
# ==============================================================================
@bot.tree.command(name="create_channel", description="Creates a text channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def create_channel(interaction: discord.Interaction, name: str, category: discord.CategoryChannel = None):
    ch = await interaction.guild.create_text_channel(name, category=category)
    await interaction.response.send_message(f"Created {ch.mention}.")

@bot.tree.command(name="create_vc", description="Creates a voice channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def create_vc(interaction: discord.Interaction, name: str, category: discord.CategoryChannel = None):
    ch = await interaction.guild.create_voice_channel(name, category=category)
    await interaction.response.send_message(f"Created voice channel **{ch.name}**.")

@bot.tree.command(name="create_category", description="Creates a category.")
@app_commands.checks.has_permissions(manage_channels=True)
async def create_category(interaction: discord.Interaction, name: str):
    cat = await interaction.guild.create_category(name)
    await interaction.response.send_message(f"Created category **{cat.name}**.")

@bot.tree.command(name="delete_channel", description="Deletes a channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def delete_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    await channel.delete()
    await interaction.response.send_message(f"Deleted #{channel.name}.")

@bot.tree.command(name="rename_channel", description="Renames a channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def rename_channel(interaction: discord.Interaction, channel: discord.TextChannel, name: str):
    old = channel.name
    await channel.edit(name=name)
    await interaction.response.send_message(f"Renamed #{old} to #{name}.")

@bot.tree.command(name="set_topic", description="Sets a channel topic.")
@app_commands.checks.has_permissions(manage_channels=True)
async def set_topic(interaction: discord.Interaction, topic: str):
    await interaction.channel.edit(topic=topic)
    await interaction.response.send_message(f"Topic set to: {topic}")

# ==============================================================================
# --- SECTION 22: ROLE MANAGEMENT ---
# ==============================================================================
@bot.tree.command(name="create_role", description="Creates a role.")
@app_commands.checks.has_permissions(manage_roles=True)
async def create_role(interaction: discord.Interaction, name: str, color: str = "000000"):
    try:
        c_int = int(color.strip("#"), 16)
    except ValueError:
        c_int = 0
    role = await interaction.guild.create_role(name=name, color=discord.Color(c_int))
    await interaction.response.send_message(f"Created role {role.mention}.")

@bot.tree.command(name="delete_role", description="Deletes a role.")
@app_commands.checks.has_permissions(manage_roles=True)
async def delete_role(interaction: discord.Interaction, role: discord.Role):
    await role.delete()
    await interaction.response.send_message(f"Deleted role **{role.name}**.")

@bot.tree.command(name="role_color", description="Changes a role's color.")
@app_commands.checks.has_permissions(manage_roles=True)
async def role_color(interaction: discord.Interaction, role: discord.Role, color: str):
    try:
        c_int = int(color.strip("#"), 16)
    except ValueError:
        return await interaction.response.send_message("Invalid hex color.", ephemeral=True)
    await role.edit(color=discord.Color(c_int))
    await interaction.response.send_message(f"Changed {role.mention} color to #{color}.")

@bot.tree.command(name="role_members", description="Lists members with a role.")
async def role_members(interaction: discord.Interaction, role: discord.Role):
    members = [m.mention for m in role.members[:30]]
    embed = discord.Embed(title=f"Members with {role.name}", description="\\n".join(members) if members else "None", color=role.color)
    await interaction.response.send_message(embed=embed)

# ==============================================================================
# --- SECTION 23: EMOJI MANAGEMENT ---
# ==============================================================================
@bot.tree.command(name="emoji_list", description="Lists all server emojis.")
async def emoji_list(interaction: discord.Interaction):
    emojis = [str(e) for e in interaction.guild.emojis]
    if emojis:
        await interaction.response.send_message(" ".join(emojis[:50]))
    else:
        await interaction.response.send_message("No custom emojis.", ephemeral=True)

@bot.tree.command(name="emoji_info", description="Info about an emoji.")
async def emoji_info(interaction: discord.Interaction, emoji: str):
    for e in interaction.guild.emojis:
        if str(e) == emoji or e.name == emoji:
            embed = discord.Embed(title=e.name, color=0x3498db)
            embed.set_image(url=e.url)
            embed.add_field(name="ID", value=e.id)
            embed.add_field(name="Animated", value=str(e.animated))
            return await interaction.response.send_message(embed=embed)
    await interaction.response.send_message("Emoji not found.", ephemeral=True)

# ==============================================================================
# --- SECTION 24: MISC ADMIN COMMANDS ---
# ==============================================================================
@bot.tree.command(name="announce", description="Send an announcement embed.")
@app_commands.checks.has_permissions(manage_guild=True)
async def announce(interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str):
    embed = discord.Embed(title=title, description=message, color=0x3498db, timestamp=datetime.utcnow())
    embed.set_footer(text=f"Announced by {interaction.user}")
    await channel.send(embed=embed)
    await interaction.response.send_message("Announcement sent!", ephemeral=True)

@bot.tree.command(name="say", description="Makes the bot say something.")
@app_commands.checks.has_permissions(manage_messages=True)
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("Sent!", ephemeral=True)
    await interaction.channel.send(message)

@bot.tree.command(name="dm", description="DMs a user.")
@app_commands.checks.has_permissions(administrator=True)
async def dm_cmd(interaction: discord.Interaction, member: discord.Member, message: str):
    try:
        await member.send(message)
        await interaction.response.send_message(f"DM sent to {member.mention}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("Cannot DM that user.", ephemeral=True)

# ==============================================================================
# --- SECTION 25: COMPREHENSIVE ERROR HANDLER ---
# ==============================================================================
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = f"Cooldown! Try again in {error.retry_after:.1f}s."
    elif isinstance(error, app_commands.MissingPermissions):
        msg = f"Missing permissions: {', '.join(error.missing_permissions)}"
    elif isinstance(error, app_commands.BotMissingPermissions):
        msg = f"I need permissions: {', '.join(error.missing_permissions)}"
    elif isinstance(error, app_commands.CheckFailure):
        msg = "You lack permission to use this."
    else:
        msg = f"An error occurred: {error}"
        print(f"Command error: {error}")
    if not interaction.response.is_done():
        await interaction.response.send_message(msg, ephemeral=True)
    else:
        await interaction.followup.send(msg, ephemeral=True)

# ==============================================================================
# --- SECTION 26: HOW TO USE COGS (Copy-Paste Template) ---
# ==============================================================================
# To split this bot into multiple files, create a "cogs" folder and use this template:
#
# --- cogs/moderation.py ---
# import discord
# from discord.ext import commands
# from discord import app_commands
#
# class Moderation(commands.Cog):
#     def __init__(self, bot):
#         self.bot = bot
#
#     @app_commands.command(name="cog_ban", description="Ban from cog")
#     @app_commands.checks.has_permissions(ban_members=True)
#     async def cog_ban(self, interaction: discord.Interaction, member: discord.Member):
#         await member.ban()
#         await interaction.response.send_message(f"Banned {member.mention}")
#
# async def setup(bot):
#     await bot.add_cog(Moderation(bot))
#
# Then in your main file's setup_hook:
#     await self.load_extension("cogs.moderation")

# ==============================================================================
# --- SECTION 27: RUN THE BOT ---
# ==============================================================================
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("WARNING: Replace YOUR_BOT_TOKEN_HERE with your actual bot token!")
        print("Or set the DISCORD_BOT_TOKEN environment variable.")
    bot.run(TOKEN)
'''

def main():
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = "make_a_bot.py"

    if os.path.exists(filename):
        print(f"Error: '{filename}' already exists. Delete it first or choose a different name.")
        sys.exit(1)

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(TEMPLATE)
        lines = TEMPLATE.count('\\n') + 1
        print(f"*** Successfully generated {filename} ({lines} lines) ***")
        print("*** The ULTIMATE Discord bot snippet library! ***")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
