moduleInfo = {
    "meta": {
        "name": "YunhuAdapter",
        "version": "2.8.0",
        "description": "云湖协议适配器，整合所有云湖功能模块",
        "author": "r1a, WSu2059",
        "license": "MIT",
        "homepage": "https://github.com/ErisPulse/ErisPulse-YunhuAdapter"
    },
    "dependencies": {
        "requires": [],
        "optional": [],
        "pip": [
            "aiohttp",
            "filetype"
        ]
    }
}

from .Core import Main

from .Core import YunhuAdapter

adapterInfo = {
    "yunhu": YunhuAdapter,
    "yh": YunhuAdapter,
}

# build_hash="d324b58a7844f9b44d8757d182fe68825a649678192aa37f60664350c6670809"
