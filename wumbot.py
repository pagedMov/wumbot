import random
import string
import discord
from discord.ext import commands
import os
from plexapi.myplex import MyPlexAccount
import requests
import json
import re

httpd = None
plexpass = 'Wumboners!999'
plexserver = 'movserver'
plexuser = 'page710'
publicip = requests.get('https://api.ipify.org').text

global plex
account = MyPlexAccount(plexuser, plexpass)
plex = account.resource(plexserver).connect()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
sessions = {}


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
            with open(f'sessions/{self.sessionname}.txt', 'w') as file:
                json.dump({'sessionname': self.sessionname, 'showkey': self.showkey.title, 'episode': next}, file)
                await ctx.send("Session data saved.")
            sessions[str(self.owner.id)] = None
            await ctx.send('Session ended.')
    return Session(owner, sessionname, showkey, episode)

        
    

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.event
async def on_guild_join(guild):
    print(f'Joined {guild.name}')


@bot.command(help="Start a new session. Provide a session name under 20 characters. Sessions are deleted when all episodes have been watched. Sessions start at episode 1, but you can override this by typing a number after the session name.")
async def createsession(ctx,sessionname=None,episodeoverride=None):
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
    
    shows = plex.library.section('Video').all()
    showstring = 'Pick a show (type the number):\n```'
    counter = 1
    for show in shows:
        showstring += f'{counter} - {show.title}\n'
        counter += 1
    showstring += '```'
    await ctx.send(showstring)
    await ctx.send('type exit to cancel')

    undecided = True

    while undecided:
        showchoice = await bot.wait_for('message', check=lambda msg: msg.author == ctx.author)
        if showchoice.content.isdigit() and int(showchoice.content) <= len(shows):
            showchoice = shows[int(showchoice.content) - 1]
            undecided = False
        elif showchoice.content == 'exit':
            return
        else:
            await ctx.send('Invalid choice.')
    newsession = await session_factory(ctx.author,sessionname, showchoice, 0) if not episodeoverride else await session_factory(sessionname, showchoice.key, int(episodeoverride))
    sessions[str(ctx.author.id)] = newsession
    await ctx.send(f'Starting new session {sessionname} at episode {newsession.episode + 1}')
    await newsession.resume(ctx, showchoice.episodes()[newsession.episode])
    newsession = None

@bot.command(help="End a session. This will save the session data for later.")
async def endsession(ctx):
    if str(ctx.guild.id) not in open('authservers.txt').read():
        await ctx.send('Server not authenticated.')
        return
    session = sessions[str(ctx.author.id)]
    await ctx.send('Ending session...')
    await session.end(ctx)

@bot.command(help="Resume a session. You will be prompted to pick a session from the list of existing sessions.")
async def resumesession(ctx):
    if str(ctx.guild.id) not in open('authservers.txt').read():
        await ctx.send('Server not authenticated.')
        return
    if str(ctx.author.id) in sessions and sessions[str(ctx.author.id)] is not None:
            await ctx.send('User already running existing session. Close it with !endsession first.')
            return
    sessions = os.listdir('sessions')
    sessionstring = 'Pick a session (type the number):\n```'
    counter = 1
    for session in sessions:
        sessionstring += f'{counter} - {session}\n'
        counter += 1
    sessionstring += '```'
    await ctx.send(sessionstring)
    await ctx.send('type exit to cancel')

    undecided = True

    while undecided:
        sessionchoice = await bot.wait_for('message', check=lambda msg: msg.author == ctx.author)
        if sessionchoice.content.isdigit() and int(sessionchoice.content) <= len(sessions):
            sessionchoice = sessions[int(sessionchoice.content) - 1]
            undecided = False
        elif sessionchoice.content == 'exit':
            return
        else:
            await ctx.send('Invalid choice.')

    with open(f'sessions/{sessionchoice}', 'r') as file:
        sessiondata = json.load(file)
        showkey = None
        for item in plex.library.section('Video').all():
            if item.title == sessiondata['showkey']:
                showkey = item
        session = await session_factory(ctx.author, sessiondata['sessionname'], showkey, sessiondata['episode'])
        sessions[str(ctx.author.id)] = session
        await session.resume(ctx, sessiondata['episode'])

@bot.command(help="List all existing sessions.")
async def listsessions(ctx):
    if str(ctx.guild.id) not in open('authservers.txt').read():
        await ctx.send('Server not authenticated.')
        return
    sessions = os.listdir('sessions')
    sessionstring = '```'
    for session in sessions:
        sessionstring += f'{session}\n'
    sessionstring += '```'
    await ctx.send(sessionstring)

