from plexapi.myplex import MyPlexAccount
import sys
import http.server
import socketserver
import threading
import requests

publicip = requests.get('https://api.ipify.org').text
publicip = publicip.replace('.', '-')
arg = sys.argv[1]

library = plex.library.sections()
lib = sys.argv

media = None
if arg == 'shows':
    counter = 0
    for show in lib.all():
        print(show.title)
        counter += 1

elif arg in lib.all():
    counter = 0
    for episode in media.episodes():
        print(episode.title)
        counter += 1

else:
    media = arg
    url = media.getStreamURL().replace('192-168-1-187', publicip)
    with open('video_player.html', 'w') as f:
        f.write(f'''
        <html>
        <head>
            <title>Video Player</title>
        </head>
        <body>
            <video controls autoplay>
                <source src="{url}" type="video/mp4">
            </video>
        </body>
        </html>
        ''')

PORT = 25565
Handler = http.server.SimpleHTTPRequestHandler
httpd = socketserver.TCPServer(("", PORT), Handler)
thread = threading.Thread(target=httpd.serve_forever)
thread.start()
print(f'http://{publicip}:{PORT}/video_player.html')