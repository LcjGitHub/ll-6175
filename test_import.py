"""测试导入接口"""
import requests

BASE = "http://127.0.0.1:5000"

# 测试1: 合并模式导入（重复数据应被跳过）
print("=== 测试1: 合并模式导入 ===")
with open("test_backup.json", "rb") as f:
    resp = requests.post(
        f"{BASE}/api/backup/import?mode=merge",
        files={"file": ("test_backup.json", f, "application/json")},
    )
print(f"HTTP {resp.status_code}")
data = resp.json()
print(data)
print()

# 测试2: 创建一个稍微修改的备份 - 加个新游戏
print("=== 测试2: 含新游戏的合并导入 ===")
import json

with open("test_backup.json", "r", encoding="utf-8") as f:
    bak = json.load(f)

bak["games"].append({"id": 999, "name": "导入测试新游戏"})
bak["missing_parts"].append({
    "id": 999,
    "game_id": 999,
    "channel_id": 1,
    "accessory": "新游戏配件1",
    "replacement_plan": "测试导入方案",
    "cost": 9.9,
    "completion_date": None,
})
with open("test_modified.json", "w", encoding="utf-8") as f:
    json.dump(bak, f, ensure_ascii=False, indent=2)

with open("test_modified.json", "rb") as f:
    resp = requests.post(
        f"{BASE}/api/backup/import?mode=merge",
        files={"file": ("test_modified.json", f, "application/json")},
    )
print(f"HTTP {resp.status_code}")
data = resp.json()
print(data)
print()

# 测试3: 格式校验 - 缺少必填字段
print("=== 测试3: 格式校验（缺少字段） ===")
bad_data = {"version": "1.0", "games": []}  # 缺少 purchase_channels, missing_parts
with open("test_bad.json", "w", encoding="utf-8") as f:
    json.dump(bad_data, f)

with open("test_bad.json", "rb") as f:
    resp = requests.post(
        f"{BASE}/api/backup/import?mode=merge",
        files={"file": ("test_bad.json", f, "application/json")},
    )
print(f"HTTP {resp.status_code}")
print(resp.json())
print()

# 测试4: 版本不兼容
print("=== 测试4: 版本不兼容 ===")
bad_ver = {"version": "2.0", "games": [], "purchase_channels": [], "missing_parts": []}
with open("test_bad_ver.json", "w", encoding="utf-8") as f:
    json.dump(bad_ver, f)

with open("test_bad_ver.json", "rb") as f:
    resp = requests.post(
        f"{BASE}/api/backup/import?mode=merge",
        files={"file": ("test_bad_ver.json", f, "application/json")},
    )
print(f"HTTP {resp.status_code}")
print(resp.json())
print()

# 测试5: 检查游戏列表是否包含新游戏
print("=== 测试5: 验证游戏列表（应包含导入测试新游戏） ===")
resp = requests.get(f"{BASE}/api/games")
print(f"HTTP {resp.status_code}")
games = resp.json()
for g in games:
    print(f"  {g['id']}: {g['name']} ({g['part_count']} 条缺件)")

# 清理临时文件
import os
for fn in ["test_backup.json", "test_modified.json", "test_bad.json", "test_bad_ver.json"]:
    try:
        os.remove(fn)
    except OSError:
        pass
