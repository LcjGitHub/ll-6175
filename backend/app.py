"""桌游缺件替换记录 API。"""

import json
from datetime import datetime
from io import BytesIO

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from db import get_connection, init_db

app = Flask(__name__)
CORS(app)

init_db()


def row_to_dict(row):
    """将 sqlite3.Row 转为 dict。"""
    return dict(row) if row else None


def write_log(conn, op_type, target, detail=None):
    """写入一条操作日志。"""
    conn.execute(
        "INSERT INTO operation_logs (op_type, target, detail) VALUES (?, ?, ?)",
        (op_type, target, detail),
    )


# ── 游戏 ──────────────────────────────────────────────


@app.get("/api/games")
def list_games():
    """获取全部桌游列表。"""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT g.*,
                   COUNT(mp.id) AS part_count
            FROM games g
            LEFT JOIN missing_parts mp ON mp.game_id = g.id
            GROUP BY g.id
            ORDER BY g.name
            """
        ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.post("/api/games")
def create_game():
    """新建桌游。"""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "游戏名称不能为空"}), 400

    try:
        with get_connection() as conn:
            cur = conn.execute("INSERT INTO games (name) VALUES (?)", (name,))
            write_log(conn, "新增游戏", name, f"游戏：{name}")
            conn.commit()
            row = conn.execute(
                "SELECT * FROM games WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
    except Exception:
        return jsonify({"error": "游戏名称已存在"}), 409

    return jsonify(row_to_dict(row)), 201


@app.put("/api/games/<int:game_id>")
def update_game(game_id: int):
    """更新桌游名称。"""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "游戏名称不能为空"}), 400

    try:
        with get_connection() as conn:
            old = conn.execute(
                "SELECT name FROM games WHERE id = ?", (game_id,)
            ).fetchone()
            if not old:
                return jsonify({"error": "游戏不存在"}), 404
            old_name = old["name"]
            result = conn.execute(
                "UPDATE games SET name = ? WHERE id = ?", (name, game_id)
            )
            if result.rowcount == 0:
                return jsonify({"error": "游戏不存在"}), 404
            write_log(conn, "修改游戏", name, f"{old_name} → {name}")
            conn.commit()
            row = conn.execute(
                "SELECT * FROM games WHERE id = ?", (game_id,)
            ).fetchone()
    except Exception:
        return jsonify({"error": "游戏名称已存在"}), 409

    return jsonify(row_to_dict(row))


@app.delete("/api/games/<int:game_id>")
def delete_game(game_id: int):
    """删除桌游及其全部缺件记录。"""
    with get_connection() as conn:
        game = conn.execute(
            "SELECT name FROM games WHERE id = ?", (game_id,)
        ).fetchone()
        if not game:
            return jsonify({"error": "游戏不存在"}), 404
        write_log(conn, "删除游戏", game["name"])
        conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
        conn.commit()
    return "", 204


# ── 采购渠道 ──────────────────────────────────────────


@app.get("/api/channels")
def list_channels():
    """获取全部采购渠道列表。"""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.*,
                   COUNT(mp.id) AS part_count
            FROM purchase_channels c
            LEFT JOIN missing_parts mp ON mp.channel_id = c.id
            GROUP BY c.id
            ORDER BY c.name
            """
        ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.post("/api/channels")
def create_channel():
    """新建采购渠道。"""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    contact = (data.get("contact") or "").strip() or None
    remark = (data.get("remark") or "").strip() or None

    if not name:
        return jsonify({"error": "渠道名称不能为空"}), 400

    try:
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO purchase_channels (name, contact, remark) VALUES (?, ?, ?)",
                (name, contact, remark),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM purchase_channels WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
    except Exception:
        return jsonify({"error": "渠道名称已存在"}), 409

    return jsonify(row_to_dict(row)), 201


@app.put("/api/channels/<int:channel_id>")
def update_channel(channel_id: int):
    """更新采购渠道。"""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    contact = (data.get("contact") or "").strip() or None
    remark = (data.get("remark") or "").strip() or None

    if not name:
        return jsonify({"error": "渠道名称不能为空"}), 400

    try:
        with get_connection() as conn:
            old = conn.execute(
                "SELECT name FROM purchase_channels WHERE id = ?", (channel_id,)
            ).fetchone()
            if not old:
                return jsonify({"error": "渠道不存在"}), 404
            old_name = old["name"]
            result = conn.execute(
                "UPDATE purchase_channels SET name = ?, contact = ?, remark = ? WHERE id = ?",
                (name, contact, remark, channel_id),
            )
            if result.rowcount == 0:
                return jsonify({"error": "渠道不存在"}), 404
            conn.commit()
            row = conn.execute(
                "SELECT * FROM purchase_channels WHERE id = ?", (channel_id,)
            ).fetchone()
    except Exception:
        return jsonify({"error": "渠道名称已存在"}), 409

    return jsonify(row_to_dict(row))


