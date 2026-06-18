"""SQLite 数据库初始化与 seed 数据。"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "boardgame.db"

# 游戏名称到出版商和购入年份的映射
_GAME_META = {
    "卡坦岛": ("Kosmos", 2023),
    "璀璨宝石": ("Space Cowboys", 2022),
    "狼人杀": ("Asmodee", 2021),
}

# 配件名称到备注说明和购买链接的映射（与种子数据保持一致）
_PART_NOTE_URL_MAP = {
    "红色道路板块": ("原装红色道路板块，注意与现有版本色差", "https://item.taobao.com/item.htm?id=example1"),
    "绿色宝石代币": ("玻璃材质，注意边缘打磨光滑", "https://mobile.yangkeduo.com/goods.html?goods_id=example2"),
    "预言家角色牌": ("扫描分辨率需 300dpi 以上，双面彩印", None),
    "法官锤": (None, "https://item.taobao.com/item.htm?id=example3"),
}


def get_connection() -> sqlite3.Connection:
    """获取 SQLite 连接，行结果以 dict 形式返回。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _fill_game_publisher_and_year(conn: sqlite3.Connection) -> None:
    """若游戏表已有数据但出版商和购入年份均为空，按名称补写。"""
    rows = conn.execute(
        "SELECT id, name FROM games WHERE publisher IS NULL AND purchase_year IS NULL"
    ).fetchall()
    for row in rows:
        meta = _GAME_META.get(row["name"])
        if meta:
            publisher, purchase_year = meta
            conn.execute(
                "UPDATE games SET publisher = ?, purchase_year = ? WHERE id = ?",
                (publisher, purchase_year, row["id"]),
            )
    conn.commit()


def _fill_missing_parts_note_and_url(conn: sqlite3.Connection) -> None:
    """若缺件表已有数据但备注和购买链接均为空，按配件名称补写示例值。"""
    total = conn.execute("SELECT COUNT(*) FROM missing_parts").fetchone()[0]
    if total == 0:
        return

    filled = conn.execute(
        "SELECT COUNT(*) FROM missing_parts WHERE note IS NOT NULL OR purchase_url IS NOT NULL"
    ).fetchone()[0]
    if filled > 0:
        return

    rows = conn.execute("SELECT id, accessory FROM missing_parts").fetchall()
    for row in rows:
        meta = _PART_NOTE_URL_MAP.get(row["accessory"])
        if meta:
            note, purchase_url = meta
            conn.execute(
                "UPDATE missing_parts SET note = ?, purchase_url = ? WHERE id = ?",
                (note, purchase_url, row["id"]),
            )
    conn.commit()


