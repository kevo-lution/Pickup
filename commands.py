import discord
from discord.ext import commands
import os
import asyncio
import random
import psycopg2
import datetime

class MyCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # Dictionary to store multiple queues
        self.user_queue_mapping = {}  # Dictionary to store user-queue mappings
        # add an on-member-join to add them to the MySQL server

    async def chooseCaps(self, ctx):
        nickname = ctx.author.nick or ctx.author
        queue_id = self.user_queue_mapping[ctx.author.id]
        queue_info = self.queues[queue_id]
        captains = []
        rancap = []
        first_pick = None
        second_pick = None
        lobby = []

        await ctx.send(
            "Are we doing random captains, or choosing?\n Enter 'r' for random and 'c' for to volunteer yourself.")

        def check(message):
            return message.channel == ctx.channel and message.author != self.bot.user and ctx.author in queue_info[
                'members']

        # message.channel ensures it is in the same channel it was invoked in
        # message.author.id this part checks if the message.author.id is also a member in the queue.id
        while len(captains) < 2:
            try:
                message = await self.bot.wait_for('message', check=check)
                text = message.content.lower()
                # rancap.append(ctx.author)
                if text == 'r':
                    rancap.append(message)
                    if len(rancap) > 0:
                        await ctx.send("We are doing random captains!")
                        captains = random.sample(queue_info['members'], 2)
                        await ctx.send(f"The captains are {captains[0].mention} and {captains[1].mention}")
                        first_pick = random.choice(captains)
                        second_pick = captains[0] if first_pick == captains[1] else captains[1]
                        await ctx.send(f"{first_pick.mention} your pick!")
                        lobby = [player for player in queue_info['members'] if player not in captains]
                    else:
                        await ctx.send(f"{message.author.mention} has chosen themselves as a captain.")
                        captains.append(message.author)
                        if len(captains) == 2:
                            await ctx.send(f"The captains are {captains[0].nick} and {captains[1].nick}")
                            first_pick = random.choice(captains)
                            second_pick = captains[0] if first_pick == captains[1] else captains[1]
                            await ctx.send(f"{first_pick.mention} has the first pick!")
                            lobby = [player for player in queue_info['members'] if player not in captains]
                elif text == 'c':
                    # Handle the case when captains are chosen manually
                    await ctx.send(f"{message.author.mention} has chosen themselves as a captain.")
                    captains.append(message.author)
                    if len(captains) == 2:
                        await ctx.send(f"The captains are {captains[0].nick} and {captains[1].nick}")
                        first_pick = random.choice(captains)
                        second_pick = captains[0] if first_pick == captains[1] else captains[1]
                        await ctx.send(f"{first_pick.mention} has the first pick!")
                        lobby = [player for player in queue_info['members'] if player not in captains]
                elif text == ',leaveq':
                    # this checks if user is in queue
                    if ctx.author.id in self.user_queue_mapping:
                        await self.leaveq(ctx)


                elif text == ',endq':
                    await self.endq(self, ctx)
                else:
                    await ctx.send("Not the correct letters, please try again.")
            except asyncio.TimeoutError:
                await ctx.send("After a long deliberation, we will be choosing random captains.")

        team_a = []
        team_b = []

        await self.chooseTeams(ctx, first_pick, second_pick, team_a, "A", lobby)
        await self.chooseTeams(ctx, second_pick, first_pick, team_b, "B", lobby)
        if not lobby:
            await self.announceTeams(self, ctx, team_a, team_b)

    async def chooseTeams(self, ctx, first_pick, second_pick, team, team_label, lobby):
        queue_id = self.user_queue_mapping[ctx.author.id]
        queue_info = self.queues[queue_id]
        await ctx.send(f"{first_pick.mention} has the first pick, go ahead and enter a number.")
        for index, player in enumerate(lobby):
            await ctx.reply(f"{index + 1}. {player.mention}")

        def check(message):
            return message.author == first_pick and message.channel == ctx.channel and message.content.isdigit() and 0 < int(
                message.content) <= len(lobby)
        # message.channel ensures it is in the same channel it was invoked in
        # message.author.id this part checks if the message.author.id is also a member in the queue.id

        try:
            message = await self.bot.wait_for('message', check=check, timeout=60)
            selected_index = int(message.content) - 1
            selected_player = lobby.pop(selected_index)
            team.append(selected_player)
            await ctx.send(f"{selected_player.mention} has been added to Team {team_label}.")

            # Print out the team of the player who made the pick
            team_str = ', '.join(member.mention for member in team)
            await ctx.send(f"{first_pick.mention}'s team: {team_str}")

            if first_pick == second_pick:
                next_pick = await self.switchCaptain(first_pick, team, lobby)
                await ctx.send(f"{next_pick.mention} has the next pick!")

        except asyncio.TimeoutError:
            await ctx.send("Team selection timed out.")
            return

        # start timer and prompt bot to ask random captain ephemeral mssage
        # if match is over after 10 minutes, if y, move them to main channel again
        # if no reply or n restart timer
        # ask for if Team A or B won in ephemeral message from both captains
        # shows record for that team of players
        await ctx.send(queue_info['members'])
    # Make sure this function works!!
    async def announceTeams(self, ctx, team_a, team_b):
        await ctx.send(f"The teams are \n {team_a} \n vs.\n {team_b}")
        await self.teamChannels(self, ctx, team_a, team_b)

    async def teamChannels(self, ctx, player1, player2, team_a, team_b, queue_info):
        guild = ctx.guild
        admin_role = discord.utils.get(guild.roles,
                                       name="Super Saiyan Blue", )  # Replace "Admin" with the name of your admin role

        pickup_role = discord.utils.get(guild.roles, name="PickUp")

        # Check if both roles are found
        if admin_role and pickup_role:
            # Replace the existing admin_role with the newly found roles
            admin_role = pickup_role

        bot_member = guild.get_member(ctx.bot.user.id)  # Get the bot's member object

        # Check if the bot has the necessary permissions

        queue_id = self.user_queue_mapping[ctx.author.id]
        queue_info = self.queues[queue_id]

        player1_member = guild.get_member_named(player1)
        player2_member = guild.get_member_named(player2)
        # Append player1 to team_a
        team_a.append(player1_member.name)

        # Append player2 to team_b
        team_b.append(player2_member.name)

        # Create the voice channel for Team A with permissions set
        overwrites_team_a = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            # Deny permission for @everyone to see channel
            admin_role: discord.PermissionOverwrite(view_channel=True),
            pickup_role: discord.PermissionOverwrite(view_channel=True)
            # only allow admins to see every channel in the discord
        }
        vc_team_a = await guild.create_voice_channel("Team A", user_limit=None, overwrites=overwrites_team_a)
        for member in team_a:
            player_member = guild.get_member_named(member)
            if player_member:
                await player_member.move_to(vc_team_a)
        if player1_member:
            await player1_member.move_to(vc_team_a)

        # Create the voice channel for Team B with permissions set
        overwrites_team_b = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            # Deny permission for @everyone to see channel
            admin_role: discord.PermissionOverwrite(view_channel=True),
            pickup_role: discord.PermissionOverwrite(view_channel=True)
            # only allow admins to see every channel in the discord
        }
        vc_team_b = await guild.create_voice_channel("Team B", user_limit=None, overwrites=overwrites_team_b)
        for member in team_b:
            player_member = guild.get_member_named(member)
            if player_member:
                await player_member.move_to(vc_team_b)
        if player2_member:
            await player2_member.move_to(vc_team_b)

        await self.match_end(ctx, vc_team_a, vc_team_b, player1_member, player2_member, team_a, team_b, queue_info)

    async def match_end(self, ctx, vc_team_a, vc_team_b, player1_member, player2_member, team_a, team_b, queue_info):
        guild = ctx.guild
        just_chillin_channel = discord.utils.get(guild.voice_channels, name="Madden")

        async def delete_voice_channels(self, ctx):
            if guild.me.guild_permissions.manage_channels:
                try:
                    if vc_team_a:
                        await vc_team_a.delete()
                    if vc_team_b:
                        await vc_team_b.delete()
                except Exception as e:
                    print(f"Error occurred while deleting voice channels: {e}")
            else:
                await ctx.send("I don't have the necessary permissions to delete channels.")

        await asyncio.sleep(4)
        await ctx.send("Enter 'done' when the match has concluded. You have 20 minutes.")

        def check(message):
            return (
                    message.content.lower() == 'done'
                    and message.channel == ctx.channel
                    and message.author != ctx.bot.user
                    and message.author in queue_info['members']
            )

        winning_members = []
        losing_members = []

        try:
            message = await self.bot.wait_for('message', check=check, timeout=1200)
            text = message.content.lower()

            if text == 'done':
                if just_chillin_channel:
                    for member in queue_info['members']:
                        await member.move_to(just_chillin_channel)
                await delete_voice_channels(self, ctx)
                await ctx.send("Thank you, you have been moved to Just Chillin.")

            await ctx.send("Which team won the match? Enter 'A' or 'B'.")

            def check_winner(m):
                return (
                        m.content.lower() in ['a', 'b']
                        and m.channel == ctx.channel
                        and m.author != ctx.bot.user
                        and m.author in queue_info['members']
                )

            winner_message = await self.bot.wait_for('message', check=check_winner, timeout=600)

            if winner_message.content.lower() == 'a' or winner_message.content.lower() == 'b':
                winning_team = team_a if winner_message.content.lower() == 'a' else team_b
                losing_team = team_b if winner_message.content.lower() == 'a' else team_a

                # Fetch members of winning team
                winning_members = [guild.get_member_named(member_name) for member_name in winning_team]

                # Fetch members of losing team
                losing_members = [guild.get_member_named(member_name) for member_name in losing_team]

                await ctx.send(f"{losing_members[0].mention}, please confirm the result by replying with 'yes'.")

                def check_loser(m):
                    return (
                            m.content.lower() in ['yes', 'no']
                            and m.channel == ctx.channel
                            and m.author != ctx.bot.user
                            and m.author == losing_members[0]
                    )

                confirm_message = await self.bot.wait_for('message', check=check_loser, timeout=1200)
                print(confirm_message.content)

                if confirm_message.content.lower() == 'yes':
                    await ctx.send(
                        f"Congrats to {' and '.join([member.mention for member in winning_members])}'s team!")
                if confirm_message.content.lower() == 'no':
                    await ctx.send(f"Please contact Majin Bver or bverr to solve this dispute")


                    # Update statistics
                    await self.updateStats(ctx, guild, winning_team, winning_members, losing_team, losing_members)

        except asyncio.TimeoutError:
            await ctx.send("You didn't respond within the timeout period.")
        except Exception as e:
            print(f"An error occurred: {e}")

        await self.updateStats(ctx, guild, winning_team, winning_members, losing_team, losing_members)

    async def updateStats(self, ctx, guild, winning_team, winning_members, losing_team, losing_members):

        # Connect to MySQL database
        pword = os.getenv("password")
        hst = os.getenv("host")
        ser = os.getenv("user")
        base = os.getenv("database")


        # Connect to MySQL database
        db = psycopg2.connect(
            host=hst,
            user=ser,
            password=pword,
            database=base
        )
        cursor = db.cursor()

        for members in winning_team:
            member = guild.get_member_named(members)
            if member:
                # Update records for the winning team
                update_query_w = "UPDATE UserRecords SET Wins = Wins + 1 WHERE Username = %s"
                cursor.execute(update_query_w, (member.name,))
                db.commit()
                cursor.close()

        for members in losing_team:
            member = guild.get_member_named(members)
            if member:
                # Update records for the losing team
                cursor = db.cursor()
                update_query_l = "UPDATE UserRecords SET Losses = Losses + 1 WHERE Username = %s"
                cursor.execute(update_query_l, (member.name,))
                db.commit()
                cursor.close()

        await ctx.send(f"We have added updated wins and losses to each member of each team")

        await self.endingq(ctx)

    async def endingq(self, ctx):
        queue_ids = list(self.queues.keys())  # Create a copy of queue IDs

        for queue_id in queue_ids:
            if queue_id in self.queues:
                queue_members = list(self.queues[queue_id]['members'])  # Create a copy of queue members
                for member in queue_members:
                    self.user_queue_mapping.pop(member.id, None)
                self.queues.pop(queue_id, None)  # Remove the queue

        await ctx.send("The lobby has been cleared. \n To play another match, use the ',que' command! ")

    @commands.command()
    async def que(self, ctx):
        # Check if the user is already in a queue
        if ctx.author.id in self.user_queue_mapping:
            await ctx.send("You are already in a queue.")
            return

        # Check if the queue size has been specified
        if ctx.author.id not in self.queues:
            # If the user is not already in a queue, ask for queue size
            await ctx.send("How many players will be playing? (Including yourself)")

            def check(message):
                return message.author == ctx.author and message.channel == ctx.channel

            try:
                message = await self.bot.wait_for('message', timeout=30.0, check=check)
                queue_size = int(message.content)

                if queue_size <= 0 or queue_size > 8 or queue_size % 2 != 0:
                    await ctx.send("Please enter a valid even number of players between 2 and 8.")
                    return

                # Store the user's nickname when invoking the que command
                self.user_queue_mapping[ctx.author.id] = ctx.author.nick or ctx.author

                # Create a new queue
                self.queues[ctx.author.id] = {
                    'size': queue_size,
                    'members': [ctx.author]
                }
                await ctx.send(f"The queue has been created with a size of {queue_size}.")
                # await ctx.send(f"{self.user_queue_mapping[ctx.author.id]} has been added to the queue.")
                # the line above will comment that the creator of the queue has been added to the queue

                # Calculate and display the number of open spots in the queue
                open_spots = queue_size - 1
                if open_spots == 1:
                    await ctx.send(f"There is {open_spots} open spot left in the queue.")
                else:
                        await ctx.send(f"There are {open_spots} open spots left in the queue.")

            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond. The queue command has timed out.")
            except ValueError:
                await ctx.send("Please enter a valid number of players.")
        else:
            await ctx.send("You are already in a queue.")

    @commands.command()
    async def join(self, ctx):
        # Check if the user is already in a queue
        if ctx.author.id in self.user_queue_mapping:
            await ctx.send("You are already in a queue.")
            return

        # Check if there are active queues
        if not self.queues:
            await ctx.send("There are no active queues.")
            return

        # If there is only one active queue, directly add the user to it
        if len(self.queues) == 1:
            queue_id, queue_info = next(iter(self.queues.items()))
            queue_size = queue_info['size']
            num_members = len(queue_info['members'])
            open_spots = queue_size - num_members

            if open_spots > 0:
                self.queues[queue_id]['members'].append(ctx.author)
                self.user_queue_mapping[ctx.author.id] = queue_id
                await ctx.send(f"{ctx.author.display_name} has joined the queue.")

                # Check if any queue is full and announce the players
                full_queues = [queue_id for queue_id, queue_info in self.queues.items() if
                               len(queue_info['members']) == queue_info['size']]
                for queue_id in full_queues:
                    queue_info = self.queues[queue_id]
                    queue_members = queue_info['members']
                    queue_size = queue_info['size']

                    # Extract display names of the players
                    player_names = [member.display_name if member.nick else member.name for member in queue_members]

                    # Notify that the queue is full
                    await ctx.send("The queue is now full.")

                    if queue_size == 2:
                        await ctx.send(f"{player_names[0]} vs. {player_names[1]} are about to play!")
                        await self.teamChannels(ctx, player_names[0], player_names[1], [], [],queue_info)
                    elif 4 <= queue_size <= 8:
                        lobby_message = ""
                        for i in range(0, queue_size, 2):
                            player1 = player_names[i]
                            player2 = player_names[i + 1] if i + 1 < len(player_names) else None
                            lobby_message += f"{player1}"
                            if player2:
                                lobby_message += f", {player2}\n"
                            else:
                                lobby_message += "\n"

                        await ctx.send(lobby_message + "are in the lobby!")

                        if queue_size == 4:
                            await self.chooseCaps(ctx)
                        elif queue_size == 6:
                            await self.chooseCaps(ctx)
                        elif queue_size == 8:
                            await self.chooseCaps(ctx)

                # Calculate and display the number of open spots in the queue
                open_spots = queue_size - len(self.queues[queue_id]['members'])
                if open_spots >= 1:
                    await ctx.send(f"There are {open_spots} open spots left in the queue.")
            else:
                await ctx.send("The queue is already full.")
        else:
            # If there are multiple active queues, show them to the user and prompt them to choose a queue
            nickname = ctx.author.nick or ctx.author
            message = "Multiple queues are active. Please choose a queue to join by number:\n"
            for idx, (queue_id, queue_info) in enumerate(self.queues.items(), 1):
                queue_size = queue_info['size']
                num_members = len(queue_info['members'])
                open_spots = queue_size - num_members
                message += f"Queue {idx}: {nickname}'s Queue, {open_spots} open spots\n"
            await ctx.send(message)

            def check(message):
                return message.author == ctx.author and message.channel == ctx.channel

            try:
                message = await self.bot.wait_for('message', timeout=30.0, check=check)
                queue_number = int(message.content)

                if queue_number < 1 or queue_number > len(self.queues):
                    await ctx.send(f"{nickname} Please enter a valid queue number.")
                    return

                selected_queue_id = list(self.queues.keys())[queue_number - 1]
                selected_queue_info = self.queues[selected_queue_id]
                selected_queue_members = selected_queue_info['members']

                if len(selected_queue_members) < selected_queue_info['size']:
                    selected_queue_members.append(ctx.author)
                    self.user_queue_mapping[ctx.author.id] = selected_queue_id
                    await ctx.send(f"{ctx.author.display_name} has joined Queue {queue_number}.")

                    # Calculate and display the number of open spots in the queue
                    open_spots = selected_queue_info['size'] - len(selected_queue_members)
                    if open_spots > 1:
                        await ctx.send(f"There are {open_spots} open spots left in Queue {queue_number}.")
                else:
                    await ctx.send("The selected queue is already full.")

            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond. Join command has timed out.")
            except ValueError:
                await ctx.send("Please enter a valid queue number.")

    @commands.command()
    async def viewq(self, ctx):
        if not self.queues:
            await ctx.send("There are no active queues.")
            return

        for idx, (user_id, queue_info) in enumerate(self.queues.items(), 1):
            queue_size = queue_info['size']
            num_members = len(queue_info['members'])
            open_spots = queue_size - num_members
            await ctx.send(f" Queue {idx}: Queue, {open_spots} open spots\n")

    @commands.command()
    async def leaveq(self, ctx):
        # Check if the user is in a queue
        if ctx.author.id in self.user_queue_mapping:
            # Get the queue ID the user is in
            queue_id = self.user_queue_mapping[ctx.author.id]

            # Check if the queue exists
            if queue_id in self.queues:
                # Remove the user from the queue
                self.queues[queue_id]['members'].remove(ctx.author)
                del self.user_queue_mapping[ctx.author.id]
                await ctx.send(f"{ctx.author.display_name} has left the queue.")
                return

        await ctx.send("You are not in a queue.")

    @commands.command()
    async def clearq(self, ctx, target_member: discord.Member = None):
        if not target_member:
            target_member = ctx.author

        if target_member.id in self.queues:
            # Clear the queue to remove all users
            self.queues.pop(target_member.id, None)
            self.user_queue_mapping.pop(target_member.id, None)
            await ctx.send(f"The queue for {target_member.display_name} has been cleared.")
        else:
            await ctx.send(f"{target_member.display_name} is not in any queue.")

    @commands.command()
    async def endq(self, ctx):
        queue_id = ctx.author.id
        if queue_id in self.queues:
            queue_members = list(self.queues[queue_id]['members'])  # Create a copy of queue members
            for member in queue_members:
                self.user_queue_mapping.pop(member.id, None)
            self.queues.pop(queue_id, None)  # Remove the queue
            await ctx.reply("Your queue has been ended. Only the creator of the queue can end queues, members must leave queues.")
        else:
            await ctx.reply("You are not in any queue.")

    @commands.command()
    async def ff(self, ctx):
        nickname = ctx.author.nick
        await ctx.reply(f'{nickname} from ... has forfeited the match, Can someone from ... confirm?')
        # add a loss the forfeiters record.

    @commands.command()
    async def rm(self, ctx):
        await ctx.reply("Loser ahh tryna run it back")
        #ask other captain in the queue if they would like to rematch




        # Database Related Commands, Super Saiyan Blue Roles ONLY


    @commands.command()
    async def wl(self, ctx, *users: discord.Member):
        guild = ctx.guild  # Fetch the guild object
        nickname = ctx.author.nick
        pword = os.getenv("password")
        hst = os.getenv("host")
        ser = os.getenv("user")
        base = os.getenv("database")

            # Connect to MySQL database
        db = psycopg2.connect(
            host=hst,
            user=ser,
            password=pword,
            database=base
        )
        cursor = db.cursor()

        # Get all members from the Discord server
        await guild.chunk()  # Ensure all members are fetched
        members = guild.members
        if not users:  # If no users are mentioned, retrieve the record for the command invoker
            user_id = ctx.author.id
            username = ctx.author.nick
        else:  # If users are mentioned, retrieve records for each mentioned user
            user_id = users[0].id
            username = users[0].nick  # For the first mentioned user
        # Query the database to retrieve the win/loss record associated with the user ID
        cursor.execute("SELECT Wins, Losses FROM UserRecords WHERE UserID = %s", (user_id,))
        record = cursor.fetchone()  # Assuming one row per user
        if record:
            wins, losses = record
            await ctx.send(f"{username} has a win/loss record of {wins} - {losses}.")
        else:
            await ctx.send(f"No record found for {username}.")


    @commands.command()
    async def addw(self, ctx, member: discord.Member = None):
        if member is None:
            await ctx.send("You need to mention a user to add a win.")
            return


        if discord.utils.get(ctx.author.roles, name="Super Saiyan Blue"):
            pword = os.getenv("password")
            hst = os.getenv("host")
            ser = os.getenv("user")
            base = os.getenv("database")


            # Connect to MySQL database
            db = psycopg2.connect(
                host=hst,
                user=ser,
                password=pword,
                database=base
            )
            cursor = db.cursor()
            update_query = "UPDATE UserRecords SET Wins = Wins + 1 WHERE Username = %s"
            cursor.execute(update_query, (member.name,))
            db.commit()
            cursor.close()
            await ctx.send(f"Added a win to {member.display_name}'s record.")
        else:
            await ctx.send("You do not have permission to use this command.")

    @commands.command()
    async def addl(self, ctx, member: discord.Member):
        # have to @ a member, even if it is yourself
        if member is None:
            await ctx.send("You need to mention a user to add a loss.")
            return

        if discord.utils.get(ctx.author.roles, name="Super Saiyan Blue"):
            pword = os.getenv("password")
            hst = os.getenv("host")
            ser = os.getenv("user")
            base = os.getenv("database")


            # Connect to MySQL database
            db = psycopg2.connect(
                host=hst,
                user=ser,
                password=pword,
                database=base
            )
            cursor = db.cursor()
            update_query = "UPDATE UserRecords SET Losses = Losses + 1 WHERE Username = %s"
            cursor.execute(update_query, (member.name,))
            db.commit()
            cursor.close()
            await ctx.send(f"Added a loss to {member.display_name}'s record.")
            await asyncio.sleep(5)
            await ctx.message.delete()
        else:
            await ctx.send("You do not have permission to use this command.")

    @commands.command()
    async def removew(self, ctx, member: discord.Member):
        if member is None:
            await ctx.send("You need to mention a user to remove a win.")
            return

        if discord.utils.get(ctx.author.roles, name="Super Saiyan Blue"):
            pword = os.getenv("password")
            hst = os.getenv("host")
            ser = os.getenv("user")
            base = os.getenv("database")


            # Connect to MySQL database
            db = psycopg2.connect(
                host=hst,
                user=ser,
                password=pword,
                database=base
            )
            cursor = db.cursor()
            update_query = "UPDATE UserRecords SET Wins = Wins - 1 WHERE Username = %s"
            cursor.execute(update_query, (member.name,))
            db.commit()
            cursor.close()
            await ctx.send(f"Removed a win from {member.display_name}'s record.")
            await asyncio.sleep(5)
            await ctx.message.delete()
        else:
            await ctx.send("You do not have permission to use this command.")

    @commands.command()
    async def removel(self, ctx, member: discord.Member):
        pword = os.getenv("password")

        if discord.utils.get(ctx.author.roles, name="Super Saiyan Blue"):
            if member is None:
                await ctx.send("You need to mention a user to remove a loss.")
                return
            if discord.utils.get(ctx.author.roles, name="Super Saiyan Blue"):
                pword = os.getenv("password")
                hst = os.getenv("host")
                ser = os.getenv("user")
                base = os.getenv("database")


                # Connect to MySQL database
                db = psycopg2.connect(
                    host=hst,
                    user=ser,
                    password=pword,
                    database=base
                )
                cursor = db.cursor()
                update_query = "UPDATE UserRecords SET Losses = Losses - 1 WHERE Username = %s"
                cursor.execute(update_query, (member.name,))
                db.commit()
                cursor.close()
                await ctx.send(f"Removed a loss to {member.mention}'s record.")
                await asyncio.sleep(5)
                await ctx.message.delete()
        else:
            await ctx.send("You do not have permission to use this command.")

    @commands.command()
    async def fetch(self, ctx, *users: discord.Member):
        await self.fetching(ctx, users)
        message = await ctx.send("Members have been fetched and inserted into the MySQL table.")

        # Define a check function for wait_for
        def check(message):
            return message.author == ctx.author and message.channel == ctx.channel



    async def fetching(self, ctx, users):
        guild = ctx.guild  # Fetch the guild object
        pword = os.getenv("password")
        hst = os.getenv("host")
        ser = os.getenv("user")
        base = os.getenv("database")


        # Connect to MySQL database
        db = psycopg2.connect(
            host=hst,
            user=ser,
            password=pword,
            database=base,
            port = 5432
        )
        cursor = db.cursor()

        await guild.chunk()  # Ensure all members are fetched
        members = guild.members

        # Define default values
        default_wins = 0
        default_losses = 0
        default_draws = 0
        default_win_percentage = 0.0
        default_last_played = None

        # Insert each member into the MySQL table
        if member not in members:
            for member in members:
                username = member.name  # You can choose which information to insert
                userID = member.id
                # Replace default values with actual values or remove them if not needed
                cursor.execute(
                    "INSERT INTO UserRecords (UserID, Username, Wins, Losses, Draws, WinPercentage, LastPlayed) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (userID, username, default_wins, default_losses, default_draws, default_win_percentage,
                     default_last_played))
                db.commit()

        # Close database connection when done
            cursor.close()
            db.close()

    @commands.command()
    async def help(self, ctx):
        # Display list of available commands as an ephemeral message
        command_list = "\n".join([
            "Available commands for all Users:",
            ",que - Create a queue",
            ",join - Join a queue",
            ",endq - Delete a queue",
            ",leaveq - Leave a queue",
            ",viewq - View available queues",
            ",rm - Initiate a rematch (still in progress)",
            ",ff - Forfeit a match (still in progress)",
            ",wl @user - show a users overall record"
            "\n"
            "\n"
            "Admin Role Commands:"
            ",addw - Adds a W in the case where it was not added"
            ",addl - Adds an L in the case where it was not added"
            ",removew - Removes a W in case it was added incorrectly"
            ",removel -  Removes an L in the case where it was added incorrectly"
            ""

        ])
        await ctx.reply(command_list, ephemeral=True)

    @commands.command()
    async def faq(self, ctx):
        faq_list = "\n".join([
            "Commonly asked questions:"
            "Why doesn't my match start? ALL users must be in a discord channel in the server in order to process the next step",
            "Why doesn't my Playstation/Xbox not let me join Discord calls. \n"
            "Make sure your discord and Xbox/Playstation accounts are connected and join the call through the phone"
            "Only the person who created the queue can use the , endq command"
            "Only the people who join the queue are able to use the , leaveq command"
            "If someone is AFK or unable to leaveq, use the , clearq command ton reset the queue"
            "If you are unable to dispute a win/loss, contact Majin Bver to correct your public records."

        ])



# Define a setup function to load the cog into the bot
async def setup(bot):
    # Add the MyCommands cog to the bot
    await bot.add_cog(MyCommands(bot))
