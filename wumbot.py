import random
import string
import discord
from discord.ext import commands
import os
from plexapi.myplex import MyPlexAccount
import requests
import json

httpd = None
plexpass = 'Wumboners!999'
plexserver = 'movserver'
plexuser = 'page710'
publicip = requests.get('https://api.ipify.org').text

account = MyPlexAccount(plexuser, plexpass)
plex = account.resource(plexserver).connect()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
sessions = []


async def session_factory(owner, sessionname, showkey, episode):
    class Session:
        def __init__(self, owner, sessionname, showkey, episode):
            self.owner = owner
            self.sessionname = sessionname
            self.showkey = showkey
            self.episode = episode

        async def resume(self, ctx, episode):
            await ctx.send(f'Resuming {episode.title}')
            startstream(ctx, episode)
        
        async def next(self, ctx):
            self.episode += 1
            episodes = plex.library.section('Video').get(self.showkey).episodes()
            if self.episode >= len(episodes):
                await ctx.send('No more episodes.')
                return
            episode = episodes[self.episode]
            await ctx.send(f'Starting next episode {episode.title}')
            startstream(ctx, episode)

        async def previous(self, ctx):
            self.episode -= 1
            episodes = plex.library.section('Video').get(self.showkey).episodes()
            if self.episode < 0:
                await ctx.send('No previous episodes.')
                return
            episode = episodes[self.episode]
            await ctx.send(f'Starting previous episode {episode.title}')
            startstream(ctx, episode)
        
        async def end(self, ctx):
            await ctx.send('Session ended.')
            next = self.episode + 1
            if next >= len(plex.library.section('Video').get(self.showkey).episodes()):
                # Delete session file
                os.remove(f'sessions/{self.sessionname}.txt')
                await ctx.send('No more episodes left, session deleted.')
                return
            with open(f'sessions/{self.sessionname}.txt', 'w') as file:
                json.dump({'sessionname': self.sessionname, 'showkey': self.showkey, 'episode': next}, file)
                await ctx.send("Session data saved.")
            sessions.remove(self)
    return Session(sessionname, showkey, episode)

        
    

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.event
async def on_guild_join(guild):
    print(f'Joined {guild.name}')


@bot.command(help="Start a new session. Provide a session name under 20 characters. Sessions are deleted when all episodes have been watched. Sessions start at episode 1, but you can override this by typing a number after the session name.")
async def createnewsession(ctx,sessionname=None,episodeoverride=None):
    if not sessionname:
        await ctx.send('Please enter a session name.')
    if len(sessionname) > 20:
        await ctx.send('Session name too long.')
        return
    if not os.path.exists('sessions'):
        os.makedirs('sessions')
    if os.path.exists(f'sessions/{sessionname}.txt'):
        await ctx.send('Session name already exists.')
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
    newsession = await session_factory(ctx.author,sessionname, showchoice.key, 0) if not episodeoverride else await session_factory(sessionname, showchoice.key, int(episodeoverride))
    sessions.append(newsession)
    await ctx.send(f'Starting new session {sessionname} at episode {newsession.episode + 1}')
    newsession.resume(ctx, showchoice.episodes()[newsession.episode])
    newsession = None

