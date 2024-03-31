import random
import string
import discord
from discord.ext import commands
import os
from plexapi.myplex import MyPlexAccount
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

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

def handler_factory(expectedcode):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = urlparse(self.path).query
            params = parse_qs(query)
            if 'code' in params and params['code'][0] == expectedcode:
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                with open('video_player.html', 'r') as f:
                    self.wfile.write(f.read().encode())
            else:
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                with open('video_player.html', 'r') as f:
                    self.wfile.write(f.read().encode())
    return Handler

def start_httpd(httpd):
    httpd.serve_forever()

def generateurlcode():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.event
async def on_guild_join(guild):
    print(f'Joined {guild.name}')

@bot.command()
async def help(ctx):
    await ctx.send('Commands:\n!ping - pong\n!password <password> - authenticate server\n!authservers - list authenticated servers\n!startstream - start a stream')

@bot.command()
async def createsession(ctx,session=None):
    if not session:
        await ctx.send('Please enter a session name.')
        return
    if len(session > 20):
        await ctx.send('Session name too long.')
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
    
    


@bot.command()
async def ping(ctx):
    await ctx.send('pong')

@bot.command()
async def password(ctx, userpass):
    password = 'wumboner'

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

@bot.command()
async def authservers(ctx):
    await ctx.send(f'current channel id: {ctx.guild.id}')
    await ctx.send(open('authservers.txt').read())
    if str(ctx.guild.id) in open('authservers.txt').read():
        await ctx.send('Server is authenticated.')

@bot.command()
async def startstream(ctx):
    global httpd
    if str(ctx.guild.id) not in open('authservers.txt').read():
        await ctx.send('Server not authenticated.')
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


bot.run(os.getenv('DISCORD_BOT_TOKEN'))