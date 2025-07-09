moduleInfo = {
    "meta": {
        "name": "YunhuAdapter",
        "version": "2.6.1",
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

# build_hash="d0cc154d4e8266fd5cc0a01be2cf39b88c6e153433ed1796b7f3512d6e34868f"

# build_hash="20057514d557b4bd4528e35d56125fc2803eebf25df18d9ef63c6ba29445b6a0"

# build_hash="edcf249e8530d016b573df6e985c41b8ef24458563b4723b1bacc646c27719de"

# build_hash="8d005728c11ce5e01a5df77ff02a8b2a878c1dd4211e7b81366156a926d77de7"
