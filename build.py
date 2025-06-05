import os
import json
from datetime import datetime
from pathlib import Path
import zipfile

def update_version_and_build_info():
    init_file = Path("YunhuAdapter/__init__.py")
    content = init_file.read_text(encoding="utf-8")

    version_line = next(line for line in content.splitlines() if '"version"' in line)
    current_version = version_line.split('"')[3]
    major, minor, patch = map(int, current_version.split('.'))

    # 版本号递增 (这里递增 patch)
    new_version = f"{major}.{minor}.{patch + 1}"

    build_time = datetime.now().isoformat()

    new_content = content.replace(
        f'"version": "{current_version}"',
        f'"version": "{new_version}"'
    ).replace(
        '"build_time": "2023-01-01T00:00:00Z"',
        f'"build_time": "{build_time}"'
    )

    init_file.write_text(new_content, encoding="utf-8")
    return new_version, build_time

# 打包模块为 ZIP
def create_zip(version: str):
    zip_name = f"YunhuAdapter-{version}.zip"
    files_to_include = [
        "YunhuAdapter/__init__.py",
        "YunhuAdapter/Core.py",
        "README.md"
    ]

    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in files_to_include:
            zipf.write(file, arcname=os.path.basename(file))
    return zip_name

# 更新 map.json
def update_module_map(version: str, zip_name: str, build_time: str):
    map_file = Path("map.json")
    data = json.loads(map_file.read_text(encoding="utf-8"))

    data["modules"]["YunhuAdapter"]["path"] = f"/{zip_name}"
    data["modules"]["YunhuAdapter"]["meta"]["version"] = version
    data["modules"]["YunhuAdapter"]["meta"]["build_time"] = build_time

    map_file.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__":
    new_version, build_time = update_version_and_build_info()
    zip_name = create_zip(new_version)
    update_module_map(new_version, zip_name, build_time)
    print(f"打包完成: {zip_name} (版本 {new_version})")