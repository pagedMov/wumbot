import random
import string
import discord
from discord.ext import commands
import os
from plexapi.myplex import MyPlexAccount
from plexapi.video import Show, Episode
import requests
import json
import re
import asyncio
import subprocess

global home
home = os.path.expanduser('~')

print("Starting bot...")

httpd = None
plexpass = 'Wumboners!999'
plexserver = 'movserver'
plexuser = 'page710'
publicip = requests.get('https://api.ipify.org').text

print("Connecting to plex server...")

global plex
account = MyPlexAccount(plexuser, plexpass)
plex = account.resource(plexserver).connect()

print("Connected to plex server.")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
global sessions
sessions = {}

async def startstream(ctx, episode):
    cog = bot.get_cog('Session Commands')
    await cog.startstream(ctx, episode)

async def decide(ctx, choices):
    list = choices
    liststring = 'Pick an option (type the number):\n```'
    counter = 1
    for item in list:
        if isinstance(item, Episode) or isinstance(item, Show):
            liststring += f'{counter} - {item.title}\n'
        else:
            liststring += f'{counter} - {item}\n'
        counter += 1
    liststring += '```'
    await ctx.send(liststring)
    await ctx.send('type exit to cancel')

    undecided = True

    while undecided:
        choice = await bot.wait_for('message', check=lambda msg: msg.author == ctx.author)
        if choice.content.isdigit() and int(choice.content) <= len(list):
            choice = list[int(choice.content) - 1]
            return choice
        elif choice.content == 'exit':
            await ctx.send('Cancelling command.')
            return 'exit'
        else:
            await ctx.send('Invalid choice.')

async def session_factory(owner, sessionname, showkey, episode):
    class Session:
        def __init__(self, owner, sessionname, showkey, episode):
            self.plex = plex
            self.owner = owner
            self.sessionname = sessionname
            self.showkey = showkey
            self.episode = episode
            sessions[str(self.owner.id)] = self

        async def resume(self, ctx, episode):
            if isinstance(episode,int): # if episode has not been properly tied to an episode object
                episode = self.showkey.episodes()[episode] # then tie it
            await ctx.send(f'Starting stream at episode: {episode.title}')
            await startstream(ctx, episode)
        
        async def next(self, ctx):
            self.episode += 1
            episodes = self.showkey.episodes()
            if self.episode >= len(episodes):
                await ctx.send('No more episodes.')
                return
            episode = episodes[self.episode]
            await ctx.send(f'Starting next episode {episode.title}')
            await startstream(ctx, episode)

        async def previous(self, ctx):
            self.episode -= 1
            episodes = self.showkey.episodes()
            if self.episode < 0:
                await ctx.send('No previous episodes.')
                return
            episode = episodes[self.episode]
            await ctx.send(f'Starting previous episode {episode.title}')
            await startstream(ctx, episode)
        
        async def goto(self, ctx, episodenum):
            self.episode = episodenum - 1
            episodes = self.showkey.episodes()
            if episodenum not in range(len(episodes)):
                await ctx.send('Episode not found.')
                return
            episode = episodes[self.episode]
            await ctx.send(f'Going to episode {episodenum} - {episode.title}')
            await startstream(ctx, episode)

        
        async def end(self, ctx):
            next = self.episode + 1
            if next >= len(self.showkey.episodes()):
                os.remove(f'sessions/{self.sessionname}.txt')
                await ctx.send('No more episodes left, session deleted.')
                return
            filename = self.sessionname.replace(' ', '-')
            with open(f'sessions/{filename}.txt', 'w') as file:
                json.dump({'sessionname': self.sessionname, 'showkey': self.showkey.title, 'episode': next}, file)
                await ctx.send("Session data saved.")
            sessions[str(self.owner.id)] = None
            await ctx.send('Session ended.')

        async def list(self,ctx):
            episodes = self.showkey.episodes()
            episodestring = '```'
            for episode in episodes:
                episodestring += f'{episode.index} - {episode.title}\n'
            episodestring += '```'
            await ctx.send(episodestring)

    return Session(owner, sessionname, showkey, episode)


