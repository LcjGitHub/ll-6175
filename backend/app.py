"""桌游缺件替换记录 API。"""

from flask import Flask, jsonify, request
from flask_cors import CORS

from db import get_connection, init_db

app = Flask(__name__)
CORS(app)

init_db()


def row_to_dict(row):
    """将 sqlite3.Row 转为 dict。"""
    return dict(row) if row else None


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
            result = conn.execute(
                "UPDATE games SET name = ? WHERE id = ?", (name, game_id)
            )
            if result.rowcount == 0:
                return jsonify({"error": "游戏不存在"}), 404
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
        result = conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
        if result.rowcount == 0:
            return jsonify({"error": "游戏不存在"}), 404
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
    """获取指定游戏的缺件列表。"""
    with get_connection() as conn:
        game = conn.execute(
            "SELECT * FROM games WHERE id = ?", (game_id,)
        ).fetchone()
        if not game:
            return jsonify({"error": "游戏不存在"}), 404

        rows = conn.execute(
            """
            SELECT * FROM missing_parts
            WHERE game_id = ?
            ORDER BY id
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

    if not accessory:
        return jsonify({"error": "配件名称不能为空"}), 400
    if not replacement_plan:
        return jsonify({"error": "替换方案不能为空"}), 400

    try:
        cost = float(cost)
    except (TypeError, ValueError):
        return jsonify({"error": "成本必须是数字"}), 400

    with get_connection() as conn:
        game = conn.execute(
            "SELECT id FROM games WHERE id = ?", (game_id,)
        ).fetchone()
        if not game:
            return jsonify({"error": "游戏不存在"}), 404

        cur = conn.execute(
            """
            INSERT INTO missing_parts
                (game_id, accessory, replacement_plan, cost, completion_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (game_id, accessory, replacement_plan, cost, completion_date),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM missing_parts WHERE id = ?", (cur.lastrowid,)
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

    if not accessory:
        return jsonify({"error": "配件名称不能为空"}), 400
    if not replacement_plan:
        return jsonify({"error": "替换方案不能为空"}), 400

    try:
        cost = float(cost)
    except (TypeError, ValueError):
        return jsonify({"error": "成本必须是数字"}), 400

    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE missing_parts
            SET accessory = ?, replacement_plan = ?, cost = ?, completion_date = ?
            WHERE id = ?
            """,
            (accessory, replacement_plan, cost, completion_date, part_id),
        )
        if result.rowcount == 0:
            return jsonify({"error": "缺件记录不存在"}), 404
        conn.commit()
        row = conn.execute(
            "SELECT * FROM missing_parts WHERE id = ?", (part_id,)
        ).fetchone()

    return jsonify(row_to_dict(row))


@app.delete("/api/parts/<int:part_id>")
def delete_part(part_id: int):
    """删除缺件记录。"""
    with get_connection() as conn:
        result = conn.execute(
            "DELETE FROM missing_parts WHERE id = ?", (part_id,)
        )
        if result.rowcount == 0:
            return jsonify({"error": "缺件记录不存在"}), 404
        conn.commit()
    return "", 204


if __name__ == "__main__":
    app.run(debug=True, port=5000)