@bot.command(help="Resume a session. You will be prompted to pick a session from the list of existing sessions.")
async def resumesession(ctx):
    if ctx.guild.id not in open('authservers.txt').read():
        await ctx.send('Server not authenticated.')
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
        session = await session_factory(sessiondata['sessionname'], sessiondata['showkey'], sessiondata['episode'])
        await session.resume(ctx, sessiondata['episode'])
    
    
    
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
        url = episodechoice.getStreamURL()
        # url = f'{url}&?audioStreamID={audiochoice}&subtitleStreamID={subtitlechoice}'
        publicipdashes = publicip.replace('.', '-') 
        url = url.replace('192-168-1-187', publicipdashes)
        await ctx.send(f'Stream started at:')
        await ctx.send(url)
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

    # Parse the XML data
    # xml_data = episodechoice._server.query(episodechoice.key)
    # xml_data = ET.tostring(xml_data,encoding='utf8')
    # xml_data = xml_data.decode('utf-8')
    # root = ET.fromstring(xml_data)

    # audiostreams = [stream.attrib for stream in root.findall('.//Stream[@streamType="2"]')]
    # streamstring = 'Pick an audio stream (type the number):\n```'
    # counter = 1
    # for stream in audiostreams:
    #     streamstring += f'{counter} - {stream.get("language")}\n'
    #     counter += 1
    # streamstring += '```'
    # await ctx.send(streamstring)
    # await ctx.send('type exit to cancel')

    # undecided = True
    
    # while undecided:
    #     audiochoice = await bot.wait_for('message', check=lambda msg: msg.author == ctx.author)
    #     if audiochoice.content.isdigit():
    #         audiochoice = audiostreams[int(audiochoice.content) - 1]['id']
    #         undecided = False
    #     elif audiochoice.content == 'exit':
    #         return
    #     else:
    #         await ctx.send('Invalid choice.')
    
    # subtitlestreams = [stream.attrib for stream in root.findall('.//Stream[@streamType="3"]')]
    # subtitlechoice = None
    # for stream in subtitlestreams:
    #     if 'forced' in stream and stream['forced'] == '1':
    #         subtitlechoice = stream['id']
    #         await ctx.send(f'Forced subtitle stream found: {stream.get("language")}')
    #         break
    
    # if not subtitlechoice:
    #     streamstring = 'Pick a subtitle stream (type the number):\n```'
    #     counter = 1
    #     for stream in subtitlestreams:
    #         streamstring += f'{counter} - {stream.get("language")}\n'
    #         counter += 1
    #     streamstring += '```'
    #     await ctx.send(streamstring)
    #     await ctx.send('type exit to cancel')

    #     undecided = True

    #     while undecided:
    #         subtitlechoice = await bot.wait_for('message', check=lambda msg: msg.author == ctx.author)
    #         if subtitlechoice.content.isdigit():
    #             subtitlechoice = subtitlestreams[int(subtitlechoice.content) - 1]['id']
    #             undecided = False
    #         elif subtitlechoice.content == 'exit':
    #             return
    #         else:
    #             await ctx.send('Invalid choice.')

    
    await ctx.send('Attempting to start stream...')
    url = episodechoice.getStreamURL()
    # url = f'{url}&?audioStreamID={audiochoice}&subtitleStreamID={subtitlechoice}'
    publicipdashes = publicip.replace('.', '-') 
    url = url.replace('192-168-1-187', publicipdashes)
    # await ctx.send(url)
    # with open('video_player.html', 'w') as f:
    #     f.write(f'''
    #     <html>
    # <head>
    #     <title>Video Player</title>
    #     <link href="https://vjs.zencdn.net/7.8.4/video-js.css" rel="stylesheet" />
    # </head>
    # <body>
    #     <video id='my-video' class='video-js' controls preload='auto' width='640' height='264'>
    #         <source src="{url}" type='video/mkv'>
    #     </video>
    #     <script src="https://vjs.zencdn.net/7.8.4/video.js"></script>
    # </body>
    # </html>
    # ''')

    # urlcode = plex._token
    # PORT = 32400
    # if not httpd:
    #     httpd = HTTPServer(('0.0.0.0', PORT), handler_factory(urlcode))
    #     httpd_thread = threading.Thread(target=start_httpd, args=(httpd,))
    #     httpd_thread.start()
    # url = f'http://localhost:{PORT}/video_player.html?X-Plex-Token={urlcode}'
    
    await ctx.send(f'Stream started at:')
    await ctx.send(url)


if os.getenv('DISCORD_BOT_TOKEN'):
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
else:
    bot.run(open('token.txt').read())