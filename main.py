import sys
import os
from datetime import datetime  # 新增，为缓存导出用
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QSplitter,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
    QLabel,
    QTabWidget,
)
from PyQt6.QtCore import Qt

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from model.predictor_thread import PredictorThread
from database.db_manager import DBManager
from ui.predict_tab import PredictTab
from ui.batch_tab import BatchTab
from ui.history_tab import HistoryTab
from ui.cache_tab import CacheTab  # 新增导入


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("英文名字国籍预测系统 v1.0")
        self.setMinimumSize(1300, 800)  # 稍微增高以容纳双标签页

        # 初始化核心组件
        self.db_manager = DBManager()
        self.predictor_thread = PredictorThread()

        # 检查模型
        if not self.predictor_thread.initialize():
            QMessageBox.critical(
                self,
                "初始化失败",
                "无法加载模型文件，请确认 best_name_classifier.pth 存在\n程序将退出。",
            )
            sys.exit(1)

        self._init_ui()

    def _init_ui(self):
        # 主分割器：左（功能区）右（信息区）
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # === 左侧：预测功能区 ===
        left_tabs = QTabWidget()
        left_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #ddd; }
            QTabBar::tab {
                background: #e0e0e0;
                padding: 10px 20px;
                margin-right: 2px;
            }
            QTabBar::tab:selected { 
                background: #2196F3; 
                color: white;
                font-weight: bold;
            }
            QTabBar::tab:hover { background: #bbdefb; }
        """)

        # 单预测
        self.predict_tab = PredictTab(self.predictor_thread, self.db_manager)
        left_tabs.addTab(self.predict_tab, "🎯 单名字预测")

        # 批量预测
        self.batch_tab = BatchTab(self.predictor_thread, self.db_manager)
        left_tabs.addTab(self.batch_tab, "📁 批量预测")

        splitter.addWidget(left_tabs)

        # === 右侧：信息展示区（改为双标签页） ===
        right_tabs = QTabWidget()
        right_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #ddd; }
            QTabBar::tab {
                background: #f5f5f5;
                padding: 8px 15px;
            }
            QTabBar::tab:selected { 
                background: #4CAF50; 
                color: white;
                font-weight: bold;
            }
        """)

        # 历史记录标签页
        self.history_tab = HistoryTab(self.db_manager)
        right_tabs.addTab(self.history_tab, "📜 历史记录")

        # 缓存管理标签页（新增）
        self.cache_tab = CacheTab(self.db_manager)
        right_tabs.addTab(self.cache_tab, "💾 缓存管理")

        splitter.addWidget(right_tabs)

        # 设置比例 3:2
        splitter.setSizes([800, 500])
        self.setCentralWidget(splitter)

        # 信号连接：预测完成后自动刷新右侧两个标签页
        self.predictor_thread.result_ready.connect(self._on_prediction_finished)
        # 批量预测完成也刷新（BatchTab内部已处理，但这里统一刷新缓存和历史）

        self.batch_tab.batch_finished.connect(self._on_batch_finished)

        menubar = self.menuBar()
        help_menu = menubar.addMenu("帮助")

        about_action = help_menu.addAction("关于")
        about_action.triggered.connect(self._show_about)

    def _show_about(self):
        """关于对话框（包含软著信息）"""
        QMessageBox.about(
            self,
            "关于",
            "<h2>英文名字国籍预测系统 v1.0</h2>"
            "<p>基于深度学习的英文名字国籍预测工具</p>"
            "<p><b>技术栈：</b>PyTorch + PyQt6 + SQLite</p>"
            "<p><b>模型准确率：</b>82.72%</p>"
            "<p><b>功能特性：</b></p>"
            "<ul>"
            "<li>单名字智能预测</li>"
            "<li>批量文件处理</li>"
            "<li>用户纠正缓存</li>"
            "<li>历史记录管理</li>"
            "</ul>"
            "<p style='color: #666;'>© 2025 软件开发实践课程设计</p>",
        )

    def _on_prediction_finished(self, name, results):
        """单预测完成：刷新历史记录"""
        self.history_tab.refresh_history()

    def _on_batch_finished(self):
        """批量预测完成：刷新历史记录和缓存"""
        self.history_tab.refresh_history()
        # 如果批量预测中有纠正操作，也需要刷新缓存页
        self.cache_tab.refresh_cache()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 全局样式表（Day 3 美化）
    app.setStyleSheet("""
        QMainWindow {
            background-color: #fafafa;
        }
        QWidget {
            font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
        }
        QTableWidget {
            gridline-color: #e0e0e0;
            border: 1px solid #e0e0e0;
            selection-background-color: #bbdefb;
        }
        QHeaderView::section {
            background-color: #f5f5f5;
            padding: 8px;
            border: 1px solid #ddd;
            font-weight: bold;
            color: #333;
        }
        QLineEdit {
            padding: 5px;
            border: 2px solid #e0e0e0;
            border-radius: 4px;
        }
        QLineEdit:focus {
            border-color: #2196F3;
        }
        QProgressBar {
            border: 2px solid #e0e0e0;
            border-radius: 5px;
            text-align: center;
            font-weight: bold;
        }
        QProgressBar::chunk {
            background-color: #4CAF50;
            border-radius: 5px;
        }
        QMessageBox {
            font-size: 14px;
        }
    """)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
