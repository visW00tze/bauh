import time
import traceback

from colorama import Fore

from fpakman.core.controller import ApplicationManager
from fpakman.core.flatpak.constants import FLATHUB_API_URL, FLATHUB_URL
from fpakman.core.flatpak.model import FlatpakApplication
from fpakman.core.model import ApplicationStatus
from fpakman.core.worker import AsyncDataLoader
from fpakman.util.cache import Cache


class FlatpakAsyncDataLoader(AsyncDataLoader):

    def __init__(self, app: FlatpakApplication, manager: ApplicationManager, http_session, api_cache: Cache, attempts: int = 2, timeout: int = 30):
        super(FlatpakAsyncDataLoader, self).__init__(app=app)
        self.manager = manager
        self.http_session = http_session
        self.attempts = attempts
        self.api_cache = api_cache
        self.to_persist = {}  # stores all data loaded by the instance
        self.timeout = timeout

    def run(self):
        if self.app:
            self.app.status = ApplicationStatus.LOADING_DATA

            for _ in range(0, self.attempts):
                try:
                    res = self.http_session.get('{}/apps/{}'.format(FLATHUB_API_URL, self.app.base_data.id), timeout=self.timeout)

                    if res.status_code == 200 and res.text:
                        data = res.json()

                        if not self.app.base_data.version:
                            self.app.base_data.version = data.get('version')

                        if not self.app.base_data.name:
                            self.app.base_data.name = data.get('name')

                        self.app.base_data.description = data.get('description', data.get('summary', None))
                        self.app.base_data.icon_url = data.get('iconMobileUrl', None)
                        self.app.base_data.latest_version = data.get('currentReleaseVersion', self.app.base_data.version)

                        if not self.app.base_data.version and self.app.base_data.latest_version:
                            self.app.base_data.version = self.app.base_data.latest_version

                        if self.app.base_data.icon_url and self.app.base_data.icon_url.startswith('/'):
                            self.app.base_data.icon_url = FLATHUB_URL + self.app.base_data.icon_url

                        loaded_data = self.app.get_data_to_cache()

                        self.api_cache.add(self.app.base_data.id, loaded_data)
                        self.app.status = ApplicationStatus.READY

                        if self.app.supports_disk_cache():
                            self.to_persist[self.app.base_data.id] = self.app

                        break
                    else:
                        self.log_msg("Could not retrieve app data for id '{}'. Server response: {}. Body: {}".format(
                            self.app.base_data.id, res.status_code, res.content.decode()), Fore.RED)
                except:
                    self.log_msg("Could not retrieve app data for id '{}'".format(self.app.base_data.id), Fore.YELLOW)
                    traceback.print_exc()
                    time.sleep(0.5)

            self.app.status = ApplicationStatus.READY

    def cache_to_disk(self):
        if self.to_persist:
            for app in self.to_persist.values():
                self.manager.cache_to_disk(app=app, icon_bytes=None, only_icon=False)

            self.to_persist = {}

    def clone(self) -> "FlatpakAsyncDataLoader":
        return FlatpakAsyncDataLoader(manager=self.manager,
                                      api_cache=self.api_cache,
                                      attempts=self.attempts,
                                      http_session=self.http_session,
                                      timeout=self.timeout,
                                      app=self.app)
