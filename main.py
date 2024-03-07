# main.py

import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import mysql.connector

# Bot Setup

# Define the bot's intents
intents = discord.Intents.all()

# Create the bot instance
bot = commands.Bot(command_prefix=',', intents=intents, help_command=None)


# Define an event for when the bot is ready
@bot.event
async def on_ready():
    # Set bot's presence
    await bot.change_presence(status=discord.Status.do_not_disturb, activity=discord.Activity(
        type=discord.ActivityType.playing, name=f"with {len(bot.guilds)} servers and {len(bot.users)} members"))

    # Load commands from commands.py
    await bot.load_extension("commands")
    print(f'{bot.user} is now running!')


# Event to add new members to the MySQL server when they join the guild
@bot.event
async def on_member_join(ctx, member):
    guild = ctx.guild  # Fetch the guild object
    load_dotenv()
    pword = os.getenv("password")
    bot.run(pword)
    # Get member information

    await guild.chunk()  # Ensure all members are fetched
    members = guild.members

    username = member.name
    userID = member.id

    # Connect to MySQL database
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password=pword,
        database="Pickup"
    )
    cursor = db.cursor()

    # Define default values
    default_wins = 0
    default_losses = 0
    default_draws = 0
    default_win_percentage = 0.0
    default_last_played = None

    # Check if the member already exists in the database
    cursor.execute("SELECT UserID FROM UserRecords WHERE UserID = %s", (userID,))
    existing_member = cursor.fetchone()

    # If member doesn't exist, insert into the database
    if not existing_member:
        cursor.execute(
            "INSERT INTO UserRecords (UserID, Username, Wins, Losses, Draws, WinPercentage, LastPlayed) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (userID, username, default_wins, default_losses, default_draws, default_win_percentage,
             default_last_played))
        db.commit()


# Load commands from commands.py
async def setup_bot():
    # Wait until the bot is fully ready
    await bot.wait_until_ready()
    # Load commands from commands.py
    await bot.load_extension('commands')


# Define a function to run the bot
def main() -> None:
    # Run the bot with the provided token
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    bot.run(token)


# Run the bot if this file is executed directly
if __name__ == '__main__':
    main()
