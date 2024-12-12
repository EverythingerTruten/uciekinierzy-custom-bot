import math
import discord
from discord.ext import commands
from unbelievaboat import Client
from discord.ext.commands.errors import CommandOnCooldown
import random
import re

'''Config for the bot'''
terrorism_cooldown = 14400 #Set in seconds
currency_emoji = '<:EMOJINAME:EMOJIID>' #Put the name of emoji between the colons and the emoji id after
# Set the winning and fine maxes and minimums here
win_max = 2500
win_min = 800
loss_max = 1500
loss_min = 600

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Set up bot
bot = commands.Bot(command_prefix="!", intents=intents)

api_token = 'REPLACE WITH YOUR UNBELIAVABOAT TOKEN'  # Define your API token here

def check_success(user_balance):
    """
    Check if action succeeds based on user balance.
    Higher balance = lower chance of success, maxed at 50%.
    
    Args:
        user_balance (float): User's balance
        k (float): Divisor to control how quickly success rate drops
        
    Returns:
        bool: True if successful, False if failed
    """
    if user_balance <= 0:
        return random.randrange(1, 100, 1) <= 50
    
    # Calculate success chance (0-50)
    success_percent = 60 / (1 + (user_balance / 10000))
    
    # Return True based on the calculated probability
    return random.randrange(1, 100, 1) <= success_percent

def format_cooldown_time(hours=0, minutes=0, seconds=0):
    # For times >= 1 hour, show only hours and minutes
    if hours > 0:
        details = []
        time_parts = []

        if hours > 0:
            details.append(f"Hours left: {hours}")
            time_parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            details.append(f"Minutes left: {minutes}")
            time_parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

    # For times < 1 hour, show only minutes and seconds
    else:
        details = []
        time_parts = []

        if minutes > 0:
            details.append(f"Minutes left: {minutes}")
            time_parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds > 0:
            details.append(f"Seconds left: {seconds}")
            time_parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    # Join with 'and' before the last element if multiple parts exist
    if len(time_parts) > 1:
        time_message = f"{', '.join(time_parts[:-1])} and {time_parts[-1]}"
    else:
        time_message = time_parts[0]

    return time_message

def format_number(number: int) -> str:
    return "{:,}".format(number)

def select_weighted_user(leaderboard_data, user_id, member_ids):
    # The leaderboard data should be accessed through its proper attributes
    users = []
    for entry in leaderboard_data.users:  # Assuming the Leaderboard object has a users attribute
        # Only include users who are:
        # 1. Not the command user
        # 2. Still in the server
        if str(entry.user_id) != str(user_id) and str(entry.user_id) in member_ids:
            users.append((str(entry.user_id), entry.total))

    if not users:
        return None

    # Calculate total weight for normalization
    total_weight = sum(weight for _, weight in users)
    
    if total_weight == 0:
        return None

    # Generate a random value between 0 and total weight
    r = random.uniform(0, total_weight)

    # Use weighted selection
    current_weight = 0
    for user_id, weight in users:
        current_weight += weight
        if r <= current_weight:
            return user_id

    # Fallback to last user if we somehow don't select one
    return users[-1][0] if users else None

@bot.event
async def on_ready():
    """Start-up message."""
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')

@bot.command(aliases =["terror","ter"])
@commands.cooldown(1, terrorism_cooldown, commands.BucketType.user)
async def terrorism(ctx, avamember : discord.Member=None):
    try:
        # Use the Unbelievaboat client with async context
        async with Client(api_token) as unb_client:
            guild = await unb_client.get_guild(ctx.guild.id)
            user = await guild.get_user_balance(ctx.author.id)
            user_balance = user.cash + user.bank
            if check_success(user_balance):
                with open('win_messages.txt', 'r', encoding='utf-8') as file:
                    leaderboard = await unb_client.get_guild_leaderboard(ctx.guild.id)
                    all_member_ids = [str(member.id) for member in ctx.guild.members]
                    victim_id = select_weighted_user(leaderboard, ctx.author.id, all_member_ids)
                    
                    if victim_id is None:
                        await ctx.send("No valid targets found!")
                        return
                        
                    transaction_value = random.randrange(win_min, win_max, 1)
                    victim = await guild.get_user_balance(victim_id)
                    await user.update(cash=transaction_value)
                    await victim.update(cash=-transaction_value)
                    responses = [line.strip() for line in file if line.strip()]
                    response = random.choice(responses)
                    win_message = response.format(victim=f"<@{victim_id}>", amount=f"{currency_emoji}{format_number(transaction_value)}")
                    embed = discord.Embed(
                        description=win_message,
                        color= 0x66bb6a
                    )
                    icon_url = avamember.display_avatar.url if avamember else ctx.author.display_avatar.url
                    embed.set_author(
                        name=ctx.author.name,
                        icon_url=icon_url
                    )
                    await ctx.send(embed=embed)
            else:
                # Rest of the code remains the same for the failure case
                with open('loss_messages.txt', 'r', encoding='utf-8') as file:
                    amount = random.randrange(loss_min, loss_max, 1)
                    await user.update(cash=-amount)
                    responses = [line.strip() for line in file if line.strip()]
                    response = random.choice(responses)
                    fail_message = response.replace("{amount}", str(currency_emoji) + format_number(amount))
                    embed = discord.Embed(
                        description=fail_message,
                        color=discord.Color.red()
                    )
                    icon_url = avamember.display_avatar.url if avamember else ctx.author.display_avatar.url
                    embed.set_author(
                        name=ctx.author.name,
                        icon_url=icon_url
                    )
                    await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

@bot.event #Cooldown handler
async def on_command_error(ctx, error, avamember: discord.Member=None):
    # Make sure command exists before checking name
    if ctx.command:
        if ctx.command.name == 'terrorism':
            if isinstance(error, CommandOnCooldown):
                retry_after = error.retry_after
                cdwn_hours = round(retry_after // 3600)
                cdwn_minutes = round((retry_after % 3600) // 60)
                cdwn_seconds = round(retry_after % 60)

                embed = discord.Embed(
                    description=f"<:Stopwatch:1307319093019283486> You cannot commit terrorism for {format_cooldown_time(cdwn_hours,cdwn_minutes,cdwn_seconds)}", #Emoji will not work, you can either remove it or add it to the emojis in developer panel
                    color= discord.Color.blue()  # You can change the color of the embed
                )
    
                # Set the author with the author's name and avatar URL
                icon_url = avamember.display_avatar.url if avamember else ctx.author.display_avatar.url
                embed.set_author(
                    name=ctx.author.name,  # The author's username
                    icon_url=icon_url  # The author's avatar URL 
                )
                await ctx.send(embed=embed)
        else:
            await ctx.send(f"An error occurred: {error}")

# Run the bot
bot.run("REPLACE WITH YOUR DISCORD BOT TOKEN")