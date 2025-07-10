moduleInfo = {
    "meta": {
        "name": "YunhuAdapter",
        "version": "2.8.2",
        "description": "云湖协议适配器，整合所有云湖功能模块",
        "author": "wsu2059q",
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

# build_hash="ea2009bceef0a20c83aa3512aafb83d6f18619c8bdd8864c0887f19600d71c67"

# build_hash="ac6fe045e8c5aff621af7534e5d31edbe26a3d511022372a0b19f698fa3ac2b0"
