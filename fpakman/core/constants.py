from pathlib import Path

from fpakman import __app_name__

HOME_PATH = Path.home()
CACHE_PATH = '{}/.cache/{}'.format(HOME_PATH, __app_name__)
