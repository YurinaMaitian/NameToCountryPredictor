import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class DBManager:
    """SQLite数据库管理器 - 支持历史记录与纠错缓存"""

    def __init__(self, db_path: str = "name_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库表结构（如果不存在则创建）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 用况1/2/3: 历史记录表（单预测 + 批量预测）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    predicted_country TEXT NOT NULL,
                    confidence REAL,
                    is_corrected BOOLEAN DEFAULT 0,
                    corrected_country TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    source TEXT DEFAULT 'single'  -- 'single'或'batch'区分单条/批量
                )
            """)

            # 用况4/5: 用户纠正缓存表（LRU机制）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS corrections_cache (
                    name TEXT PRIMARY KEY,
                    corrected_country TEXT NOT NULL,
                    hit_count INTEGER DEFAULT 1,
                    last_used DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    def save_prediction(
        self, name: str, country: str, confidence: float, source: str = "single"
    ) -> Optional[int]:
        """
        保存预测记录（用况1：单预测，用况2：批量）
        返回: 插入的记录ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO predictions (name, predicted_country, confidence, source)
                VALUES (?, ?, ?, ?)
            """,
                (name, country, confidence, source),
            )
            conn.commit()
            return cursor.lastrowid

    def get_recent_history(self, limit: int = 50) -> List[Dict]:
        """
        获取最近预测历史（用况3：历史记录查询）
        返回: [{id, name, predicted_country, confidence, timestamp}, ...]
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, predicted_country, confidence, 
                       is_corrected, corrected_country, timestamp
                FROM predictions
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def check_cache(self, name: str) -> Optional[Tuple[str, int]]:
        """
        检查缓存（用况4：纠错功能前置）
        返回: (corrected_country, hit_count) 或 None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT corrected_country, hit_count 
                FROM corrections_cache 
                WHERE name = ?
            """,
                (name,),
            )
            result = cursor.fetchone()

            if result:
                # 更新LRU时间戳和命中次数
                cursor.execute(
                    """
                    UPDATE corrections_cache 
                    SET hit_count = hit_count + 1, last_used = ?
                    WHERE name = ?
                """,
                    (datetime.now(), name),
                )
                conn.commit()
                return result
            return None

    def save_correction(self, name: str, corrected_country: str):
        """
        保存用户纠正（用况4：纠错）
        如果已存在则更新，不存在则插入
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO corrections_cache (name, corrected_country, hit_count)
                VALUES (?, ?, 1)
                ON CONFLICT(name) DO UPDATE SET
                    corrected_country = excluded.corrected_country,
                    hit_count = corrections_cache.hit_count + 1,
                    last_used = ?
            """,
                (name, corrected_country, datetime.now()),
            )
            conn.commit()

    def get_all_corrections(self) -> List[Dict]:
        """
        获取所有纠正记录（用况5：缓存管理）
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, corrected_country, hit_count, last_used
                FROM corrections_cache
                ORDER BY last_used DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def delete_correction(self, name: str):
        """删除特定纠正记录"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM corrections_cache WHERE name = ?", (name,))
            conn.commit()

    def clear_all_corrections(self):
        """清空所有缓存"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM corrections_cache")
            conn.commit()

    def update_prediction_correction(self, record_id: int, corrected_country: str):
        """标记某条历史记录已被纠正"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE predictions 
                SET is_corrected = 1, corrected_country = ?
                WHERE id = ?
            """,
                (corrected_country, record_id),
            )
            conn.commit()