@bot.command(help="Delete a session. Provide the session name.")
async def deletesession(ctx):
    if str(ctx.guild.id) not in open('authservers.txt').read():
        await ctx.send('Server not authenticated.')
        return
    sessions = os.listdir('sessions')
    sessionstring = 'Pick a session to delete (type the number):\n```'
    counter = 1
    for session in sessions:
        sessionstring += f'{counter} - {session}\n'
        counter += 1
    sessionstring += '```'
    await ctx.send(sessionstring)
    await ctx.send('type exit to cancel')

    undecided = True

    while undecided:
        sessionchoice = await bot.wait_for('message', check=lambda msg: msg.author == ctx.author)
        if sessionchoice.content.isdigit() and int(sessionchoice.content) <= len(sessions):
            sessionchoice = sessions[int(sessionchoice.content) - 1]
            undecided = False
        elif sessionchoice.content == 'exit':
            return
        else:
            await ctx.send('Invalid choice.')
    os.remove(f'sessions/{sessionchoice}')
    await ctx.send('Session deleted.')

@bot.command(help="Move to the next episode in the session.")
async def nextepisode(ctx):
    if str(ctx.author.id) in sessions.keys() and sessions[str(ctx.author.id)] is not None:
        await sessions[str(ctx.author.id)].next(ctx)
        return
    else:
        await ctx.send(f"No session found for user {ctx.author.name}.")

@bot.command(help="Move to the previous episode in the session.")
async def previousepisode(ctx):
    if str(ctx.author.id) in sessions.keys() and sessions[str(ctx.author.id)] is not None:
        await sessions[str(ctx.author.id)].previous(ctx)
        return
    else:
        await ctx.send(f"No session found for user {ctx.author.name}.")

    
@bot.command(help="Use this to move the session to a specific episode")
async def gotoepisode(ctx, episode):
    if not episode.isdigit():
        await ctx.send("Input a number.")
        return
    episode = int(episode)
    if str(ctx.author.id) in sessions.keys() and sessions[str(ctx.author.id)] is not None:
        await sessions[str(ctx.author.id)].goto(ctx,episode)
        return
    else:
        await ctx.send(f"No session found for user {ctx.author.name}.")

    
    
@bot.command(help="Receive generic response from the bot to make sure it's listening to commands")
async def ping(ctx):
    await ctx.send('pong')

@bot.command(help="Authenticate the server to make use of bot commands. Ask pagedMov for the password.")
async def password(ctx, userpass):

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
        await ctx.send('Server authenticated.')
        with open('authservers.txt', 'a') as file:
            file.write(f'{ctx.guild.id}\n')
    else:
        await ctx.send('Incorrect password.')

@bot.command(help="List all authenticated servers.")
async def authservers(ctx):
    await ctx.send(f'current channel id: {ctx.guild.id}')
    await ctx.send(open('authservers.txt').read())
    if str(ctx.guild.id) in open('authservers.txt').read():
        await ctx.send('Server is authenticated.')

@bot.command(help="Manually start a stream without using the session system. Useful for testing, or if the session system breaks.")
async def startstream(ctx,episode=None):
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
            return
        except:
            await ctx.send('Some error occured, idk')
            return

    shows = plex.library.section('Video').all()
    showstring = 'Pick a show (type the number):\n```'
    counter = 1
    for show in shows:
        showstring += f'{counter} - {show.title}\n'
        counter += 1
    showstring += '```'
    await ctx.send(showstring)
    await ctx.send('type exit to cancel')

    undecided = True

    while undecided:
        showchoice = await bot.wait_for('message', check=lambda msg: msg.author == ctx.author)
        if showchoice.content.isdigit() and int(showchoice.content) <= len(shows):
            showchoice = shows[int(showchoice.content) - 1] # -1 because the list is 0-indexed
            undecided = False
        elif showchoice.content == 'exit':
            return
        else:
            await ctx.send('Invalid choice.')
    
    episodes = showchoice.episodes()
    episodestring = 'Pick an episode (type the number):\n```'
    for episode in episodes:
        episodestring += f'{episode.index} - {episode.title}\n'
    episodestring += '```'
    await ctx.send(episodestring)
    await ctx.send('type exit to cancel')

    undecided = True

    while undecided:
        episodechoice = await bot.wait_for('message', check=lambda msg: msg.author == ctx.author)
        if episodechoice.content.isdigit() and int(episodechoice.content) <= len(episodes):
            episodechoice = episodes[int(episodechoice.content) - 1]
            print('Selected ' + episodechoice.title)
            undecided = False
        elif episodechoice.content == 'exit':
            return
        else:
            await ctx.send('Invalid choice.')

    
    await ctx.send('Attempting to start stream...')
    url = episodechoice.getStreamURL()
    publicipdashes = publicip.replace('.', '-') 
    url = url.replace('192-168-1-187', publicipdashes)
    await ctx.send(f'Stream started at: ```{url}```')
    await ctx.send('Open this link by starting VLC media player, pressing Ctrl+N and pasting the link in the text box. This will work with other media players too if they have network stream support.')
    #await ctx.send('(Note: for some god forsaken reason, right clicking the link message and then clicking copy text does not work with VLC, the link won`t work. You have to highlight it and then do Ctrl+C. Do not ask. I have no idea.)')


if os.getenv('DISCORD_BOT_TOKEN'):
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
else:
    bot.run(open('token.txt').read())