from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QHeaderView,
    QAbstractItemView,
    QMessageBox,
    QFileDialog,
)
from PyQt6.QtCore import Qt
from datetime import datetime
import json


class CacheTab(QWidget):
    """
    缓存管理（用况5）
    查看、删除、导出用户纠正的缓存数据
    """

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._init_ui()
        self.refresh_cache()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 标题栏
        header_layout = QHBoxLayout()
        title = QLabel("用户纠正缓存管理")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(title)

        # 统计信息
        self.stats_label = QLabel("共 0 条缓存")
        self.stats_label.setStyleSheet("color: #666;")
        header_layout.addStretch()
        header_layout.addWidget(self.stats_label)
        layout.addLayout(header_layout)

        # 说明文字
        hint = QLabel(
            "💡 以下为用户手动纠正过的名字-国籍映射。下次输入相同名字时将优先显示缓存结果。\n命中次数越多，说明该纠正越常被使用。"
        )
        hint.setStyleSheet("color: #666; font-size: 12px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["名字", "纠正为", "命中次数", "最后使用"])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)

        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 150)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)

        # 操作按钮
        btn_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        self.refresh_btn.clicked.connect(self.refresh_cache)

        self.delete_btn = QPushButton("🗑 删除选中")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QPushButton:hover { background-color: #D32F2F; }
        """)
        self.delete_btn.clicked.connect(self._delete_selected)

        self.clear_btn = QPushButton("⚠️ 清空全部")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #9E9E9E;
                color: white;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QPushButton:hover { background-color: #616161; }
        """)
        self.clear_btn.clicked.connect(self._clear_all)

        self.export_btn = QPushButton("💾 导出缓存")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QPushButton:hover { background-color: #388E3C; }
        """)
        self.export_btn.clicked.connect(self._export_cache)

        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.clear_btn)
        layout.addLayout(btn_layout)

    def refresh_cache(self):
        """刷新缓存表格"""
        records = self.db_manager.get_all_corrections()

        self.table.setRowCount(len(records))

        for row_idx, record in enumerate(records):
            # 名字
            name_item = QTableWidgetItem(record.get("name", ""))
            self.table.setItem(row_idx, 0, name_item)

            # 纠正为（国籍）
            country = record.get("corrected_country", "")
            country_item = QTableWidgetItem(country)
            country_item.setForeground(Qt.GlobalColor.blue)
            country_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 1, country_item)

            # 命中次数（高亮高频缓存）
            hits = record.get("hit_count", 0)
            hit_item = QTableWidgetItem(str(hits))
            hit_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if hits >= 5:
                hit_item.setForeground(Qt.GlobalColor.darkGreen)
                hit_item.setToolTip("高频使用缓存")
            self.table.setItem(row_idx, 2, hit_item)

            # 最后使用时间
            last_used = record.get("last_used", "")
            time_item = QTableWidgetItem(str(last_used))
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 3, time_item)

        self.stats_label.setText(f"共 {len(records)} 条缓存")

    def _delete_selected(self):
        """删除选中的缓存条目"""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "提示", "请先选择要删除的行")
            return

        # 获取选中的行号（每行有4列，所以取整除）
        rows = set(item.row() for item in selected)

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除选中的 {len(rows)} 条缓存记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            for row in sorted(rows, reverse=True):  # 倒序删除避免索引错乱
                name = self.table.item(row, 0).text()
                self.db_manager.delete_correction(name)

            self.refresh_cache()
            QMessageBox.information(self, "成功", f"已删除 {len(rows)} 条缓存")

    def _clear_all(self):
        """清空所有缓存"""
        count = self.table.rowCount()
        if count == 0:
            QMessageBox.information(self, "提示", "缓存已为空")
            return

        reply = QMessageBox.warning(
            self,
            "危险操作",
            f"确定要清空全部 {count} 条缓存吗？\n此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.db_manager.clear_all_corrections()
            self.refresh_cache()
            QMessageBox.information(self, "成功", "已清空所有缓存")

    def _export_cache(self):
        """导出缓存为JSON（供后续模型重训练使用）"""
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "提示", "没有可导出的缓存数据")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出纠正缓存", "correction_cache.json", "JSON文件 (*.json)"
        )

        if not file_path:
            return

        try:
            records = self.db_manager.get_all_corrections()

            # 导出为结构化JSON
            export_data = {
                "export_time": str(datetime.now()),
                "total_count": len(records),
                "corrections": [
                    {
                        "name": r["name"],
                        "corrected_country": r["corrected_country"],
                        "hit_count": r["hit_count"],
                        "last_used": r["last_used"],
                    }
                    for r in records
                ],
            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            QMessageBox.information(
                self,
                "导出成功",
                f"已导出 {len(records)} 条纠正记录到:\n{file_path}\n\n"
                f"这些高质量标注数据可用于后续模型优化训练。",
            )

        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