class ServerController:

    def __init__(self):
        self.servers = {}
        self.outputrelay = None
        if not os.path.exists('servers.txt') or not open('servers.txt').read():
            with open('servers.txt', 'w') as file:
                file.write('\n'.join(os.listdir(f'{home}/run/servers'))) # Write all server names to file, one per line

    async def startserver(self,ctx,game,verbose):
        if game in self.servers.keys():
            await ctx.send('Server already running.')
            return
        if game not in open('servers.txt').read():
            await ctx.send('Game not supported.')
            return
        if len(self.servers) >= 2:
            await ctx.send('Too many servers running.')
            return
        await ctx.send(f'Starting {game.capitalize()} server...')
        if verbose is True:
            await ctx.send("Outputting console lines.")
            with open('console.txt', 'w') as file:
                self.servers[game] = subprocess.Popen(f'{home}/run/servers/{game}',stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=file,shell=True)
            if self.outputrelay:
                self.outputrelay.cancel()
            self.outputrelay = asyncio.create_task(self.relayoutput(ctx))
        else:
            self.servers[game] = subprocess.Popen(f'{home}/run/servers/{game}',stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=True)
            await ctx.send("Not outputting console lines.")
        await ctx.send(f'{game.capitalize()} server started.')

    async def stopserver(self,ctx,game):
        if game not in self.servers:
            await ctx.send('Server not running.')
            return
        commoncommands = ['stop','quit','exit']
        self.outputrelay = None
        for command in commoncommands:
            self.servers[game].stdin.write(command.encode())
            self.servers[game].stdin.flush()
        await self.servers[game].terminate()
        self.servers[game] = None


    async def relayoutput(self,ctx):
        with open('console.txt', 'r') as file: #read from the console file that is being written to by the server
            file.seek(0,2)
            last_line_sent = None
            while True:
                line = file.readline()
                if not line:
                    await asyncio.sleep(1)
                    continue
                if line != last_line_sent:
                    await ctx.send(line)
                    last_line_sent = line
    
    async def startrelay(self,ctx,game):
        if not self.outputrelay:
            self.outputrelay = asyncio.create_task(self.relayoutput(ctx,self.servers[game]))
    
    async def stoprelay(self):
        if self.outputrelay:
            self.outputrelay.cancel()
            self.outputrelay = None
    
    async def rcon(self,ctx,game,command):
        if game not in self.servers.keys():
            await ctx.send('Server not running.')
            return
        await ctx.send(f'Sending command: {command}')
        self.servers[game].stdin.write(command.encode())
        self.servers[game].stdin.flush()
        


