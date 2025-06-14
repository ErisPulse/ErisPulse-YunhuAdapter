moduleInfo = {
    "meta": {
        "name": "YunhuAdapter",
        "version": "2.2.6",
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
    "yh": YunhuAdapter,
}

# build_hash="d0cc154d4e8266fd5cc0a01be2cf39b88c6e153433ed1796b7f3512d6e34868f"
