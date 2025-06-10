moduleInfo = {
    "meta": {
        "name": "YunhuAdapter",
        "version": "2.1.1",
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

# build_hash="730c49551cc6c86952d603aab3eb170c1243bebbdd5174c6ce3f6da940e9d46c"

# build_hash="991c55051ab5e443fe8e7d368cf0dcfba76bdaf4a3b7f89cd1b2e148af44e452"

# build_hash="84270387643fdea6db697b0269ca5bfc07251535b8f234dee312cac562bd1f9c"
