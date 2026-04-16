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
)
from PyQt6.QtCore import Qt


class HistoryTab(QWidget):
    """
    历史记录查询（用况3）
    展示过往预测记录，支持刷新
    """

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._init_ui()
        self.refresh_history()  # 启动时自动加载

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 标题栏 + 刷新按钮
        header_layout = QHBoxLayout()
        title = QLabel("预测历史记录")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(title)

        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.refresh_btn.clicked.connect(self.refresh_history)
        header_layout.addStretch()
        header_layout.addWidget(self.refresh_btn)
        layout.addLayout(header_layout)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["时间", "名字", "预测国籍", "置信度", "状态"]
        )

        # 表格样式设置
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)

        self.table.setColumnWidth(0, 150)  # 时间
        self.table.setColumnWidth(3, 80)  # 置信度
        self.table.setColumnWidth(4, 100)  # 状态

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)

        # 统计信息
        self.stats_label = QLabel("共 0 条记录")
        self.stats_label.setStyleSheet("color: #666;")
        layout.addWidget(self.stats_label)

    def refresh_history(self):
        """从数据库刷新历史记录"""
        records = self.db_manager.get_recent_history(limit=100)

        self.table.setRowCount(len(records))

        for row_idx, record in enumerate(records):
            # 时间
            time_item = QTableWidgetItem(str(record.get("timestamp", "")))
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 0, time_item)

            # 名字
            name_item = QTableWidgetItem(record.get("name", ""))
            self.table.setItem(row_idx, 1, name_item)

            # 预测国籍
            pred_item = QTableWidgetItem(record.get("predicted_country", ""))
            pred_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 2, pred_item)

            # 置信度（百分比格式）
            conf = record.get("confidence", 0)
            conf_item = QTableWidgetItem(f"{conf * 100:.1f}%")
            conf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # 根据置信度设置颜色
            if conf >= 0.8:
                conf_item.setForeground(Qt.GlobalColor.darkGreen)
            elif conf >= 0.5:
                conf_item.setForeground(Qt.GlobalColor.darkYellow)
            else:
                conf_item.setForeground(Qt.GlobalColor.red)

            self.table.setItem(row_idx, 3, conf_item)

            # 状态（是否纠正）
            is_corrected = record.get("is_corrected", 0)
            if is_corrected:
                corrected_country = record.get("corrected_country", "")
                status_text = f"已纠正为 {corrected_country}"
                status_item = QTableWidgetItem(status_text)
                status_item.setForeground(Qt.GlobalColor.blue)
            else:
                status_item = QTableWidgetItem("原始预测")

            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 4, status_item)

        self.stats_label.setText(f"共 {len(records)} 条记录（显示最近100条）")