def init_db() -> None:
    """创建表结构并在空库时写入 seed 数据。"""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                publisher TEXT,
                purchase_year INTEGER
            );

            CREATE TABLE IF NOT EXISTS purchase_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                contact TEXT,
                remark TEXT
            );

            CREATE TABLE IF NOT EXISTS missing_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                channel_id INTEGER,
                accessory TEXT NOT NULL,
                replacement_plan TEXT NOT NULL,
                cost REAL NOT NULL DEFAULT 0,
                completion_date TEXT,
                priority TEXT NOT NULL DEFAULT '中'
                    CHECK(priority IN ('高', '中', '低')),
                note TEXT,
                purchase_url TEXT,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
                FOREIGN KEY (channel_id) REFERENCES purchase_channels(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                op_type TEXT NOT NULL,
                target TEXT NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            """
        )

        _migrate_missing_parts(conn)
        _migrate_games(conn)
        _fill_game_publisher_and_year(conn)
        _fill_missing_parts_note_and_url(conn)

        game_count = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        if game_count == 0:
            _seed(conn)
        else:
            channel_count = conn.execute(
                "SELECT COUNT(*) FROM purchase_channels"
            ).fetchone()[0]
            if channel_count == 0:
                _seed_channels_and_link_parts(conn)


def _migrate_missing_parts(conn: sqlite3.Connection) -> None:
    """为已有数据库添加缺失的列。"""
    columns = conn.execute(
        "PRAGMA table_info(missing_parts)"
    ).fetchall()
    col_names = [col["name"] for col in columns]
    if "channel_id" not in col_names:
        conn.execute(
            "ALTER TABLE missing_parts ADD COLUMN channel_id INTEGER REFERENCES purchase_channels(id) ON DELETE SET NULL"
        )
    if "priority" not in col_names:
        conn.execute(
            "ALTER TABLE missing_parts ADD COLUMN priority TEXT NOT NULL DEFAULT '中' CHECK(priority IN ('高', '中', '低'))"
        )
    if "note" not in col_names:
        conn.execute("ALTER TABLE missing_parts ADD COLUMN note TEXT")
    if "purchase_url" not in col_names:
        conn.execute("ALTER TABLE missing_parts ADD COLUMN purchase_url TEXT")


def _migrate_games(conn: sqlite3.Connection) -> None:
    """为已有 games 表添加 publisher 和 purchase_year 列。"""
    columns = conn.execute(
        "PRAGMA table_info(games)"
    ).fetchall()
    col_names = [col["name"] for col in columns]
    if "publisher" not in col_names:
        conn.execute("ALTER TABLE games ADD COLUMN publisher TEXT")
    if "purchase_year" not in col_names:
        conn.execute("ALTER TABLE games ADD COLUMN purchase_year INTEGER")


def _seed(conn: sqlite3.Connection) -> None:
    """写入 3 个游戏，各 2 条缺件记录及示例采购渠道。"""
    channels = [
        ("淘宝桌游配件专营店", "客服旺旺：bg-parts，电话：400-123-4567", "主要购买原装桌游配件"),
        ("3D打印定制工作室", "微信：3dprint_mini，QQ：123456789", "定制特殊形状的塑料零件"),
        ("拼多多通用耗材店", "店铺ID：bg_supplies", "购买卡牌套、骰子等通用配件"),
    ]
    channel_ids = []
    for name, contact, remark in channels:
        cur = conn.execute(
            "INSERT INTO purchase_channels (name, contact, remark) VALUES (?, ?, ?)",
            (name, contact, remark),
        )
        channel_ids.append(cur.lastrowid)

    games = [
        ("卡坦岛", "Kosmos", 2023),
        ("璀璨宝石", "Space Cowboys", 2022),
        ("狼人杀", "Asmodee", 2021),
    ]
    parts = [
        [
            ("红色道路板块", "淘宝补购原装配件", 28.5, "2025-03-12", channel_ids[0], "高", "原装红色道路板块，注意与现有版本色差", "https://item.taobao.com/item.htm?id=example1"),
            ("六面骰", "3D 打印替代件", 5.0, None, channel_ids[1], "低", None, None),
        ],
        [
            ("绿色宝石代币", "通用玻璃筹码替代", 15.0, "2025-01-20", channel_ids[2], "中", "玻璃材质，注意边缘打磨光滑", "https://mobile.yangkeduo.com/goods.html?goods_id=example2"),
            ("卡牌套", "标准 57×89mm 牌套", 32.0, "2025-02-08", channel_ids[2], "高", None, None),
        ],
        [
            ("预言家角色牌", "高清扫描重印", 2.0, "2024-11-05", None, "高", "扫描分辨率需 300dpi 以上，双面彩印", None),
            ("法官锤", "木质迷你锤替代", 18.0, None, channel_ids[1], "中", None, "https://item.taobao.com/item.htm?id=example3"),
        ],
    ]

    for (name, publisher, purchase_year), game_parts in zip(games, parts):
        cur = conn.execute(
            "INSERT INTO games (name, publisher, purchase_year) VALUES (?, ?, ?)",
            (name, publisher, purchase_year),
        )
        game_id = cur.lastrowid
        conn.executemany(
            """
            INSERT INTO missing_parts
                (game_id, accessory, replacement_plan, cost, completion_date, channel_id, priority, note, purchase_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(game_id, *p) for p in game_parts],
        )

    conn.commit()


def _seed_channels_and_link_parts(conn: sqlite3.Connection) -> None:
    """当游戏表有数据但渠道表为空时，补充示例渠道并为缺件记录关联合适渠道。"""
    channels = [
        ("淘宝桌游配件专营店", "客服旺旺：bg-parts，电话：400-123-4567", "主要购买原装桌游配件"),
        ("3D打印定制工作室", "微信：3dprint_mini，QQ：123456789", "定制特殊形状的塑料零件"),
        ("拼多多通用耗材店", "店铺ID：bg_supplies", "购买卡牌套、骰子等通用配件"),
    ]
    channel_ids = []
    for name, contact, remark in channels:
        cur = conn.execute(
            "INSERT INTO purchase_channels (name, contact, remark) VALUES (?, ?, ?)",
            (name, contact, remark),
        )
        channel_ids.append(cur.lastrowid)

    taobao_id, print3d_id, pdd_id = channel_ids

    parts = conn.execute(
        "SELECT id, accessory, replacement_plan FROM missing_parts WHERE channel_id IS NULL ORDER BY id"
    ).fetchall()

    for part in parts:
        accessory = part["accessory"].lower()
        plan = part["replacement_plan"].lower()

        channel_id = None
        if "3d" in plan or "打印" in plan or "定制" in plan:
            channel_id = print3d_id
        elif "牌套" in accessory or "卡牌套" in accessory or "筹码" in accessory or "代币" in accessory:
            channel_id = pdd_id
        elif "淘宝" in plan or "原装" in plan or "配件" in plan:
            channel_id = taobao_id
        elif "骰" in accessory or "骰子" in accessory:
            channel_id = pdd_id

        if channel_id is not None:
            conn.execute(
                "UPDATE missing_parts SET channel_id = ? WHERE id = ?",
                (channel_id, part["id"]),
            )

    conn.commit()
