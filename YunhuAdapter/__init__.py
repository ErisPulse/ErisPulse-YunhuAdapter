moduleInfo = {
    "meta": {
        "name": "YunhuAdapter",
        "version": "2.3.1",
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

# build_hash="20057514d557b4bd4528e35d56125fc2803eebf25df18d9ef63c6ba29445b6a0"

# build_hash="7ef73245618e840abbbfa89ac3aef7e46c02ecb67fe7d1ea0e1bb5c6e6ed5ada"
