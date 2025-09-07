import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Select
import asyncio
import datetime
import random
import aiosqlite
from typing import List, Dict, Optional

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
# Bot Creator And Developer : Copy

class GiveawayDB:
    def __init__(self):
        self.db_path = "giveaways.db"
    
    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS giveaways (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    guild_id INTEGER,
                    prize TEXT,
                    winners INTEGER,
                    end_time TIMESTAMP,
                    emoji TEXT,
                    status TEXT DEFAULT 'active'
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS entries (
                    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER,
                    user_id INTEGER,
                    entry_time TIMESTAMP,
                    FOREIGN KEY (message_id) REFERENCES giveaways (message_id)
                )
            ''')
            await db.commit()

db = GiveawayDB()


class SpecialEmoji:
    def __init__(self):
        self.default_emoji = "🎉"
        self.premium_emojis = {
            "gold": "💰",
            "diamond": "💎", 
            "gift": "🎁",
            "star": "⭐",
            "fire": "🔥",
            "trophy": "🏆",
            "rocket": "🚀"
        }
    
    def get_emoji(self, emoji_type: str = "default"):
        return self.premium_emojis.get(emoji_type, self.default_emoji)

special_emoji = SpecialEmoji()

class GiveawayCreateView(View):
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="Create Giveaway", style=discord.ButtonStyle.primary, emoji="🎁")
    async def create_button(self, interaction: discord.Interaction, button: Button):
        modal_view = GiveawayModalView()
        await interaction.response.send_message("Please answer the following questions to create a giveaway:", view=modal_view, ephemeral=True)

class GiveawayModalView(View):
    def __init__(self):
        super().__init__(timeout=300)
        self.prize = None
        self.duration = None
        self.winners = None
        self.emoji_type = "default"
        

        emoji_select = Select(
            placeholder="Choose emoji type",
            options=[
                discord.SelectOption(label="Default 🎉", value="default"),
                discord.SelectOption(label="Gold 💰", value="gold"),
                discord.SelectOption(label="Diamond 💎", value="diamond"),
                discord.SelectOption(label="Gift 🎁", value="gift"),
                discord.SelectOption(label="Star ⭐", value="star"),
                discord.SelectOption(label="Fire 🔥", value="fire"),
                discord.SelectOption(label="Trophy 🏆", value="trophy"),
                discord.SelectOption(label="Rocket 🚀", value="rocket")
            ]
        )
        
        async def emoji_callback(interaction: discord.Interaction):
            self.emoji_type = emoji_select.values[0]
            await interaction.response.send_message(f"Selected emoji: {special_emoji.get_emoji(self.emoji_type)}", ephemeral=True)
        
        emoji_select.callback = emoji_callback
        self.add_item(emoji_select)

class GiveawayJoinView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Join Giveaway", style=discord.ButtonStyle.primary, emoji="🎯", custom_id="join_giveaway")
    async def join_button(self, interaction: discord.Interaction, button: Button):
        async with aiosqlite.connect(db.db_path) as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM entries WHERE message_id = ? AND user_id = ?",
                (interaction.message.id, interaction.user.id)
            )
            existing = await cursor.fetchone()
            
            if not existing:
                await conn.execute(
                    "INSERT INTO entries (message_id, user_id, entry_time) VALUES (?, ?, ?)",
                    (interaction.message.id, interaction.user.id, datetime.datetime.now().isoformat())
                )
                await conn.commit()
                
                await interaction.response.send_message(
                    "✅ You've entered the giveaway! Good luck!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "⚠️ You've already entered this giveaway!",
                    ephemeral=True
                )

class GiveawayControlView(View):
    def __init__(self, message_id: int):
        super().__init__(timeout=300)
        self.message_id = message_id
    
    @discord.ui.button(label="End Now", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def end_now(self, interaction: discord.Interaction, button: Button):
        await end_giveaway(interaction, self.message_id)
    
    @discord.ui.button(label="Reroll", style=discord.ButtonStyle.success, emoji="🔄")
    async def reroll(self, interaction: discord.Interaction, button: Button):
        await reroll_giveaway(interaction, self.message_id)

# Commands
@bot.command(name="giveaway")
async def giveaway_create(ctx):


    await ctx.send("🎁 **Giveaway Creation**\nWhat is the prize?")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    try:
        prize_msg = await bot.wait_for('message', timeout=60.0, check=check)
        prize = prize_msg.content
        
        # Ask for duration
        await ctx.send("⏰ How many minutes should the giveaway last?")
        duration_msg = await bot.wait_for('message', timeout=60.0, check=check)
        duration = int(duration_msg.content)
        

        await ctx.send("👥 How many winners?")
        winners_msg = await bot.wait_for('message', timeout=60.0, check=check)
        winners = int(winners_msg.content)
        
   
        view = GiveawayModalView()
        await ctx.send("🎨 Choose an emoji type for your giveaway:", view=view)
        

        await asyncio.sleep(5)  
        
        emoji = special_emoji.get_emoji(view.emoji_type)
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration)
        

        embed = discord.Embed(
            title=f"{emoji} GIVEAWAY {emoji}",
            description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
            color=0x00ff00
        )
        embed.set_footer(text=f"Hosted by {ctx.author.name}")
        
        view = GiveawayJoinView()
        message = await ctx.send(embed=embed, view=view)
        
 
        await message.add_reaction(emoji)
        
        # Save to database
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                '''INSERT INTO giveaways 
                (message_id, channel_id, guild_id, prize, winners, end_time, emoji, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (message.id, message.channel.id, message.guild.id, prize, winners, 
                 end_time.isoformat(), emoji, 'active')
            )
            await conn.commit()
        
        await ctx.send(f"Giveaway created successfully! {emoji}")
        
    except asyncio.TimeoutError:
        await ctx.send("Giveaway creation timed out!")
    except ValueError:
        await ctx.send("Invalid input! Please enter numbers for duration and winners.")

@bot.command(name="giveaway_list")
async def giveaway_list(ctx):
    """Show active giveaways"""
    async with aiosqlite.connect(db.db_path) as conn:
        cursor = await conn.execute(
            "SELECT message_id, prize, end_time, emoji FROM giveaways WHERE status = 'active' AND guild_id = ?",
            (ctx.guild.id,)
        )
        active_giveaways = await cursor.fetchall()
    
    if not active_giveaways:
        await ctx.send("No active giveaways found!")
        return
    
    embed = discord.Embed(title="🎁 Active Giveaways", color=0xffd700)
    
    for giveaway in active_giveaways:
        message_id, prize, end_time, emoji = giveaway
        end_dt = datetime.datetime.fromisoformat(end_time)
        time_left = end_dt - datetime.datetime.now()
        
        embed.add_field(
            name=f"{emoji} {prize}",
            value=f"Ends in: {str(time_left).split('.')[0]}\nID: {message_id}",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name="giveaway_end")
async def giveaway_end(ctx, message_id: int):
    """End a giveaway early"""
    await end_giveaway(ctx, message_id)

@bot.command(name="giveaway_reroll")
async def giveaway_reroll(ctx, message_id: int):
    """Reroll a giveaway"""
    await reroll_giveaway(ctx, message_id)


async def end_giveaway(ctx, message_id: int):
    async with aiosqlite.connect(db.db_path) as conn:
        cursor = await conn.execute(
            "SELECT channel_id, prize, winners, emoji FROM giveaways WHERE message_id = ?",
            (message_id,)
        )
        giveaway = await cursor.fetchone()
        
        if not giveaway:
            await ctx.send("Giveaway not found!")
            return
        
        channel_id, prize, winners, emoji = giveaway
        
        cursor = await conn.execute(
            "SELECT user_id FROM entries WHERE message_id = ?",
            (message_id,)
        )
        entries = await cursor.fetchall()
        
        if not entries:
            await ctx.send("No entries found!")
            return
        
        winner_ids = random.sample([entry[0] for entry in entries], min(winners, len(entries)))
        winners_mention = [f"<@{winner_id}>" for winner_id in winner_ids]
        
        await conn.execute(
            "UPDATE giveaways SET status = 'ended' WHERE message_id = ?",
            (message_id,)
        )
        await conn.commit()
    
    channel = bot.get_channel(channel_id)
    if channel:
        try:
            message = await channel.fetch_message(message_id)
            
            embed = message.embeds[0] if message.embeds else discord.Embed()
            embed.color = 0xff0000
            embed.description += f"\n\n**🎊 Winners:** {', '.join(winners_mention)}"
            embed.set_footer(text="Giveaway ended")
            
            await message.edit(embed=embed, view=None)
            
            announcement = f"🎉 **GIVEAWAY ENDED** 🎉\nCongratulations {', '.join(winners_mention)}! You won **{prize}**!"
            await channel.send(announcement)
            
            await ctx.send("Giveaway ended successfully!")
            
        except discord.NotFound:
            await ctx.send("Message not found!")

async def reroll_giveaway(ctx, message_id: int):
    async with aiosqlite.connect(db.db_path) as conn:
        cursor = await conn.execute(
            "SELECT channel_id, prize, winners FROM giveaways WHERE message_id = ?",
            (message_id,)
        )
        giveaway = await cursor.fetchone()
        
        if not giveaway:
            await ctx.send("Giveaway not found!")
            return
        
        channel_id, prize, winners = giveaway
        
        cursor = await conn.execute(
            "SELECT user_id FROM entries WHERE message_id = ?",
            (message_id,)
        )
        entries = await cursor.fetchall()
        
        if not entries:
            await ctx.send("No entries found!")
            return
        
        winner_ids = random.sample([entry[0] for entry in entries], min(winners, len(entries)))
        winners_mention = [f"<@{winner_id}>" for winner_id in winner_ids]
    
    channel = bot.get_channel(channel_id)
    if channel:
        announcement = f"🔄 **GIVEAWAY REROLL** 🔄\nNew winners: {', '.join(winners_mention)}! You won **{prize}**!"
        await channel.send(announcement)
        
        await ctx.send("Giveaway rerolled successfully!")


@tasks.loop(minutes=1)
async def check_giveaways():
    async with aiosqlite.connect(db.db_path) as conn:
        cursor = await conn.execute(
            "SELECT message_id, channel_id, prize, winners, emoji FROM giveaways WHERE status = 'active' AND end_time <= ?",
            (datetime.datetime.now().isoformat(),)
        )
        ended_giveaways = await cursor.fetchall()
        
        for giveaway in ended_giveaways:
            message_id, channel_id, prize, winners, emoji = giveaway
            channel = bot.get_channel(channel_id)
            
            if channel:
                try:
                    message = await channel.fetch_message(message_id)
                    
                    cursor = await conn.execute(
                        "SELECT user_id FROM entries WHERE message_id = ?",
                        (message_id,)
                    )
                    entries = await cursor.fetchall()
                    
                    if entries:
                        winner_ids = random.sample([entry[0] for entry in entries], min(winners, len(entries)))
                        winners_mention = [f"<@{winner_id}>" for winner_id in winner_ids]
                    else:
                        winners_mention = ["No valid entries"]
                    
                    embed = message.embeds[0] if message.embeds else discord.Embed()
                    embed.color = 0xff0000
                    embed.description += f"\n\n**🎊 Winners:** {', '.join(winners_mention)}"
                    embed.set_footer(text="Giveaway ended")
                    
                    await message.edit(embed=embed, view=None)
                    
                    announcement = f"🎉 **GIVEAWAY ENDED** 🎉\nCongratulations {', '.join(winners_mention)}! You won **{prize}**!"
                    await channel.send(announcement)
                    
                    await conn.execute(
                        "UPDATE giveaways SET status = 'ended' WHERE message_id = ?",
                        (message_id,)
                    )
                    await conn.commit()
                    
                except discord.NotFound:
                    pass


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await db.init_db()
    check_giveaways.start()
    bot.add_view(GiveawayJoinView())

@bot.event
async def on_raw_reaction_add(payload):
    if payload.member and payload.member.bot:
        return
    
    async with aiosqlite.connect(db.db_path) as conn:
        cursor = await conn.execute(
            "SELECT emoji FROM giveaways WHERE message_id = ? AND status = 'active'",
            (payload.message_id,)
        )
        giveaway = await cursor.fetchone()
        
        if giveaway:
            expected_emoji = giveaway[0]
            reaction_emoji = str(payload.emoji)
            
            if reaction_emoji == expected_emoji:
                cursor = await conn.execute(
                    "SELECT 1 FROM entries WHERE message_id = ? AND user_id = ?",
                    (payload.message_id, payload.user_id)
                )
                existing = await cursor.fetchone()
                
                if not existing:
                    await conn.execute(
                        "INSERT INTO entries (message_id, user_id, entry_time) VALUES (?, ?, ?)",
                        (payload.message_id, payload.user_id, datetime.datetime.now().isoformat())
                    )
                    await conn.commit()
@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="🎯 راهنمای بات Giveaway",
        description="**دستورات اصلی بات:**",
        color=0x00ff00
    )
    
    embed.add_field(
        name="🎁 `!giveaway`",
        value="ایجاد یک giveaway جدید",
        inline=False
    )
    
    embed.add_field(
        name="📋 `!giveaway_list`",
        value="نمایش giveawayهای فعال",
        inline=False
    )
    
    embed.add_field(
        name="⏹️ `!giveaway_end <message_id>`",
        value="پایان دادن به giveaway",
        inline=False
    )
    
    embed.add_field(
        name="🔄 `!giveaway_reroll <message_id>`",
        value="انتخاب مجدد برنده",
        inline=False
    )
    
    embed.add_field(
        name="🎨 ایموجی‌های ویژه",
        value="`gold💰, diamond💎, gift🎁, star⭐, fire🔥, trophy🏆, rocket🚀`",
        inline=False
    )
    
    embed.set_footer(text="برای اطلاعات بیشتر با ادمین تماس بگیرید")
    
    await ctx.send(embed=embed)

if __name__ == "__main__":

    bot.run("")