@app.delete("/api/channels/<int:channel_id>")
def delete_channel(channel_id: int):
    """删除采购渠道（关联的缺件记录会保留但渠道置空）。"""
    with get_connection() as conn:
        channel = conn.execute(
            "SELECT name FROM purchase_channels WHERE id = ?", (channel_id,)
        ).fetchone()
        if not channel:
            return jsonify({"error": "渠道不存在"}), 404
        conn.execute(
            "DELETE FROM purchase_channels WHERE id = ?", (channel_id,)
        )
        conn.commit()
    return "", 204


# ── 统计汇总 ──────────────────────────────────────────


@app.get("/api/stats/summary")
def get_stats_summary():
    """获取费用统计汇总数据。"""
    with get_connection() as conn:
        total_row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_parts,
                SUM(CASE WHEN completion_date IS NOT NULL THEN 1 ELSE 0 END) AS completed_parts,
                SUM(CASE WHEN completion_date IS NULL THEN 1 ELSE 0 END) AS pending_parts,
                COALESCE(SUM(cost), 0) AS total_cost
            FROM missing_parts
            """
        ).fetchone()

        rank_rows = conn.execute(
            """
            SELECT
                g.id,
                g.name,
                COUNT(mp.id) AS part_count,
                COALESCE(SUM(mp.cost), 0) AS total_cost
            FROM games g
            LEFT JOIN missing_parts mp ON mp.game_id = g.id
            GROUP BY g.id, g.name
            ORDER BY total_cost DESC, g.name
            """
        ).fetchall()

    summary = row_to_dict(total_row)
    game_ranking = [row_to_dict(r) for r in rank_rows]

    return jsonify({
        "total_parts": summary["total_parts"],
        "completed_parts": summary["completed_parts"],
        "pending_parts": summary["pending_parts"],
        "total_cost": summary["total_cost"],
        "game_ranking": game_ranking,
    })


# ── 缺件 ──────────────────────────────────────────────


@app.get("/api/games/<int:game_id>/parts")
def list_parts(game_id: int):
    """获取指定游戏的缺件列表（包含渠道名称）。"""
    with get_connection() as conn:
        game = conn.execute(
            "SELECT * FROM games WHERE id = ?", (game_id,)
        ).fetchone()
        if not game:
            return jsonify({"error": "游戏不存在"}), 404

        rows = conn.execute(
            """
            SELECT mp.*,
                   c.name AS channel_name
            FROM missing_parts mp
            LEFT JOIN purchase_channels c ON c.id = mp.channel_id
            WHERE mp.game_id = ?
            ORDER BY mp.id
            """,
            (game_id,),
        ).fetchall()

    return jsonify([row_to_dict(r) for r in rows])


@app.post("/api/games/<int:game_id>/parts")
def create_part(game_id: int):
    """为指定游戏新增缺件记录。"""
    data = request.get_json(silent=True) or {}
    accessory = (data.get("accessory") or "").strip()
    replacement_plan = (data.get("replacement_plan") or "").strip()
    cost = data.get("cost", 0)
    completion_date = data.get("completion_date") or None
    channel_id = data.get("channel_id") or None

    if not accessory:
        return jsonify({"error": "配件名称不能为空"}), 400
    if not replacement_plan:
        return jsonify({"error": "替换方案不能为空"}), 400

    try:
        cost = float(cost)
    except (TypeError, ValueError):
        return jsonify({"error": "成本必须是数字"}), 400

    if channel_id is not None:
        try:
            channel_id = int(channel_id)
        except (TypeError, ValueError):
            return jsonify({"error": "渠道ID必须是数字"}), 400

    with get_connection() as conn:
        game = conn.execute(
            "SELECT id, name FROM games WHERE id = ?", (game_id,)
        ).fetchone()
        if not game:
            return jsonify({"error": "游戏不存在"}), 404

        if channel_id is not None:
            channel = conn.execute(
                "SELECT id FROM purchase_channels WHERE id = ?", (channel_id,)
            ).fetchone()
            if not channel:
                return jsonify({"error": "渠道不存在"}), 404

        cur = conn.execute(
            """
            INSERT INTO missing_parts
                (game_id, accessory, replacement_plan, cost, completion_date, channel_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (game_id, accessory, replacement_plan, cost, completion_date, channel_id),
        )
        write_log(conn, "新增缺件", accessory, f"所属游戏：{game['name']}")
        conn.commit()
        row = conn.execute(
            """
            SELECT mp.*,
                   c.name AS channel_name
            FROM missing_parts mp
            LEFT JOIN purchase_channels c ON c.id = mp.channel_id
            WHERE mp.id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()

    return jsonify(row_to_dict(row)), 201


@app.put("/api/parts/<int:part_id>")
def update_part(part_id: int):
    """更新缺件记录。"""
    data = request.get_json(silent=True) or {}
    accessory = (data.get("accessory") or "").strip()
    replacement_plan = (data.get("replacement_plan") or "").strip()
    cost = data.get("cost", 0)
    completion_date = data.get("completion_date") or None
    channel_id = data.get("channel_id") if "channel_id" in data else None

    if not accessory:
        return jsonify({"error": "配件名称不能为空"}), 400
    if not replacement_plan:
        return jsonify({"error": "替换方案不能为空"}), 400

    try:
        cost = float(cost)
    except (TypeError, ValueError):
        return jsonify({"error": "成本必须是数字"}), 400

    if channel_id is not None and channel_id != "":
        try:
            channel_id = int(channel_id)
        except (TypeError, ValueError):
            return jsonify({"error": "渠道ID必须是数字"}), 400
    else:
        channel_id = None

    with get_connection() as conn:
        old = conn.execute(
            """
            SELECT mp.*, c.name AS channel_name, g.name AS game_name
            FROM missing_parts mp
            LEFT JOIN purchase_channels c ON c.id = mp.channel_id
            LEFT JOIN games g ON g.id = mp.game_id
            WHERE mp.id = ?
            """,
            (part_id,),
        ).fetchone()
        if not old:
            return jsonify({"error": "缺件记录不存在"}), 404

        if channel_id is not None:
            channel = conn.execute(
                "SELECT id FROM purchase_channels WHERE id = ?", (channel_id,)
            ).fetchone()
            if not channel:
                return jsonify({"error": "渠道不存在"}), 404

        result = conn.execute(
            """
            UPDATE missing_parts
            SET accessory = ?, replacement_plan = ?, cost = ?, completion_date = ?, channel_id = ?
            WHERE id = ?
            """,
            (accessory, replacement_plan, cost, completion_date, channel_id, part_id),
        )
        if result.rowcount == 0:
            return jsonify({"error": "缺件记录不存在"}), 404

        changes = []
        if old["accessory"] != accessory:
            changes.append(f"配件：{old['accessory']} → {accessory}")
        if old["replacement_plan"] != replacement_plan:
            changes.append(f"替换方案：{old['replacement_plan']} → {replacement_plan}")
        if float(old["cost"]) != cost:
            changes.append(f"成本：{old['cost']} → {cost}")
        old_date = old["completion_date"] or ""
        new_date = completion_date or ""
        if old_date != new_date:
            changes.append(f"完成日期：{old['completion_date'] or '未完成'} → {completion_date or '未完成'}")
        old_ch = old["channel_id"]
        if (old_ch is None and channel_id is not None) or (old_ch is not None and channel_id is None) or (old_ch is not None and channel_id is not None and old_ch != channel_id):
            old_ch_name = old["channel_name"] or "未指定"
            new_ch_row = conn.execute("SELECT name FROM purchase_channels WHERE id = ?", (channel_id,)).fetchone() if channel_id else None
            new_ch_name = new_ch_row["name"] if new_ch_row else "未指定"
            changes.append(f"采购渠道：{old_ch_name} → {new_ch_name}")

        summary = "；".join(changes) if changes else "无变更"
        write_log(conn, "修改缺件", accessory, f"所属游戏：{old['game_name']}；{summary}")
        conn.commit()
        row = conn.execute(
            """
            SELECT mp.*,
                   c.name AS channel_name
            FROM missing_parts mp
            LEFT JOIN purchase_channels c ON c.id = mp.channel_id
            WHERE mp.id = ?
            """,
            (part_id,),
        ).fetchone()

    return jsonify(row_to_dict(row))


@app.delete("/api/parts/<int:part_id>")
def delete_part(part_id: int):
    """删除缺件记录。"""
    with get_connection() as conn:
        part = conn.execute(
            """
            SELECT mp.accessory, g.name AS game_name
            FROM missing_parts mp
            JOIN games g ON g.id = mp.game_id
            WHERE mp.id = ?
            """,
            (part_id,),
        ).fetchone()
        if not part:
            return jsonify({"error": "缺件记录不存在"}), 404
        write_log(conn, "删除缺件", part["accessory"], f"所属游戏：{part['game_name']}")
        conn.execute(
            "DELETE FROM missing_parts WHERE id = ?", (part_id,)
        )
        conn.commit()
    return "", 204


# ── 操作日志 ──────────────────────────────────────────


@app.get("/api/logs")
def list_logs():
    """获取最近 50 条操作日志，支持按 op_type 筛选。"""
    op_type = request.args.get("op_type", "").strip()
    with get_connection() as conn:
        if op_type:
            rows = conn.execute(
                """
                SELECT * FROM operation_logs
                WHERE op_type = ?
                ORDER BY id DESC
                LIMIT 50
                """,
                (op_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM operation_logs
                ORDER BY id DESC
                LIMIT 50
                """
            ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


# ── 数据备份与恢复 ─────────────────────────────────────

BACKUP_VERSION = "1.0"


@app.get("/api/backup/export")
def export_backup():
    """导出全部游戏、采购渠道和缺件数据为结构化 JSON 文件。"""
    with get_connection() as conn:
        games = [row_to_dict(r) for r in conn.execute("SELECT id, name FROM games ORDER BY id").fetchall()]
        channels = [
            row_to_dict(r)
            for r in conn.execute(
                "SELECT id, name, contact, remark FROM purchase_channels ORDER BY id"
            ).fetchall()
        ]
        parts = [
            row_to_dict(r)
            for r in conn.execute(
                """
                SELECT id, game_id, channel_id, accessory, replacement_plan,
                       cost, completion_date
                FROM missing_parts
                ORDER BY id
                """
            ).fetchall()
        ]

    backup_data = {
        "version": BACKUP_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "games": len(games),
            "channels": len(channels),
            "missing_parts": len(parts),
        },
        "games": games,
        "purchase_channels": channels,
        "missing_parts": parts,
    }

    filename = f"boardgame_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    json_bytes = json.dumps(backup_data, ensure_ascii=False, indent=2).encode("utf-8")
    buf = BytesIO(json_bytes)
    buf.seek(0)

    with get_connection() as conn:
        write_log(
            conn,
            "数据备份",
            "导出数据",
            f"游戏：{len(games)} 个，渠道：{len(channels)} 个，缺件：{len(parts)} 条",
        )
        conn.commit()

    return send_file(
        buf,
        mimetype="application/json",
        as_attachment=True,
        download_name=filename,
    )


