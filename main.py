import sys
import os

import numpy as np

from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QSplitter,
    QWidget,
    QVBoxLayout,
    QMessageBox,
    QLabel,
    QTabWidget,
)
from PyQt6.QtCore import Qt

# ========== 调试日志（打包后查看）==========
log_path = os.path.join(
    os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__),
    "debug.log",
)


def log(msg):
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] {msg}\n")
            f.flush()
    except:
        pass  # 如果日志也写不了，至少不崩溃


log("=" * 50)
log("程序启动")
log(f"sys.frozen: {getattr(sys, 'frozen', False)}")
log(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'None')}")
log(f"sys.executable: {sys.executable}")
log(f"当前工作目录: {os.getcwd()}")
# ===========================================

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 关键：导入 get_resource_path
from model.predictor_thread import PredictorThread, get_resource_path
from database.db_manager import DBManager
from ui.predict_tab import PredictTab
from ui.batch_tab import BatchTab
from ui.history_tab import HistoryTab
from ui.cache_tab import CacheTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("英文名字国籍预测系统 v1.0")
        self.setMinimumSize(1300, 800)

        log("开始初始化 MainWindow")

        # ========== 数据库路径（exe 同级目录）==========
        db_path = os.path.join(
            os.path.dirname(
                sys.executable if getattr(sys, "frozen", False) else __file__
            ),
            "name_history.db",
        )
        log(f"数据库路径: {db_path}")
        self.db_manager = DBManager(db_path)

        # ========== 模型路径（打包内部或同级目录）==========
        model_path = get_resource_path("model/best_name_classifier.pth")
        log(f"模型查找路径: {model_path}")

        # 检查路径是否存在
        if not os.path.exists(model_path):
            log(f"模型不存在于: {model_path}")
            # 尝试备选路径（onedir 模式：exe同级的model/）
            alt_path = os.path.join(
                os.path.dirname(
                    sys.executable if getattr(sys, "frozen", False) else __file__
                ),
                "model",
                "best_name_classifier.pth",
            )
            log(f"尝试备选路径: {alt_path}")
            if os.path.exists(alt_path):
                model_path = alt_path
                log("使用备选路径成功")
            else:
                log("备选路径也不存在")
                # 再尝试当前工作目录
                cwd_path = os.path.join(
                    os.getcwd(), "model", "best_name_classifier.pth"
                )
                log(f"尝试CWD路径: {cwd_path}")
                if os.path.exists(cwd_path):
                    model_path = cwd_path
                    log("使用CWD路径成功")

        log(f"最终模型路径: {model_path}")
        log(f"最终路径是否存在: {os.path.exists(model_path)}")

        # 初始化预测器（传入路径）
        self.predictor_thread = PredictorThread(model_path)

        # 检查模型
        try:
            if not self.predictor_thread.initialize():
                log("模型初始化返回 False")
                QMessageBox.critical(
                    self,
                    "初始化失败",
                    f"无法加载模型文件: {model_path}\n请确认模型文件存在。",
                )
                sys.exit(1)
            log("模型初始化成功")
        except Exception as e:
            log(f"初始化异常: {str(e)}")
            import traceback

            log(traceback.format_exc())
            QMessageBox.critical(self, "初始化失败", f"错误: {str(e)}")
            sys.exit(1)

        self._init_ui()

    def _init_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧功能区
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

        self.predict_tab = PredictTab(self.predictor_thread, self.db_manager)
        left_tabs.addTab(self.predict_tab, "🎯 单名字预测")

        self.batch_tab = BatchTab(self.predictor_thread, self.db_manager)
        left_tabs.addTab(self.batch_tab, "📁 批量预测")

        splitter.addWidget(left_tabs)

        # 右侧信息区
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

        self.history_tab = HistoryTab(self.db_manager)
        right_tabs.addTab(self.history_tab, "📜 历史记录")

        self.cache_tab = CacheTab(self.db_manager)
        right_tabs.addTab(self.cache_tab, "💾 缓存管理")

        splitter.addWidget(right_tabs)

        splitter.setSizes([800, 500])
        self.setCentralWidget(splitter)

        # 信号连接
        self.predictor_thread.result_ready.connect(self._on_prediction_finished)
        self.batch_tab.batch_finished.connect(self._on_batch_finished)

        # 菜单栏
        menubar = self.menuBar()
        help_menu = menubar.addMenu("帮助")
        about_action = help_menu.addAction("关于")
        about_action.triggered.connect(self._show_about)

    def _show_about(self):
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
        self.history_tab.refresh_history()

    def _on_batch_finished(self):
        self.history_tab.refresh_history()
        self.cache_tab.refresh_cache()


if __name__ == "__main__":
    log("进入 __main__")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    app.setStyleSheet("""
        QMainWindow { background-color: #fafafa; }
        QWidget { font-family: "Microsoft YaHei", "Segoe UI", sans-serif; }
        QTableWidget { gridline-color: #e0e0e0; border: 1px solid #e0e0e0; selection-background-color: #bbdefb; }
        QHeaderView::section { background-color: #f5f5f5; padding: 8px; border: 1px solid #ddd; font-weight: bold; color: #333; }
        QLineEdit { padding: 5px; border: 2px solid #e0e0e0; border-radius: 4px; }
        QLineEdit:focus { border-color: #2196F3; }
        QProgressBar { border: 2px solid #e0e0e0; border-radius: 5px; text-align: center; font-weight: bold; }
        QProgressBar::chunk { background-color: #4CAF50; border-radius: 5px; }
        QMessageBox { font-size: 14px; }
    """)

    window = MainWindow()
    window.show()
    log("窗口显示成功")

    sys.exit(app.exec())
