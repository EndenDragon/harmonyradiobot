from config import *
import discord
from discord import Game, Channel, Server, Embed
import asyncio
import logging
from html import unescape
import subprocess
import time
import datetime
import sys
import requests
import json
from random import randint
from fuzzywuzzy import fuzz

client = discord.Client()
logging.basicConfig(filename='harmonybot.log',level=logging.INFO,format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
logger = logging.getLogger('HarmonyBot')

exitCode = 0
currentDate = datetime.datetime.now().date()
centovaCookie = ""
backupMetadata = False
lastMetaUpdate = datetime.datetime.now()
currentMetadata = ""
curSongLength = 0
songCachedData = ''
songCachedTime = 0

class SongRank:
    def __init__(self, songid, rank, title, author):
        self.songid = songid
        self.rank = rank
        self.title = title
        self.author = author

def getRadioSong():
    global backupMetadata
    try:
        response = requests.get(METADATA_URL)
        backupMetadata = False
    except:
        try:
            response = requests.get(METADATA_BACKUP_URL)
            backupMetadata = True
        except:
            return "Nada en concreto :V" # Nothing in peculiar
    xsl = response.text
    return unescape(xsl[xsl.find("<SONGTITLE>")+11:xsl.find("</SONGTITLE>")])

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
    global songCachedData, songCachedTime
    now = time.time()
    if not songCachedData or now - songCachedTime > 60 * 1:
        logging.debug('Refreshing song cache')
        playlists = getCentova(PLAYLIST_URL)[0]
        songs = []
        artists = {}
        for p in playlists:
            s = getCentova(SONG_TRACKS_URL + str(p['id']))
            if p["status"] == "enabled" and p["type"] == "general":
                songs = s[1] + songs
                artists.update(s[2])
        songCachedData = {'songs': songs, 'artists': artists}
        songCachedTime = time.time()
    return songCachedData

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
        payload = {'count': count, 'key': METADATA_PRIMARY_API_KEY}
        requests.post(METADATA_URL, data=payload)
        lastListenersCount = count

def updateCurrentSongLength(currentsong):
    global curSongLength
    try:
        gitSong = getSongList()
    except:
        curSongLength = 0
        return
    songs = gitSong["songs"]
    artists = gitSong["artists"]
    if " - " in currentsong and " [" in currentsong:
        cursong = currentsong[currentsong.index(" - ")+3:currentsong.index(" [")-1]
        curartist = currentsong[:currentsong.index(" - ")]
    elif " - " in currentsong:
        cursong = currentsong[currentsong.index(" - ")+3:]
        cursong = cursong[:len(cursong) -1]
        curartist = currentsong[:currentsong.index(" - ")]
    else:
        cursong = currentsong
        curartist = ""
    for s in songs:
        if cursong in s["title"] and curartist in artists['i' + str(s['artistid'])]:
            curSongLength = s["length"]
            return
    curSongLength = 0

def matchingString(s1, s2):
    if s1 == s2:
        return True, 100
    if s1 in s2 or s2 in s1:
        return True, 95
    partialRatio = fuzz.partial_ratio(s1,s2)
    if partialRatio > 90:
        return True, partialRatio
    tokenRatio = fuzz.token_sort_ratio(s1, s2)
    if tokenRatio > 85:
        return True, tokenRatio
    genRatio = fuzz.ratio(s1,s2)
    if genRatio > 85:
        return True, genRatio
    return False, 0

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

async def background_loop():
    await client.wait_until_ready()
    global lastMetaUpdate, currentMetadata
    centovaLogin()
    c = discord.utils.get(client.get_server(str(MAIN_SERVER)).channels, id=str(MUSIC_CHANNEL), type=discord.ChannelType.voice)
    global v, exitCode, backupMetadata
    v = await client.join_voice_channel(c)
    player = v.create_ffmpeg_player(MUSIC_STREAM_URL)
    player.start()
    lastPlayerPlaying = True
    initialStart = True
    initialHasSong = False
    last_usingBackupMetadata = backupMetadata
    while not client.is_closed:
        if currentDate != datetime.datetime.now().date():
            await client.logout()
            logging.info("Bot Shutting Down... (Daily Restart)")
            exitCode = 1
        if not player.is_playing():
            player.stop()
        await asyncio.sleep(2)
        try:
            if last_usingBackupMetadata != backupMetadata:
                last_usingBackupMetadata = backupMetadata
                initialStart = True
                initialHasSong = False
            spotCheck = randint(0,9) < randint(2,4)
            pastCurrentSong = int(curSongLength) - int((datetime.datetime.now() - lastMetaUpdate).total_seconds()) < 30
            if pastCurrentSong or initialStart or spotCheck:
                text = getRadioSong()
        except:
            pass
        if text != currentMetadata or lastPlayerPlaying != player.is_playing():
            if initialStart and not initialHasSong:
                initialHasSong = True
            elif initialHasSong and initialStart:
                initialStart = False
            currentMetadata = text
            status = Game(name=text, type=0)
            updateCurrentSongLength(currentMetadata)
            if player.is_playing():
                lastPlayerPlaying = True
                lastMetaUpdate = datetime.datetime.now()
                await client.change_presence(game=status)
            else:
                lastPlayerPlaying = False
                await client.change_presence(game=status, status=discord.Status.dnd)
        postListenersCount()
        if not player.is_playing():
            player = v.create_ffmpeg_player(MUSIC_STREAM_URL)
            player.start()
        await asyncio.sleep(3)
    sys.exit(exitCode)


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
        http://ponyharmony.com/
        """.format(out)

        # """**Harmony Radio Bot 🤖** by EndenDragon
        # Git revision: `{0}` | URL: https://github.com/EndenDragon/harmonyradiobot/commit/{0}
        # Made with :heart: for Harmony Radio.
        # http://ponyharmony.com/
        # """
        await client.send_message(message.channel, about)
    elif message.content.lower().startswith('!nowplaying') or message.content.lower().startswith('!np'):
        await client.send_typing(message.channel)
        global currentMetadata
        hr_txt = currentMetadata
        global curSongLength
        global lastMetaUpdate
        timing = str(datetime.timedelta(seconds=int((datetime.datetime.now() - lastMetaUpdate).total_seconds()))) + " / " + str(datetime.timedelta(seconds=int(curSongLength)))
        em = Embed(colour=0x9BDBF5)
        em.set_author(name='Estas escuchando', url="http://ponyharmony.com/", icon_url="https://cdn.discordapp.com/attachments/224735647485788160/258390514867503104/350x3502.png") # **Now Playing:**
        em.add_field(name=str(hr_txt), value=timing)
        await client.send_message(message.channel, message.author.mention, embed=em)
    elif message.content.lower().startswith('!buscar'): # !search
        await client.send_typing(message.channel)
        if len(str(message.content)) == 7:
            await client.send_message(message.channel, "**Perdon...que? No entendi eso.** \n Porfavor ingresa tu busqueda despues del comando. \n ej. `!buscar Rainbow Dash`") # **I'm sorry, what was that? Didn't quite catch that.** \n Please enter your search query after the command. \n eg. `!search Rainbow Dash`
        else:
            em = Embed(colour=0x9BDBF5)
            getSongs = getSongList()
            songs = getSongs['songs']
            artists = getSongs['artists']
            query = str(message.content).split(' ', 1)[1]
            resultlist = []
            em.set_author(name="Buscar canciones: " + query, url="http://ponyharmony.com/", icon_url="https://cdn.discordapp.com/attachments/224735647485788160/258390514867503104/350x3502.png") #"**__Search Songs: " + query
            for element in songs:
                que = query.lower()
                art = str(artists['i' + str(element['artistid'])]).lower()
                tit = element['title'].lower()
                rank = 0
                matchArtist, arank = matchingString(que, art)
                matchTitle, trank = matchingString(que, tit)
                rank = max(arank, trank)
                if matchArtist or matchTitle:
                    sr = SongRank(str(element['id']), rank, element['title'], artists['i' + str(element['artistid'])])
                    resultlist.append(sr)
            count = 0
            overcount = 0
            if len(resultlist) != 0:
                resultlist = sorted(resultlist, key=lambda x: x.rank, reverse=True)
                for x in resultlist:
                    if count < 24:
                        em.add_field(name=str(x.songid), value="**" + x.title + "**\n*" + x.author + "*")
                        count = count + 1
                    else:
                        overcount = overcount + 1
            if len(resultlist) == 0:
                em.add_field(name="No hay resultados que coincidan.", value="\u200b", inline=False) # No matching results found
            elif overcount != 0:
                em.add_field(name="*...y " + str(overcount) + " aun mas no mostrado*", value="\u200b", inline=False) #"*...and " + str(overcount) + " more results not shown*"
            await client.send_message(message.channel, message.author.mention, embed=em)
    elif message.content.lower().startswith('!pedir') or message.content.lower().startswith('!p'): # !request !req
        await client.send_typing(message.channel)
        msg = message.content.split(None, 1)
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
                        em = Embed(colour=0x9BDBF5)
                        em.set_author(name="📬", url="http://ponyharmony.com/", icon_url="https://cdn.discordapp.com/attachments/224735647485788160/258390514867503104/350x3502.png")
                        em.add_field(name="**#" + str(element['id']) + "** " + str(element['title']), value=artists['i' + str(element['artistid'])])
                        await client.send_message(message.channel, message.author.mention + ", "+ j['data'][0], embed=em)
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
            msg = str(message.content).split()[1]
            if msg.lower() != "none":
                f = requests.get(msg)
                await client.edit_profile(avatar=f.content)
                await client.send_message(message.channel, "Avatar cambiado a " + str(message.content)[13:] + "con exito!") #"Successfully changed the avatar to " + str(message.content)[13:] + "!"
            else:
                await client.edit_profile(avatar=None)
                await client.send_message(message.channel, "Avatar cambiado a 'none' con exito!")
        else:
            await client.send_message(message.channel, "I'm sorry, this is an **admin only** command!")
    elif message.content.lower().startswith('!reiniciar'): # !restart
        await client.send_typing(message.channel)
        if isBotAdmin(message):
            await client.send_message(message.channel, "Reiniciando HarmonyBot...") #"HarmonyBot is restarting... 
            global exitCode
            if len(message.content.split()) != 1 and message.content.split()[1].lower() == 'update':
                logging.info("Bot Shutting Down... (User Invoked w/update)")
                exitCode = 2
            else:
                logging.info("Bot Shutting Down... (User Invoked)")
                exitCode = 1
            await client.logout()
        else:
            await client.send_message(message.channel, "Lo siento este es un comando **solo para el admin**!") #"I'm sorry, this is an **admin only** command!"
    elif message.content.lower().startswith('!abrasar'): # !hug
        mentions = message.mentions
        members = ""
        for x in mentions:
            members = members + " " + x.mention
        await client.send_message(message.channel, ":heartbeat: *Abrasa " + members + "!* :heartbeat:") #":heartbeat: *Hugs " + members + "!* :heartbeat:"

client.loop.create_task(background_loop())
client.run(DISCORD_BOT_TOKEN)