def _validate_backup_structure(data: dict) -> list[str]:
    """校验备份数据结构，返回错误信息列表（空列表表示校验通过）。"""
    errors = []

    if not isinstance(data, dict):
        return ["备份文件格式无效：根节点必须是对象"]

    if data.get("version") != BACKUP_VERSION:
        errors.append(f"备份版本不兼容：期望 {BACKUP_VERSION}，实际 {data.get('version')}")

    for key in ("games", "purchase_channels", "missing_parts"):
        if key not in data:
            errors.append(f"缺少必填字段：{key}")
        elif not isinstance(data[key], list):
            errors.append(f"字段 {key} 必须是数组")

    if errors:
        return errors

    for idx, g in enumerate(data["games"]):
        if not isinstance(g, dict):
            errors.append(f"games[{idx}] 必须是对象")
            continue
        if "name" not in g or not isinstance(g["name"], str) or not g["name"].strip():
            errors.append(f"games[{idx}] 缺少有效 name 字段")

    for idx, c in enumerate(data["purchase_channels"]):
        if not isinstance(c, dict):
            errors.append(f"purchase_channels[{idx}] 必须是对象")
            continue
        if "name" not in c or not isinstance(c["name"], str) or not c["name"].strip():
            errors.append(f"purchase_channels[{idx}] 缺少有效 name 字段")

    for idx, p in enumerate(data["missing_parts"]):
        if not isinstance(p, dict):
            errors.append(f"missing_parts[{idx}] 必须是对象")
            continue
        for field in ("game_id", "accessory", "replacement_plan"):
            if field not in p:
                errors.append(f"missing_parts[{idx}] 缺少必填字段 {field}")
        if "accessory" in p and (not isinstance(p["accessory"], str) or not p["accessory"].strip()):
            errors.append(f"missing_parts[{idx}] accessory 不能为空")
        if "replacement_plan" in p and (
            not isinstance(p["replacement_plan"], str) or not p["replacement_plan"].strip()
        ):
            errors.append(f"missing_parts[{idx}] replacement_plan 不能为空")
        if "cost" in p and not isinstance(p["cost"], (int, float)):
            errors.append(f"missing_parts[{idx}] cost 必须是数字")

    return errors


