from fuzzywuzzy import fuzz
import aiohttp
import asyncio
import html
import time

class CentovaCast():
    def __init__(self, client, centovacast_username, centovacast_password, centovacast_url, shoutcast_url):
        self.client = client
        self.username = centovacast_username
        self.password = centovacast_password
        
        self.MUSIC_STREAM_URL = shoutcast_url + "/stream"
        self.METADATA_URL = shoutcast_url + "/stats"
        self.LOGIN_URL = centovacast_url + "/login/index.php"
        self.CLIENT_URL = centovacast_url + "/client/rpc.php"
        self.EXTERNAL_URL = centovacast_url + "/external/rpc.php"
        
        self.PLAYLIST_URL = self.CLIENT_URL + "?m=playlist.list_all"
        self.SONG_TRACKS_URL = self.CLIENT_URL + "?m=playlist.get_tracks&p%5B%5D="
        
        self.cookie_jar = aiohttp.CookieJar()
        
        self.song_cached_data = {"songs": [], "artists": {}}
        self.song_cached_time = 0
        
        self.cached_metadata = {"title": "", "artist": ""}
        self.last_meta_changed = 0
    
    async def connect(self):
        await self.update_centova_cookie()
        self.client.loop.create_task(self.update_current_song_len())
    
    async def update_centova_cookie(self):
        payload = {'username': self.username, 'password': self.password, 'login': 'Login'}
        async with aiohttp.ClientSession(loop=self.client.loop, cookie_jar=self.cookie_jar) as session:
            await session.post(self.LOGIN_URL, data=payload, allow_redirects=False)
    
    async def get_centova(self, url):
        async with aiohttp.ClientSession(loop=self.client.loop, cookie_jar=self.cookie_jar) as session:
            async with session.get(url) as resp:
                r = await resp.json()
                if r["type"] == "error":
                    await self.update_centova_cookie()
                    return await self.get_centova(url)
                return r["data"]
    
    async def get_song_list(self):
        now = time.time()
        if now - self.song_cached_time > 60:
            playlists = (await self.get_centova(self.PLAYLIST_URL))[0]
            songs = []
            artists = {}
            for p in playlists:
                s = await self.get_centova(self.SONG_TRACKS_URL + str(p["id"]))
                if p["status"] == "enabled" and p["type"] == "general":
                    songs = s[1] + songs
                    artists.update(s[2])
            self.song_cached_data["songs"] = songs
            self.song_cached_data["artists"] = artists
            self.song_cached_time = time.time()
        return self.song_cached_data
        
    async def get_song_requests(self):
        playlists = (await self.get_centova(self.PLAYLIST_URL))[0]
        songs = []
        artists = {}
        for p in playlists:
            if p["type"] == "request" and p["status"] == "enabled":
                s = await self.get_centova(self.SONG_TRACKS_URL + str(p["id"]))
                songs += s[1]
                artists.update(s[2])
        return {"songs": songs, "artists": artists}
        
    async def get_current_song(self):
        async with aiohttp.ClientSession(loop=self.client.loop) as session:
            async with session.get(self.METADATA_URL) as resp:
                xsl = await resp.text()
                meta = html.unescape(xsl[xsl.find("<SONGTITLE>")+11:xsl.find("</SONGTITLE>")])
                if " - " in meta and " [" in meta:
                    title = meta[meta.index(" - ") + 3 : meta.index(" [") - 1]
                    artist = meta[ : meta.index(" - ")]
                elif " - " in meta:
                    title = meta[meta.index(" - ") + 3]
                    title = meta[ : len(title) - 1]
                    artist = meta[: meta.index(" - ")]
                else:
                    title = meta
                    artist = ""
                return {"title": title, "artist": artist}
    
    async def update_current_song_len(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            current_song = await self.get_current_song()
            if current_song["title"] != self.cached_metadata["title"] and current_song["artist"] != self.cached_metadata["artist"]:
                self.last_meta_changed = time.time()
                self.cached_metadata = current_song
                self.client.dispatch("song_change", current_song)
            await asyncio.sleep(10)
    
    async def get_current_song_len(self):
        song_list = await self.get_song_list()
        songs = song_list["songs"]
        artists = song_list["artists"]
        current_song = await self.get_current_song()
        for song in songs:
            if current_song["title"] in song["title"] and current_song["artist"] in artists["i" + str(song["artistid"])]:
                return song["length"]
        return 0
    
    async def get_current_song_progress(self):
        return time.time() - self.last_meta_changed
    
    async def search_song(self, query):
        query = query.lower()
        song_list = await self.get_song_list()
        songs = song_list["songs"]
        artists = song_list["artists"]
        resultlist = []
        for element in songs:
            artist = str(artists["i" + str(element["artistid"])]).lower()
            title = element["title"].lower()
            rank = 0
            match_artist, artist_rank = self.match_string(query, artist)
            match_title, title_rank = self.match_string(query, title)
            rank = max(artist_rank, title_rank)
            if match_artist or match_title:
                song_rank = self.SongRank(str(element["id"]), rank, element["title"], artists["i" + str(element["artistid"])])
                resultlist.append(song_rank)
        return sorted(resultlist, key=lambda x: x.rank, reverse=True)

    def match_string(self, s1, s2):
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
            
    class SongRank:
        def __init__(self, songid, rank, title, author):
            self.songid = songid
            self.rank = rank
            self.title = title
            self.author = author
        
        def __repr__(self):
            return "Rank-{} ID-{} Title-{} Author-{}".format(self.rank, self.songid, self.title, self.author)
            
    async def request_song(self, song_id_query):
        song_list = await self.get_song_list()
        songs = song_list["songs"]
        artists = song_list["artists"]
        for element in songs:
            if str(song_id_query) == str(element["id"]):
                async with aiohttp.ClientSession(loop=self.client.loop) as session:
                    query_param = {
                        "m": "request.submit",
                        "username": "harmonyradio",
                        "artist": artists['i' + str(element['artistid'])].replace("&", "%26"),
                        "title": element["title"].replace("&", "%26"),
                        "sender": "HarmonyBot",
                        "dedi": "myself"
                    }
                    url = self.EXTERNAL_URL + "?m=request.submit&username=harmonyradio&artist={0}&title={1}&sender=HarmonyBot&email=EndenDragon@Equestria.net&dedi=myself".format(artists["i" + str(element["artistid"])].replace("&", "%26"),  element["title"].replace("&", "%26"))
                    async with session.get(url) as resp:
                        j = await resp.json()
                        if j["type"] == "result":
                            return {"status": True, "song": {"title": element["title"], "artist": artists['i' + str(element['artistid'])]}}
        return {"status": False, "song": None}