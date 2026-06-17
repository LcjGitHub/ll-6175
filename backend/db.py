"""SQLite 数据库初始化与 seed 数据。"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "boardgame.db"


def get_connection() -> sqlite3.Connection:
    """获取 SQLite 连接，行结果以 dict 形式返回。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """创建表结构并在空库时写入 seed 数据。"""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS missing_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                accessory TEXT NOT NULL,
                replacement_plan TEXT NOT NULL,
                cost REAL NOT NULL DEFAULT 0,
                completion_date TEXT,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
            );
            """
        )

        count = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        if count == 0:
            _seed(conn)


def _seed(conn: sqlite3.Connection) -> None:
    """写入 3 个游戏，各 2 条缺件记录。"""
    games = [
        "卡坦岛",
        "璀璨宝石",
        "狼人杀",
    ]
    parts = [
        [
            ("红色道路板块", "淘宝补购原装配件", 28.5, "2025-03-12"),
            ("六面骰", "3D 打印替代件", 5.0, None),
        ],
        [
            ("绿色宝石代币", "通用玻璃筹码替代", 15.0, "2025-01-20"),
            ("卡牌套", "标准 57×89mm 牌套", 32.0, "2025-02-08"),
        ],
        [
            ("预言家角色牌", "高清扫描重印", 2.0, "2024-11-05"),
            ("法官锤", "木质迷你锤替代", 18.0, None),
        ],
    ]

    for name, game_parts in zip(games, parts):
        cur = conn.execute("INSERT INTO games (name) VALUES (?)", (name,))
        game_id = cur.lastrowid
        conn.executemany(
            """
            INSERT INTO missing_parts
                (game_id, accessory, replacement_plan, cost, completion_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            [(game_id, *p) for p in game_parts],
        )

    conn.commit()