@app.post("/api/backup/import")
def import_backup():
    """
    从备份文件批量导入数据。
    参数 mode: overwrite（覆盖，清空现有数据后导入）| merge（合并，按名称去重）
    """
    mode = request.args.get("mode", "merge").strip().lower()
    if mode not in ("overwrite", "merge"):
        return jsonify({"error": "mode 参数必须是 overwrite 或 merge"}), 400

    if "file" not in request.files:
        return jsonify({"error": "未找到上传的文件"}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "文件名为空"}), 400

    try:
        raw = file.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return jsonify({"error": f"文件解析失败：{e}"}), 400

    errors = _validate_backup_structure(data)
    if errors:
        return jsonify({"error": "数据格式校验未通过", "details": errors}), 400

    src_games = data["games"]
    src_channels = data["purchase_channels"]
    src_parts = data["missing_parts"]

    # 构建 game_id 的映射：原始备份中的 id -> 新建或找到的 id
    old_game_id_to_new = {}
    old_channel_id_to_new = {}

    try:
        with get_connection() as conn:
            if mode == "overwrite":
                conn.execute("DELETE FROM missing_parts")
                conn.execute("DELETE FROM games")
                conn.execute("DELETE FROM purchase_channels")

            inserted_games = 0
            inserted_channels = 0

            # 导入游戏
            for g in src_games:
                name = g["name"].strip()
                if mode == "merge":
                    existing = conn.execute(
                        "SELECT id FROM games WHERE name = ?", (name,)
                    ).fetchone()
                    if existing:
                        old_game_id_to_new[g.get("id")] = existing["id"]
                        continue
                cur = conn.execute("INSERT INTO games (name) VALUES (?)", (name,))
                old_game_id_to_new[g.get("id")] = cur.lastrowid
                inserted_games += 1

            # 导入采购渠道
            for c in src_channels:
                name = c["name"].strip()
                contact = (c.get("contact") or "").strip() or None
                remark = (c.get("remark") or "").strip() or None
                if mode == "merge":
                    existing = conn.execute(
                        "SELECT id FROM purchase_channels WHERE name = ?", (name,)
                    ).fetchone()
                    if existing:
                        old_channel_id_to_new[c.get("id")] = existing["id"]
                        continue
                cur = conn.execute(
                    "INSERT INTO purchase_channels (name, contact, remark) VALUES (?, ?, ?)",
                    (name, contact, remark),
                )
                old_channel_id_to_new[c.get("id")] = cur.lastrowid
                inserted_channels += 1

            # 导入缺件记录
            inserted_parts = 0
            skipped_parts = 0
            for p in src_parts:
                old_game_id = p.get("game_id")
                new_game_id = old_game_id_to_new.get(old_game_id)
                if not new_game_id:
                    skipped_parts += 1
                    continue

                accessory = p["accessory"].strip()
                replacement_plan = p["replacement_plan"].strip()
                cost = float(p.get("cost", 0) or 0)
                completion_date = p.get("completion_date") or None

                old_channel_id = p.get("channel_id")
                new_channel_id = old_channel_id_to_new.get(old_channel_id) if old_channel_id is not None else None

                if mode == "merge":
                    existing = conn.execute(
                        """
                        SELECT id FROM missing_parts
                        WHERE game_id = ? AND accessory = ? AND replacement_plan = ?
                        """,
                        (new_game_id, accessory, replacement_plan),
                    ).fetchone()
                    if existing:
                        skipped_parts += 1
                        continue

                conn.execute(
                    """
                    INSERT INTO missing_parts
                        (game_id, channel_id, accessory, replacement_plan, cost, completion_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (new_game_id, new_channel_id, accessory, replacement_plan, cost, completion_date),
                )
                inserted_parts += 1

            result_summary = {
                "games_inserted": inserted_games,
                "channels_inserted": inserted_channels,
                "parts_inserted": inserted_parts,
                "parts_skipped": skipped_parts,
            }

            write_log(
                conn,
                "数据恢复",
                f"{'覆盖模式' if mode == 'overwrite' else '合并模式'}导入",
                (
                    f"游戏：{result_summary['games_inserted']} 个，"
                    f"渠道：{result_summary['channels_inserted']} 个，"
                    f"缺件：{result_summary['parts_inserted']} 条（跳过 {skipped_parts} 条）"
                ),
            )
            conn.commit()

        return jsonify(
            {
                "message": "导入成功",
                "mode": mode,
                "summary": result_summary,
            }
        )

    except Exception as e:
        return jsonify({"error": f"导入过程中发生错误：{e}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
