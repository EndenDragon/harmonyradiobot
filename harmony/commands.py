import datetime
import discord
import subprocess

class Commands():
    def __init__(self, client, config):
        self.client = client
        self.config = config
        
    async def handle_help(self, message):
        commands = """**Lista De Comandos:**
`!ayuda` - Muestra el menu de ayuda.
`!informacion` - Informacion general del HarmonyBot.
`!nowplaying` - Muestra que esta sonando en este momento.
`!buscar <query>` - Busca el titulo de una cancion o autor con la palabra dada.
`!pedir <id>` - Pedir una cancion con la id dada.
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
        await message.channel.send(commands)
        
    async def on_ayuda(self, message): # help
        await self.handle_help(message)
    
    async def on_comandos(self, message): # commands
        await self.handle_help(message)
        
    async def on_informacion(self, message):
        out = subprocess.getoutput("git rev-parse --short master")
        about = """**Harmony Radio Bot 🤖** por EndenDragon
Git revision: `{0}` | URL: https://github.com/EndenDragon/harmonyradiobot/commit/{0}
Hecho con :heart: para Harmony Radio.
http://www.ponyradio.com/
        """.format(out)

        # """**Harmony Radio Bot 🤖** by EndenDragon
        # Git revision: `{0}` | URL: https://github.com/EndenDragon/harmonyradiobot/commit/{0}
        # Made with :heart: for Harmony Radio.
        # http://www.ponyradio.com/
        # """
        await message.channel.send(about)
    
    async def handle_nowplaying(self, message):
        current_song = await self.client.centovacast.get_current_song()
        current_song_len = await self.client.centovacast.get_current_song_len()
        progress = await self.client.centovacast.get_current_song_progress()
        progress_formatted = str(datetime.timedelta(seconds=int(progress))) + " / " + str(datetime.timedelta(seconds=int(current_song_len)))
        embed = discord.Embed(color=0x9BDBF5)
        embed.set_author(name='Estas escuchando', url="http://www.ponyradio.com/", icon_url="https://cdn.discordapp.com/attachments/224735647485788160/258390514867503104/350x3502.png")
        embed.add_field(name=str("{} - {}".format(current_song["artist"], current_song["title"])), value=":speaker:"+ progress_formatted)
        await message.channel.send(embed=embed)
        
    async def on_np(self, message):
        await self.handle_nowplaying(message)
        
    async def on_nowplaying(self, message):
        await self.handle_nowplaying(message)
        
    async def on_buscar(self, message): # search
        if len(str(message.content)) == 7:
            await message.channel.send("**Perdon...que? No entendi eso.** \n Porfavor ingresa tu busqueda despues del comando. \n ej. `!buscar Rainbow Dash`") # **I'm sorry, what was that? Didn't quite catch that.** \n Please enter your search query after the command. \n eg. `!search Rainbow Dash`
            return
        query = message.content.split(" ", 1)[1]
        results = await self.client.centovacast.search_song(query)
        em = discord.Embed(color=0x9BDBF5)
        em.set_author(name="Buscar canciones: " + query, url="http://www.ponyradio.com/", icon_url="https://cdn.discordapp.com/attachments/224735647485788160/258390514867503104/350x3502.png") #"**__Search Songs: " + query
        count = 0
        overcount = 0
        if len(results) > 0:
            for x in results:
                if count < 24:
                    em.add_field(name=str(x.songid), value="**" + x.title + "**\n*" + x.author + "*")
                    count = count + 1
                else:
                    overcount = overcount + 1
        if len(results) == 0:
            em.add_field(name="No hay resultados que coincidan.", value="\u200b", inline=False) # No matching results found
        elif overcount > 0:
            em.add_field(name="*...y " + str(overcount) + " aun mas no mostrado*", value="\u200b", inline=False) #"*...and " + str(overcount) + " more results not shown*"
        await message.channel.send(message.author.mention, embed=em)
        
    async def handle_request(self, message):
        id_query = message.content.split()[1]
        request = await self.client.centovacast.request_song(id_query)
        if request["status"]:
            song = request["song"]
            em = discord.Embed(colour=0x9BDBF5)
            em.set_author(name="📬", url="http://www.ponyradio.com/", icon_url="https://cdn.discordapp.com/attachments/224735647485788160/258390514867503104/350x3502.png")
            em.add_field(name="**#" + id_query + "** " + str(song['title']), value=song["artist"])
            await message.channel.send(message.author.mention + ", Su solicitud de canción ha sido enviada. Muchas gracias.", embed=em)
        else:
            await message.channel.send("ID de cancion no encontrada!") #"Song ID not found!"
    
    async def on_pedir(self, message): # !request
        await self.handle_request(message)
    
    async def on_p(self, message): # !p
        await self.handle_request(message)