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
        
        await self.update_voice()
        
    async def update_voice(self, channel_id=None):
        if channel_id:
            channels = [channel_id]
        else:
            channels = config["music-channels"]
        for channelid in channels:
            channel = self.get_channel(channelid)
            if channel and isinstance(channel, discord.VoiceChannel):
                members = channel.members
                count = 0
                for member in members:
                    if member != member.guild.me and not member.voice.deaf and not member.voice.self_deaf and not member.voice.afk:
                        count = count + 1
                await asyncio.sleep(1)
                if count > 0:
                    await self.connect_voice(channel)
                else:
                    await self.disconnect_voice(channel)
                    
    async def connect_voice(self, channel):
        for voice in self.voice_clients:
            if voice.channel == channel and voice.is_connected():
                return
        voice_client = await channel.connect()
        self.loop.run_in_executor(None, self.play_voice, voice_client)

    def play_voice(self, voice_client):
        while not self.is_closed() and voice_client.is_connected():
            if not voice_client.is_playing():
                audio_source = discord.FFmpegPCMAudio(shlex.quote(config["shoutcast-url"] + "/stream"))
                voice_client.play(audio_source, after=self.on_voice_error)
                time.sleep(10)
                
    async def disconnect_voice(self, channel):
        for voice in self.voice_clients:
            if voice.channel == channel and voice.is_connected():
                voice.stop()
                await voice.disconnect()
    
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
        
    async def on_voice_state_update(self, member, before, after):
        if before and before.channel:
            await self.update_voice(before.channel.id)
        if after and after.channel:
            await self.update_voice(after.channel.id)