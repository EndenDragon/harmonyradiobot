from config import config
from harmony.commands import Commands
from harmony.centovacast import CentovaCast
from harmony.opus_loader import load_opus_lib
import discord
import asyncio
import time
import shlex

load_opus_lib()

class HarmonyBot(discord.Client):
    def __init__(self):
        super().__init__()
        self.command = Commands(self, config)
        self.centovacast = CentovaCast(self, config["centovacast-username"], config["centovacast-password"], config["centovacast-url"], config["shoutcast-url"])
    
    def _cleanup(self):
        try:
            self.loop.run_until_complete(self.logout())
        except: # Can be ignored
            pass
        pending = asyncio.Task.all_tasks()
        gathered = asyncio.gather(*pending)
        try:
            gathered.cancel()
            self.loop.run_until_complete(gathered)
            gathered.exception()
        except: # Can be ignored
            pass
    
    def run(self):
        try:
            self.loop.run_until_complete(self.start())
        except discord.errors.LoginFailure:
            print("Invalid bot token in config!")
        finally:
            try:
                self._cleanup()
            except Exception as e:
                print("Error in cleanup:", e)
            self.loop.close()

    async def start(self):
        await self.centovacast.connect()
        await super().start(config["bot-token"])
    
    async def on_ready(self):
        print('HarmonyBot [DiscordBot]')
        print('Logged in as the following user:')
        print(self.user.name)
        print(self.user.id)
        print('------')
        
        await self.connect_voice()
        
    async def connect_voice(self):
        for channelid in config["music-channels"]:
            channel = self.get_channel(channelid)
            if channel and isinstance(channel, discord.VoiceChannel):
                voice_client = await channel.connect()
                audio_source = discord.FFmpegPCMAudio(shlex.quote(config["shoutcast-url"] + "/stream"))
                voice_client.play(audio_source, after=self.on_voice_error)
    
    def on_voice_error(self, error):
        print("Voice Error!!!", error)
        
    async def on_message(self, message):
        content = message.content
        if message.guild and len(content) > 1 and content.startswith("!"):
            msg_cmd = "on_" + content.split(" ")[0][1:].lower()
            cmd = getattr(self.command, msg_cmd, None)
            if cmd:
                async with message.channel.typing():
                    await cmd(message)
    
    async def on_song_change(self, song):
        activity = discord.Activity(
            name = song["title"],
            timestamps = {
                "start": int(time.time() * 1000),
                "end": int((time.time() + (await self.centovacast.get_current_song_len())) * 1000)
            },
            type = discord.ActivityType.listening
        )
        await self.change_presence(activity=activity)