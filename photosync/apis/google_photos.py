import json

import aiohttp
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from urllib.parse import urlencode

from cog_shared.seplib.utils import Result
from photosync.apis.method import Method


class BaseGoogleAPI(object):

    UPLOAD_URL = ""

    def __init__(self, access_token):
        self._access_token = access_token

    def _build_api_url(self, append_path: str = None):
        append_path = "" if append_path is None else append_path
        return f"{self.UPLOAD_URL}{append_path}"

    async def _raw_request(
        self, method: Method, params: Optional[Dict] = None, data: Optional[Dict] = None, append_path: str = None
    ) -> Result[Dict]:
        pass

    async def _request(
        self, method: Method, params: Optional[Dict] = None, data: Optional[Dict] = None, append_path: str = None
    ) -> Result[Dict]:
        params = {} if params is None else params
        params["access_token"] = self._access_token

        data = {} if data is None else data
        data["access_token"] = self._access_token
        return await self._raw_request(method=method, params=params, data=data, append_path=append_path)

    async def _post(self, data: Dict = None, append_path: str = None) -> Result[Dict]:
        return await self._request(method=Method.POST, data=data, append_path=append_path)

    async def _get(self, params: Dict = None, append_path: str = None) -> Result[Dict]:
        return await self._request(method=Method.POST, params=params, append_path=append_path)


class GoogleAuthorizeAPI(BaseGoogleAPI):

    API_URL = "https://accounts.google.com/o/oauth2/v2/auth"

    PHOTOS_SCOPES = (
        "https://www.googleapis.com/auth/photoslibrary "
        "https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata "
        "https://www.googleapis.com/auth/photoslibrary.sharing"
    )

    @staticmethod
    def build_auth_url(client_id: str, redirect_uri: str) -> str:
        """
        Builds the Google Photos app authorization URL that the user will need to go to to authorize the app.
        :param client_id: Client ID of the Google Photos App.
        :param redirect_uri: Redirect URI of the Google Photos App
        :return: Built Google Photos authorization URL that the user will need to go to to authorize the app.
        """
        url = f"{GoogleAuthorizeAPI.API_URL}"
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": GoogleAuthorizeAPI.PHOTOS_SCOPES,
            "response_type": "code",
            "access_type": "offline",
            "include_granted_scopes": "true",
        }
        query_string = urlencode(params)
        return f"{url}?{query_string}"


class GoogleTokenAPI(BaseGoogleAPI):

    API_URL = "https://www.googleapis.com/oauth2/v4/token"

    @staticmethod
    def build_token_url():
        return f"{GoogleTokenAPI.API_URL}"

    @staticmethod
    async def get_access_token(
        client_id: str, client_secret: str, redirect_uri: str, auth_code: str
    ) -> Result[Optional[Dict[str, str]]]:
        auth_data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url=GoogleTokenAPI.build_token_url(), data=auth_data) as resp:
                if resp.status != 200:
                    return Result(success=False, value=None, error=f"Error from Google API: {resp.content}")
                data = await resp.json()
                expires_time = datetime.strptime(resp.headers.get("Date"), "%a, %d %b %Y %H:%M:%S GMT") + timedelta(
                    seconds=data.get("expires_in")
                )
                data["expires"] = expires_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                return Result(success=True, value=data, error=None)

    @staticmethod
    async def get_refresh_token(
        client_id: str, client_secret: str, refresh_token: str
    ) -> Result[Optional[Dict[str, str]]]:
        auth_data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url=GoogleTokenAPI.build_token_url(), data=auth_data) as resp:
                if resp.status != 200:
                    return Result(success=False, value=None, error=f"Error from Google API: {resp.content}")
                return Result(success=True, value=await resp.json(), error=None)


class GooglePhotosAPI(BaseGoogleAPI):

    UPLOAD_URL = "https://photoslibrary.googleapis.com/v1/uploads"
    ALBUMS_URL = "https://photoslibrary.googleapis.com/v1/albums"
    BATCH_CREATE_URL = "https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate"

    DISCORD_IMG_REQ_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0"
    }

    def __init__(self, access_token: str):
        super(GooglePhotosAPI, self).__init__(access_token=access_token)

    async def get_album_list(self) -> Result[Optional[List[Dict]]]:
        params = {"access_token": self._access_token}
        async with aiohttp.ClientSession() as session:
            async with session.get(url=self.ALBUMS_URL, params=params) as resp:
                if resp.status != 200:
                    return Result(success=False, value=None, error=f"Error from Google API: {resp.content}")
                data = await resp.json()
                return Result(success=True, value=data.get("albums"), error=None)

    async def create_album(self, album: Dict):
        payload = {"album": album}
        headers = {"Authorization": f"Bearer {self._access_token}"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url=self.ALBUMS_URL, json=payload, headers=headers) as resp:
                if resp.status not in [200, 201]:
                    return Result(success=False, value=None, error=f"Error from Google API: {resp.content}")
                return Result(success=True, value=await resp.json(), error=None)

    async def share_album(self, album_id: str, share_options: Dict):
        share_url = f"{self.ALBUMS_URL}/{album_id}:share"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url=share_url, json=share_options, headers=headers) as resp:
                if resp.status not in [200, 201]:
                    return Result(success=False, value=None, error=f"Error from Google API: {resp.content}")
                return Result(success=True, value=await resp.json(), error=None)

    async def upload_image(self, image_bytes: bytes) -> Result[Optional[str]]:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/octet-stream",
            "X-Goog-Upload-Protocol": "raw",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url=self.UPLOAD_URL, headers=headers, data=image_bytes) as resp:
                if resp.status not in [200, 201]:
                    return Result(success=False, error=await resp.text(), value=None)
                return Result(success=True, value=await resp.text(), error=None)

    async def batch_create(self, album_id: str, upload_token: str, file_name: str) -> Result[Optional[str]]:
        payload = {
            "albumId": album_id,
            "newMediaItems": [{"description": file_name, "simpleMediaItem": {"uploadToken": upload_token}}],
        }
        headers = {"Authorization": f"Bearer {self._access_token}"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url=self.BATCH_CREATE_URL, headers=headers, json=payload) as resp:
                if resp.status not in [200, 201]:
                    return Result(success=False, error=await resp.text(), value=None)
                return Result(success=True, value=await resp.text())
