from config import *
import discord
from discord import Game, Channel, Server
import asyncio
import logging
from urllib.request import urlopen
import urllib.parse
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

def getRadioSong():
    response = urlopen(METADATA_URL)
    xsl = response.read()
    hr_json = str(xsl.decode("utf-8"))
    return hr_json[hr_json.find("<SONGTITLE>")+11:hr_json.find("</SONGTITLE>")]

def centovaGetLoginCookie(url, username, password):
    payload = {'username': username, 'password': password, 'login': 'Login'}
    r = requests.head(url, data=payload, allow_redirects=False)
    return r.cookies['centovacast']

def getSongList():
    cookies = {'centovacast': centovaCookie}
    songfile = json.loads(requests.get(SONG_TRACKS_URL, cookies=cookies).text)
    songs = songfile['data'][1]
    artists = songfile['data'][2]
    return {'songs': songs, 'artists': artists}

def isBotAdmin(message):
    author = client.get_server(str(MAIN_SERVER)).get_member(message.author.id)
    for a in author.roles:
        if a.name.lower() == ADMIN_ROLE_NAME.lower():
            return True
    return False

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
    global centovaCookie
    centovaCookie = centovaGetLoginCookie(CENTOVACAST_LOGIN_URL, CENTOVACAST_USERNAME, CENTOVACAST_PASSWORD)
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
            await client.change_status(game=status, idle=False)
        await asyncio.sleep(10)

@client.event
async def on_message(message):
    if message.content.startswith('!help') or message.content.startswith('!commands'):
        await client.send_typing(message.channel)
        commands = """**List of commands:**
        `!help` - displays this help menu
        `!about` - general information about HarmonyRadioBot
        `!nowplaying` - shows what is currently playing in the station
        `!search <query>` - search for a song's title or author with the given string
        `!request <id>` - make a song request to the station
        `!list (index)` - list of the songs that the radio offers
        ----------------------
        `!joinvoice` - joins the voice channel with the person who sent the command
        `!disconnectvoice` - disconnect from the voice channel
        `!changeavatar <URL>` - change the bot's avatar to the url
        `!restart` - restarts the bot

        Command parameters: `<required>` `(optional)`
        """
        await client.send_message(message.channel, commands)
    elif message.content.lower().startswith('!about'):
        await client.send_typing(message.channel)
        out = subprocess.getoutput("git rev-parse --short master")
        about = """**Harmony Radio Bot 🤖** by EndenDragon
        Git revision: `{0}` | URL: https://github.com/EndenDragon/harmonyradiobot/commit/{0}
        Made with :heart: for Harmony Radio.
        http://ponyharmonylive.com/
        """.format(out)
        await client.send_message(message.channel, about)
    elif message.content.lower().startswith('!nowplaying') or message.content.lower().startswith('!np'):
        await client.send_typing(message.channel)
        hr_txt = getRadioSong()
        text = "**Now Playing:** " + str(hr_txt)
        await client.send_message(message.channel, text)
    elif message.content.lower().startswith('!search'):
        await client.send_typing(message.channel)
        if len(str(message.content)) == 7:
            await client.send_message(message.channel, "**I'm sorry, what was that? Didn't quite catch that.** \n Please enter your search query after the command. \n eg. `!search Rainbow Dash`")
        else:
            getSongs = getSongList()
            songs = getSongs['songs']
            artists = getSongs['artists']
            query = str(message.content).split(' ', 1)[1]
            count = 0
            botmessage = "**__Search Songs: " + query + "__**\n[ID | Artist | Title]\n"
            for element in songs:
                if count < 10:
                    if query.lower() in str(artists['i' + str(element['artistid'])]).lower() or query.lower() in element['title'].lower():
                        botmessage = botmessage + "**" + str(element['id']) + "** | " + artists['i' + str(element['artistid'])] + " | " + element['title'] + "\n"
                        count = count + 1
                else:
                    break
            await client.send_message(message.channel, botmessage)
    elif message.content.lower().startswith('!request') or message.content.lower().startswith('!req'):
        await client.send_typing(message.channel)
        msg = message.content.split(" ", 1)
        if len(msg) == 1:
            await client.send_message(message.channel, "**I just don't know what went wrong!** \n Please enter your requested song id after the command. \n eg. `!request 14982` \n _Remember: you can search for the song with the `!search` command!_")
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
                        await client.send_message(message.channel, j['data'][0])
                        break
            if status == False:
                await client.send_message(message.channel, "Song ID not found!")
    elif message.content.lower().startswith('!list'):
        await client.send_typing(message.channel)
        if len(str(message.content)) >= 7:
            index = str(message.content)[str(message.content).find("!list") + 6:]
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
        text = "**__Song List: Page " + str(index) + " of " + str(round(int(count)/10)) + "__**\n"
        text = text + "[ID | Artist | Title]\n"
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
            await client.send_message(message.channel, "Successfully joined the voice channel!")
            player = v.create_ffmpeg_player(MUSIC_STREAM_URL)
            player.start()
        else:
            await client.send_message(message.channel, "I'm sorry, this is an **admin only** command!")
    elif message.content.lower().startswith('!disconnectvoice') or message.content.lower().startswith('!dv'):
        await client.send_typing(message.channel)
        if isBotAdmin(message):
            await v.disconnect()
            await client.send_message(message.channel, "Successfully disconnected from the voice channel!")
        else:
            await client.send_message(message.channel, "I'm sorry, this is an **admin only** command!")
    elif message.content.lower().startswith('!changeavatar'):
        await client.send_typing(message.channel)
        if isBotAdmin(message):
            f = urlopen(str(message.content)[13:])
            await client.edit_profile(avatar=f.read())
            await client.send_message(message.channel, "Successfully changed the avatar to " + str(message.content)[13:] + "!")
        else:
            await client.send_message(message.channel, "I'm sorry, this is an **admin only** command!")
    elif message.content.lower().startswith('!restart'):
        await client.send_typing(message.channel)
        if isBotAdmin(message):
            await client.send_message(message.channel, "HarmonyBot is restarting...")
            await client.logout()
            if len(message.content.split()) != 1 and message.content.split()[1].lower() == 'update':
                logging.info("Bot Shutting Down... (User Invoked w/update)")
                sys.exit(2)
            else:
                logging.info("Bot Shutting Down... (User Invoked)")
                sys.exit(1)
        else:
            await client.send_message(message.channel, "I'm sorry, this is an **admin only** command!")
    elif message.content.lower().startswith('!hug'):
        mentions = message.mentions
        members = ""
        for x in mentions:
            members = members + " " + x.mention
        await client.send_message(message.channel, ":heartbeat: *Hugs " + members + "!* :heartbeat:")

client.run(DISCORD_BOT_TOKEN)
