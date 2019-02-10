from datetime import datetime, timedelta
from typing import Optional, Dict

from .google_photos import BaseGoogleAPI, GoogleTokenAPI

from .google_photos import GooglePhotosAPI


class GooglePhotos(object):

    def __init__(self, access_token: str, refresh_token: str, expires: datetime):
        self.__access_token = access_token
        self.__refresh_token = refresh_token
        self.__expires = expires

    @property
    def api(self) -> GooglePhotosAPI:
        try:
            return self.__api
        except AttributeError:
            self.__api = GooglePhotosAPI(access_token=self.__access_token)
        return self.__api

    async def refresh_access_token(self, client_id: str, client_secret: str) -> Optional[Dict]:
        if datetime.utcnow()+timedelta(seconds=60) >= self.__expires:
            result = await GoogleTokenAPI.get_refresh_token(client_id=client_id, client_secret=client_secret,
                                                            refresh_token=self.__refresh_token)
            if result.success:
                data = result.value
                self.__access_token = data.get("access_token")
                self.__expires = (datetime.utcnow() + timedelta(seconds=data.get("expires_in")))
                self.clear_cache()
                return data
        return

    def clear_cache(self):
        try:
            del self.__api
        except AttributeError:
            pass
