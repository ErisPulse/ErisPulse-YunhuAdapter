moduleInfo = {
    "meta": {
        "name": "YunhuAdapter",
        "version": "2.2.5",
        "description": "云湖协议适配器，整合所有云湖功能模块",
        "author": "r1a, WSu2059",
        "license": "MIT",
        "homepage": "https://github.com/ErisPulse/ErisPulse-YunhuAdapter"
    },
    "dependencies": {
        "requires": [],
        "optional": [],
        "pip": ["aiohttp"]
    }
}

from .Core import Main

from .Core import YunhuAdapter

adapterInfo = {
    "yunhu": YunhuAdapter,
    "Yunhu": YunhuAdapter,
}