class SessionCommands(commands.Cog, name="Session Commands"):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(help='''Start a new session. Provide a session name under 20 characters.\n
                     Sessions are deleted when all episodes have been watched.\n
                     Sessions start at episode 1, but you can override this-\n
                     -by typing a number after the session name.''')
    async def createsession(self, ctx,sessionname=None,episodeoverride=None):
        if str(ctx.guild.id) not in open('authservers.txt').read():
            await ctx.send('Server not authenticated.')
            return
        if not sessionname:
            await ctx.send('Please enter a session name after the command, i.e. !createsession <name>.')
            return
        if len(sessionname) > 20:
            await ctx.send('Session name too long.')
            return
        if not os.path.exists('sessions'):
            os.makedirs('sessions')
        if os.path.exists(f'sessions/{sessionname}.txt'):
            await ctx.send('Session name already exists.')
            return
        if str(ctx.author.id) in sessions and sessions[str(ctx.author.id)] is not None:
            await ctx.send('User already running existing session. Close it with !endsession first.')
            return
        if episodeoverride and not episodeoverride.isdigit():
            await ctx.send('The session name has to be all one word.')
            return
        
        shows = plex.library.section('Video').all()
        showchoice = await decide(ctx, shows)
        if showchoice == 'exit':
            return

        newsession = await session_factory(ctx.author,sessionname, showchoice, 0) if not episodeoverride else await session_factory(sessionname, showchoice.key, int(episodeoverride))
        sessions[str(ctx.author.id)] = newsession
        await ctx.send(f'Starting new session {sessionname} at episode {newsession.episode + 1}')
        await newsession.resume(ctx, showchoice.episodes()[newsession.episode])
        newsession = None

    @commands.command(help="End a session. This will save the session data for later.")
    async def endsession(self, ctx):
        if str(ctx.guild.id) not in open('authservers.txt').read():
            await ctx.send('Server not authenticated.')
            return
        session = sessions[str(ctx.author.id)]
        await ctx.send('Note: resuming the session will start at the next episode.')
        await ctx.send('Ending session...')
        await session.end(ctx)
    
    @commands.command(help="Resume a session. You will be prompted to pick a session\n from the list of existing sessions.")
    async def resumesession(self, ctx):
        if str(ctx.guild.id) not in open('authservers.txt').read():
            await ctx.send('Server not authenticated.')
            return
        if str(ctx.author.id) in sessions and sessions[str(ctx.author.id)] is not None:
                await ctx.send('User already running existing session. Close it with !endsession first.')
                return
        sessionslist = os.listdir('sessions')
        sessionchoice = await decide(ctx, sessionslist)
        if sessionchoice == 'exit':
            return

        filename = sessionchoice.replace(' ', '-')
        with open(f'sessions/{filename}', 'r') as file:
            sessiondata = json.load(file)
            showkey = None
            for item in plex.library.section('Video').all():
                if item.title == sessiondata['showkey']:
                    showkey = item
            session = await session_factory(ctx.author, sessiondata['sessionname'], showkey, sessiondata['episode'])
            sessions[str(ctx.author.id)] = session
            await session.resume(ctx, sessiondata['episode'])
    
    @commands.command(help="List all existing sessions.")
    async def listsessions(self, ctx):
        if str(ctx.guild.id) not in open('authservers.txt').read():
            await ctx.send('Server not authenticated.')
            return
        sessions = os.listdir('sessions')
        counter = 0
        sessionstring = '```'
        for session in sessions:
            counter += 1
            sessionstring += f"{counter} - {session}\n"
        sessionstring += '```'
        await ctx.send(sessionstring)
    
    @commands.command(help="Delete a session from the list of sessions.")
    async def deletesession(self, ctx):
        if str(ctx.guild.id) not in open('authservers.txt').read():
            await ctx.send('Server not authenticated.')
            return
        sessions = os.listdir('sessions')
        if not sessions:
            await ctx.send('No sessions found.')
            return
        sessionchoice = await decide(ctx, sessions)
        if sessionchoice == 'exit':
            return
        
        os.remove(f'sessions/{sessionchoice}')
        await ctx.send('Session deleted.')

    @commands.command(help="Move to the next episode in the session.")
    async def nextepisode(self, ctx):
        if str(ctx.author.id) in sessions.keys() and sessions[str(ctx.author.id)] is not None:
            await sessions[str(ctx.author.id)].next(ctx)
            return
        else:
            await ctx.send(f"No session found for user {ctx.author.name}.")

    @commands.command(help="Move to the previous episode in the session.")
    async def previousepisode(self, ctx):
        if str(ctx.author.id) in sessions.keys() and sessions[str(ctx.author.id)] is not None:
            await sessions[str(ctx.author.id)].previous(ctx)
            return
        else:
            await ctx.send(f"No session found for user {ctx.author.name}.")

        
    @commands.command(help="Use this to move the session to a specific episode")
    async def gotoepisode(self, ctx, episode):
        if not episode.isdigit():
            await ctx.send("Input a number.")
            return
        episode = int(episode)
        if str(ctx.author.id) in sessions.keys() and sessions[str(ctx.author.id)] is not None:
            await sessions[str(ctx.author.id)].goto(ctx,episode)
            return
        else:
            await ctx.send(f"No session found for user {ctx.author.name}.")
    @commands.command(help="List all episodes in the show of the current session.")
    async def listepisodes(self,ctx):
        if str(ctx.author.id) in sessions.keys() and sessions[str(ctx.author.id)] is not None:
            await sessions[str(ctx.author.id)].list(ctx)
            return
        else:
            await ctx.send(f"No session found for user {ctx.author.name}.")

    
    @commands.command(help="Manually start a stream without using the session system.\n Useful for testing, or if the session system breaks.")
    async def startstream(self, ctx,episode=None):
        global httpd
        if str(ctx.guild.id) not in open('authservers.txt').read():
            await ctx.send('Server not authenticated.')
            return
        
        if episode:
            await ctx.send('Attempting to start stream...')
            try:
                url = episode.getStreamURL()
                # url = f'{url}&?audioStreamID={audiochoice}&subtitleStreamID={subtitlechoice}'
                publicipdashes = publicip.replace('.', '-') 
                url = re.sub(r'https://.*\.db', f'https://{publicipdashes}.db', url)
                await ctx.send(f'Stream started at: ```{url}```')
                await ctx.send('Open this link by starting VLC media player, pressing Ctrl+N and pasting the link in the text box.') 
                await ctx.send ('This will work with other media players too if they have network stream support.')
                return
            except:
                await ctx.send('Some error occured, idk')
                return

        shows = plex.library.section('Video').all()
        showchoice = await decide(ctx, shows)
        if showchoice == 'exit':
            return
        
        episodes = showchoice.episodes()
        episodechoice = await decide(ctx, episodes)
        if episodechoice == 'exit':
            return

        
        await ctx.send('Attempting to start stream...')
        url = episodechoice.getStreamURL()
        publicipdashes = publicip.replace('.', '-') 
        url = url.replace('192-168-1-187', publicipdashes)
        await ctx.send(f'Stream started at: ```{url}```')
        await ctx.send('Open this link by starting VLC media player, pressing Ctrl+N and pasting the link in the text box. This will work with other media players too if they have network stream support.')
        #await ctx.send('(Note: for some god forsaken reason, right clicking the link message and then clicking copy text does not work with VLC, the link won`t work. You have to highlight it and then do Ctrl+C. Do not ask. I have no idea.)')

