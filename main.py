from config import *
import discord
from discord import Game, Channel, Server
import asyncio
import logging
from urllib.request import urlopen
import urllib.parse
from html import unescape
import subprocess
import time
import datetime
import sys
import requests
import json

client = discord.Client()
logging.basicConfig(filename='harmonybot.log',level=logging.INFO,format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
logger = logging.getLogger('HarmonyBot')

currentDate = datetime.datetime.now().date()
centovaCookie = ""
backupMetadata = False
lastMetaUpdate = datetime.datetime.now()
curSongLength = 0

def getRadioSong():
    try:
        response = urlopen(METADATA_URL)
        backupMetadata = False
    except:
        response = urlopen(METADATA_BACKUP_URL)
        backupMetadata = True
    xsl = response.read()
    hr_json = str(xsl.decode("utf-8"))
    return unescape(hr_json[hr_json.find("<SONGTITLE>")+11:hr_json.find("</SONGTITLE>")])

def centovaGetLoginCookie(url, username, password):
    payload = {'username': username, 'password': password, 'login': 'Login'}
    r = requests.head(url, data=payload, allow_redirects=False)
    return r.cookies['centovacast']

def centovaLogin():
    global centovaCookie
    centovaCookie = centovaGetLoginCookie(CENTOVACAST_LOGIN_URL, CENTOVACAST_USERNAME, CENTOVACAST_PASSWORD)

def getCentova(url):
    cookies = {'centovacast': centovaCookie}
    f = requests.get(url, cookies=cookies).text
    f = json.loads(f)
    if f['type'] == "error":
        centovaLogin()
        f = json.loads(requests.get(url, cookies=cookies).text)
    return f["data"]

def getSongList():
    playlists = getCentova(PLAYLIST_URL)[0]
    songs = []
    artists = {}
    for p in playlists:
        s = getCentova(SONG_TRACKS_URL + str(p['id']))
        if p["status"] == "enabled" and p["type"] == "general":
            songs = s[1] + songs
            artists.update(s[2])
    return {'songs': songs, 'artists': artists}

def isBotAdmin(message):
    author = client.get_server(str(MAIN_SERVER)).get_member(message.author.id)
    for a in author.roles:
        if a.name.lower() == ADMIN_ROLE_NAME.lower():
            return True
    return False

def postListenersCount():
    if ENABLE_POSTING_LISTENERS and not backupMetadata:
        voicechannelmembers = discord.utils.get(client.get_server(str(MAIN_SERVER)).channels, id=str(MUSIC_CHANNEL), type=discord.ChannelType.voice).voice_members
        count = 0
        for m in voicechannelmembers:
            if not m.voice.deaf and not m.voice.self_deaf and not m.bot:
                count = count + 1
        payload = {'listeners': count}
        requests.post(METADATA_URL, data=payload)

def updateCurrentSongLength(currentsong):
    gitSong = getSongList()
    songs = gitSong["songs"]
    artists = gitSong["artists"]
    if " - " in currentsong and " [" in currentsong:
        cursong = currentsong[currentsong.index(" - ")+3:currentsong.index(" [")-1]
        curartist = currentsong[:currentsong.index(" - ")]
    elif " - " in currentsong:
        cursong = currentsong[currentsong.index(" - ")+3:]
        curartist = currentsong[:currentsong.index(" - ")]
    else:
        cursong = currentsong
        curartist = ""
    global curSongLength
    for s in songs:
        if cursong in s["title"] and curartist in artists['i' + str(s['artistid'])]:
            curSongLength = s["length"]
            return
    curSongLength = 0

@client.event
async def on_ready():
    print('------')
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('')
    print('It is currently ' + str(currentDate))
    print('')
    print('Connected servers')
    for x in client.servers:
        print(x.name)
    print('------')
    radioMeta = ""
    centovaLogin()
    c = discord.utils.get(client.get_server(str(MAIN_SERVER)).channels, id=str(MUSIC_CHANNEL), type=discord.ChannelType.voice)
    global v
    v = await client.join_voice_channel(c)
    player = v.create_ffmpeg_player(MUSIC_STREAM_URL)
    player.start()
    while True:
        if currentDate != datetime.datetime.now().date():
            await client.logout()
            logging.info("Bot Shutting Down... (Daily Restart)")
            sys.exit(1)
        text = getRadioSong()
        if text != radioMeta:
            radioMeta = text
            status = Game(name=text, type=0)
            global lastMetaUpdate
            lastMetaUpdate = datetime.datetime.now()
            updateCurrentSongLength(radioMeta)
            await client.change_status(game=status, idle=False)
        postListenersCount()
        await asyncio.sleep(5)

@client.event
async def on_message(message):
    if message.content.startswith('!ayuda') or message.content.startswith('!comandos'): # !help !commands
        await client.send_typing(message.channel)
        commands = """**Lista De Comandos:**
        `!ayuda` - Muestra el menu de ayuda.
        `!informacion` - Informacion general del HarmonyBot.
        `!nowplaying` - Muestra que esta sonando en este momento.
        `!buscar <query>` - Busca el titulo de una cancion o autor con la palabra dada.
        `!pedir <id>` - Pedir una cancion con la id dada.
        `!lista (index)` - Listas de canciones que la radio ofrece.
        ----------------------
        `!joinvoice` - Une el bot al canal de voz con la persona que escribio el comando.
        `!disconnectvoice` - Desconecta el bot del canal de voz.
        `!cambiaravatar <URL>` - Cambia la imagen del bot mediante URL.
        `!reiniciar` - Reinicia el bot.

        Parametros de comandos: `<requerido>` `(opcional)`
        """

        #         """**List of commands:**
        # `!help` - displays this help menu
        # `!about` - general information about HarmonyRadioBot
        # `!nowplaying` - shows what is currently playing in the station
        # `!search <query>` - search for a song's title or author with the given string
        # `!request <id>` - make a song request to the station
        # `!list (index)` - list of the songs that the radio offers
        # ----------------------
        # `!joinvoice` - joins the voice channel with the person who sent the command
        # `!disconnectvoice` - disconnect from the voice channel
        # `!changeavatar <URL>` - change the bot's avatar to the url
        # `!restart` - restarts the bot
        #
        # Command parameters: `<required>` `(optional)`
        # """
        await client.send_message(message.channel, commands)
    elif message.content.lower().startswith('!informacion'): # !about
        await client.send_typing(message.channel)
        out = subprocess.getoutput("git rev-parse --short master")
        about = """**Harmony Radio Bot 🤖** por EndenDragon
        Git revision: `{0}` | URL: https://github.com/EndenDragon/harmonyradiobot/commit/{0}
        Hecho con :heart: para Harmony Radio.
        http://ponyharmonylive.com/
        """.format(out)

        # """**Harmony Radio Bot 🤖** by EndenDragon
        # Git revision: `{0}` | URL: https://github.com/EndenDragon/harmonyradiobot/commit/{0}
        # Made with :heart: for Harmony Radio.
        # http://ponyharmonylive.com/
        # """
        await client.send_message(message.channel, about)
    elif message.content.lower().startswith('!nowplaying') or message.content.lower().startswith('!np'):
        await client.send_typing(message.channel)
        hr_txt = getRadioSong()
        text = "**Estas escuchando:** " + str(hr_txt) # **Now Playing:**
        global curSongLength
        global lastMetaUpdate
        text = text + " `[" + str(datetime.timedelta(seconds=int((datetime.datetime.now() - lastMetaUpdate).total_seconds()))) + " / " + str(datetime.timedelta(seconds=int(curSongLength))) + "]`"
        await client.send_message(message.channel, text)
    elif message.content.lower().startswith('!buscar'): # !search
        await client.send_typing(message.channel)
        if len(str(message.content)) == 7:
            await client.send_message(message.channel, "**Perdon...que? No entendi eso.** \n Porfavor ingresa tu busqueda despues del comando. \n ej. `!buscar Rainbow Dash`") # **I'm sorry, what was that? Didn't quite catch that.** \n Please enter your search query after the command. \n eg. `!search Rainbow Dash`
        else:
            getSongs = getSongList()
            songs = getSongs['songs']
            artists = getSongs['artists']
            query = str(message.content).split(' ', 1)[1]
            count = 0
            overcount = 0
            botmessage = "**__Buscar canciones: " + query + "__**\n[ID | Artista | Titulo]\n" #"**__Search Songs: " + query + "__**\n[ID | Artist | Title]\n"
            for element in songs:
                if query.lower() in str(artists['i' + str(element['artistid'])]).lower() or query.lower() in element['title'].lower():
                    if count < 10:
                        botmessage = botmessage + "**" + str(element['id']) + "** | " + artists['i' + str(element['artistid'])] + " | " + element['title'] + "\n"
                        count = count + 1
                    else:
                        overcount = overcount + 1
            if overcount != 0:
                botmessage = botmessage + "*...y " + str(overcount) + " aun mas no mostrado*" #"*...and " + str(overcount) + " more results not shown*"
            await client.send_message(message.channel, botmessage)
    elif message.content.lower().startswith('!pedir') or message.content.lower().startswith('!p'): # !request !req
        await client.send_typing(message.channel)
        msg = message.content.split(" ", 1)
        if len(msg) == 1:
            await client.send_message(message.channel, "**I just don't know what went wrong!** \n Porfavor ingresa la ID de tu peticion despues del comando. \n ej. `!pedir 14982` \n _Recuerda: Puedes buscar canciones con el comando `!buscar`_") #"**I just don't know what went wrong!** \n Please enter your requested song id after the command. \n eg. `!request 14982` \n _Remember: you can search for the song with the `!search` command!_"
        else:
            getSongs = getSongList()
            songs = getSongs['songs']
            artists = getSongs['artists']
            idquery = msg[1]
            status = False
            for element in songs:
                if str(idquery) == str(element['id']):
                    req = requests.get(CENTOVACAST_REQUEST_URL+ "?m=request.submit&username=ponyharmony&artist={0}&title={1}&sender={2}&email=sssss@ss.com&dedi=myself".format(artists['i' + str(element['artistid'])].replace("&", "%26"),  element['title'].replace("&", "%26"), message.author.name))
                    logging.info(req.url)
                    j = json.loads(req.text)
                    if j['type'] == "result":
                        status = True
                        retmsg =  message.author.mention + ", "+ j['data'][0] + "\n*(#" + str(element['id']) + ") " + str(element['title']) + ", por " + artists['i' + str(element['artistid'])] + "*" #", by "
                        await client.send_message(message.channel, retmsg)
                        break
            if status == False:
                await client.send_message(message.channel, "ID de cancion no encontrada!") #"Song ID not found!"
    elif message.content.lower().startswith('!lista'): # !list
        await client.send_typing(message.channel)
        if len(str(message.content)) >= 7:
            index = str(message.content)[str(message.content).find("!lista") + 6:]
            try:
                index = abs(int(index))
            except:
                index = 1
        else:
            index = 1
        getSongs = getSongList()
        songs = getSongs['songs']
        artists = getSongs['artists']
        count = len(songs)
        text = "**__Lista de canciones: Pagina " + str(index) + " de " + str(round(int(count)/10)) + "__**\n" #"**__Song List: Page " + str(index) + " of " + str(round(int(count)/10)) + "__**\n"
        text = text + "[ID | Artista | Titulo]\n" #"[ID | Artist | Title]\n"
        t = songs
        t = t[(int(float(index)) - 1) * 10:(int(float(index)) - 1)*10+10]
        for x in t:
            text = text + "**" + str(x["id"]) + "** | " + artists['i' + str(x['artistid'])] + " | " + x["title"] + "\n"
        await client.send_message(message.channel, text)
    elif message.content.lower().startswith('!joinvoice') or message.content.lower().startswith('!jv'):
        await client.send_typing(message.channel)
        if isBotAdmin(message) or int(str(message.author.voice_channel.id)) in TRUSTED_VOICE_CHANNELS:
            c = discord.utils.get(message.server.channels, id=message.author.voice_channel.id)
            global v
            v = await client.join_voice_channel(c)
            await client.send_message(message.channel, "Unido al canal de voz con exito!") #"Successfully joined the voice channel!"
            player = v.create_ffmpeg_player(MUSIC_STREAM_URL)
            player.start()
        else:
            await client.send_message(message.channel, "Lo siento este es un comando **solo para el admin**!") #"I'm sorry, this is an **admin only** command!"
    elif message.content.lower().startswith('!disconnectvoice') or message.content.lower().startswith('!dv'):
        await client.send_typing(message.channel)
        if isBotAdmin(message):
            await v.disconnect()
            await client.send_message(message.channel, "Desconectado del canal de voz con exito!") #"Successfully disconnected from the voice channel!"
        else:
            await client.send_message(message.channel, "Lo siento este es un comando **solo para el admin**!") #"I'm sorry, this is an **admin only** command!"
    elif message.content.lower().startswith('!cambiaravatar'): # !changeavatar
        await client.send_typing(message.channel)
        if isBotAdmin(message):
            f = urlopen(str(message.content)[14:])
            await client.edit_profile(avatar=f.read())
            await client.send_message(message.channel, "Avatar cambiado a " + str(message.content)[13:] + "con exito!") #"Successfully changed the avatar to " + str(message.content)[13:] + "!"
        else:
            await client.send_message(message.channel, "I'm sorry, this is an **admin only** command!")
    elif message.content.lower().startswith('!reiniciar'): # !restart
        await client.send_typing(message.channel)
        if isBotAdmin(message):
            await client.send_message(message.channel, "Reiniciando HarmonyBot...") #"HarmonyBot is restarting..."
            await client.logout()
            if len(message.content.split()) != 1 and message.content.split()[1].lower() == 'update':
                logging.info("Bot Shutting Down... (User Invoked w/update)")
                sys.exit(2)
            else:
                logging.info("Bot Shutting Down... (User Invoked)")
                sys.exit(1)
        else:
            await client.send_message(message.channel, "Lo siento este es un comando **solo para el admin**!") #"I'm sorry, this is an **admin only** command!"
    elif message.content.lower().startswith('!abrasar'): # !hug
        mentions = message.mentions
        members = ""
        for x in mentions:
            members = members + " " + x.mention
        await client.send_message(message.channel, ":heartbeat: *Abrasa " + members + "!* :heartbeat:") #":heartbeat: *Hugs " + members + "!* :heartbeat:"

client.run(DISCORD_BOT_TOKEN)