class ServerCommands(commands.Cog, name="Server Commands"):
    def __init__(self, bot):
        self.bot = bot
        self.controller = ServerController()

    @commands.command(help="List all game servers currently supported.")
    async def listservers(self, ctx):
        if self.controller.servers != {}:
            serverstring = '```'
            for key in self.controller.servers.keys():
                serverstring += f'{key}\n'
            serverstring += '```'
            await ctx.send(serverstring)
        else:
            await ctx.send('No servers running.')
    
    @commands.command(help="Start a game server by picking one from the list.")
    async def startserver(self, ctx):
        if str(ctx.guild.id) not in open('authservers.txt').read():
            await ctx.send('Server not authenticated.')
            return
        
        serverlist = open('servers.txt').read().split('\n')
        serverchoice = await decide(ctx, serverlist)
        if serverchoice == 'exit':
            return
        verboseoptions = ['yes', 'no']
        await ctx.send('Want me to output the server console here? (This can be kind of fucked up for some games, mainly source engine stuff)')
        verbosechoice = await decide(ctx, verboseoptions)
        if verbosechoice == 'exit':
            return
        verbosechoice = True if verbosechoice == 'yes' else False
        await self.controller.startserver(ctx, serverchoice,verbosechoice)
    
    @commands.command(help="Make the bot stop relaying console output")
    async def shutup(self,ctx):
        await self.controller.stoprelay()
    
    @commands.command(help="Makes the bot begin relaying server console output")
    async def consolerelay(self,ctx):
        servers = self.controller.servers
        if len(servers) > 1:
            serverchoice = await decide(ctx,servers)
            if serverchoice == 'exit':
                return
        else:
            serverchoice = servers.keys()[0]
        await self.controller.startrelay(serverchoice)
    
    @commands.command(help='''type !help rcon for this one.\n
                            This command will allow you to directly pass commands to the server.\n
                            It may not work for all servers, so if this breaks something, oh well.\n
                            Syntax is: !rcon <game> "<command>"\n
                            Example: !rcon minecraft "op pagedmov"\n
                            make sure that the game name is entered correctly.\n
                            You can find the game name by using !listservers.''')
    async def rcon(self,ctx,game,command):
        if str(ctx.guild.id) not in open('authservers.txt').read():
            await ctx.send('Server not authenticated.')
            return
        await self.controller.rcon(ctx,game,command)
    
    @commands.command(help="Stop a game server. Might be better to use !rcon <game> <killcommand> if this doesn't work.")
    async def stopserver(self, ctx):
        if str(ctx.guild.id) not in open('authservers.txt').read():
            await ctx.send('Server not authenticated.')
            return
        servers = [key for key in self.controller.servers.keys()]
        if len(servers) > 1:
            serverchoice = await decide(ctx,servers)
            if serverchoice == 'exit':
                return
        else:
            serverchoice = servers[0]
        await self.controller.stopserver(ctx,serverchoice)
        await ctx.send(f'{serverchoice} server stopped.')
        


class MiscCommands(commands.Cog, name= "Misc Commands"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(help="Get the bot's current latency.")
    async def ping(self, ctx):
        await ctx.send(f'Pong! {round(bot.latency * 1000)}ms')

    @commands.command(help="Authenticate the server to make use of bot commands.\n Ask pagedMov for the password.")
    async def password(self, ctx, userpass):

        if os.path.exists('password.txt'):
            password = open('password.txt').read()
        else:
            await ctx.send('Password not set.')
            return

        if not os.path.exists('authservers.txt'):
            with open('authservers.txt', 'w') as file:
                pass

        if str({ctx.guild.id}) in open('authservers.txt').read():
            await ctx.send('Server already authenticated.')
            return
        elif not userpass:
            await ctx.send('Please enter a password.')
        elif userpass == password:
            with open('authservers.txt', 'a') as file:
                file.write(f'{ctx.guild.id}\n')
            await ctx.send('Server authenticated.')
        else:
            await ctx.send('Incorrect password.')
    
    @commands.command(help="List all authenticated servers.")
    async def authservers(self, ctx):
        await ctx.send(f'current channel id: {ctx.guild.id}')
        await ctx.send(open('authservers.txt').read())
        if str(ctx.guild.id) in open('authservers.txt').read():
            await ctx.send('Server is authenticated.')

async def setup(bot):
    await bot.add_cog(SessionCommands(bot))
    await bot.add_cog(MiscCommands(bot))
    await bot.add_cog(ServerCommands(bot))

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.event
async def on_guild_join(guild):
    print(f'Joined {guild.name}')

import asyncio

async def setup_bot():
    if os.getenv('DISCORD_BOT_TOKEN'):
        await setup(bot)
        return os.getenv('DISCORD_BOT_TOKEN')
    else:
        await setup(bot)
        return open('token.txt').read()

# Create an event loop
loop = asyncio.get_event_loop()

# Use the event loop to run the asynchronous function
token = loop.run_until_complete(setup_bot())

# Start the bot
bot.run(token)
