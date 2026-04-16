from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QMessageBox,
    QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6 import QtGui
from PyQt6.QtGui import QColor


class PredictTab(QWidget):
    """
    单预测标签页（用况1：单名字预测）
    包含：输入框、预测按钮、Top-3结果展示、纠正按钮
    """

    def __init__(self, predictor_thread, db_manager, parent=None):
        super().__init__(parent)
        self.predictor_thread = predictor_thread
        self.db_manager = db_manager
        self.current_name = None
        self.current_results = None

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 输入区域（保持不变）
        input_layout = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("请输入英文名字（如：John Smith）...")
        self.name_input.setMinimumHeight(40)  # 稍微加高输入框
        self.name_input.setStyleSheet("""
            QLineEdit {
                font-size: 14px;
                padding: 5px 10px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
            }
            QLineEdit:focus { border-color: #2196F3; }
        """)

        self.predict_btn = QPushButton("🚀 开始预测")  # 加图标
        self.predict_btn.setMinimumHeight(40)
        self.predict_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 20px;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:pressed { background-color: #0D47A1; }
            QPushButton:disabled { background-color: #BDBDBD; }
        """)

        input_layout.addWidget(self.name_input, stretch=4)
        input_layout.addWidget(self.predict_btn, stretch=1)
        layout.addLayout(input_layout)

        # 缓存命中提示（放大字体，加背景色）
        self.cache_label = QLabel("")
        self.cache_label.setStyleSheet("""
            QLabel {
                color: #2E7D32;
                font-weight: bold;
                font-size: 13px;
                background-color: #E8F5E9;
                padding: 8px 12px;
                border-radius: 4px;
                border-left: 4px solid #4CAF50;
            }
        """)
        self.cache_label.setWordWrap(True)  # 允许换行
        layout.addWidget(self.cache_label)

        # 结果区域标题
        result_header = QLabel("🎯 预测结果 (Top 3):")
        result_header.setStyleSheet("font-weight: bold; font-size: 14px; color: #333;")
        layout.addWidget(result_header)

        # 结果列表（加高度）
        self.result_list = QListWidget()
        self.result_list.setMinimumHeight(220)  # 加高以填充空间
        self.result_list.setSpacing(8)  # 增加行间距
        self.result_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 10px;
                background-color: #fafafa;
            }
            QListWidget::item {
                padding: 12px;
                border-radius: 4px;
                margin-bottom: 5px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
        """)
        layout.addWidget(self.result_list, stretch=1)  # 让结果列表占据剩余空间

        # === 关键修改：纠正按钮区域（从底部移到结果下方，放大）===
        correction_area = QWidget()
        corr_layout = QVBoxLayout(correction_area)  # 改为垂直布局，更醒目
        corr_layout.setContentsMargins(0, 10, 0, 0)
        corr_layout.setSpacing(10)

        # 分隔线（视觉分割）
        line = QLabel()
        line.setStyleSheet("background-color: #e0e0e0; max-height: 2px;")
        line.setMinimumHeight(2)
        corr_layout.addWidget(line)

        # 纠正按钮（大按钮，居中）
        self.correct_btn = QPushButton("✏️ 纠正预测结果（选择正确国籍）")
        self.correct_btn.setMinimumHeight(50)  # 加高
        self.correct_btn.setEnabled(False)
        corr_layout.addWidget(self.correct_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # 提示文字（小字说明）
        hint = QLabel("💡 如果预测不准确，点击上方按钮纠正，系统将学习您的反馈")
        hint.setStyleSheet("color: #666; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        corr_layout.addWidget(hint)

        layout.addWidget(correction_area)

        # 状态栏（底部）
        self.status_label = QLabel("就绪 - 请输入名字开始预测")
        self.status_label.setStyleSheet(
            "color: #666; font-size: 12px; padding-top: 10px;"
        )
        layout.addWidget(self.status_label)

    def _connect_signals(self):
        self.predict_btn.clicked.connect(self._on_predict)
        self.name_input.returnPressed.connect(self._on_predict)  # 回车触发
        self.predictor_thread.result_ready.connect(self._on_result_ready)
        self.predictor_thread.error_occurred.connect(self._on_error)
        self.correct_btn.clicked.connect(self._on_correct)

    def _on_predict(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "输入错误", "请输入名字")
            return

        self.current_name = name
        self.predict_btn.setEnabled(False)
        self.status_label.setText("正在预测...")
        self.result_list.clear()
        self.cache_label.clear()
        self.correct_btn.setEnabled(False)

        # 先检查缓存（用况4）
        cache_result = self.db_manager.check_cache(name)
        if cache_result:
            corrected_country, hit_count = cache_result
            self.cache_label.setText(
                f"💡 已命中用户纠正缓存: {corrected_country} (命中{hit_count}次)"
            )

        # 启动后台预测线程
        self.predictor_thread.predict_single(name)

    def _on_result_ready(self, name: str, results: list):
        """接收预测结果 - 美化版"""
        from utils.flags import get_flag  # 局部导入避免循环

        self.current_results = results
        self.predict_btn.setEnabled(True)
        self.status_label.setText(f"预测完成: {name}")

        # 保存到数据库
        if results:
            top_country, top_prob = results[0]
            self.db_manager.save_prediction(name, top_country, float(top_prob))

        # 清空旧结果，使用富文本展示
        self.result_list.clear()

        for idx, (country, prob) in enumerate(results):
            flag = get_flag(country)

            # 创建自定义展示项
            if idx == 0:
                # Top-1 特殊展示（大号字体）
                item_text = f"{flag} {country}\n置信度: {prob * 100:.2f}%"
                item = QListWidgetItem(item_text)
                item.setFont(
                    QtGui.QFont("Microsoft YaHei", 12, QtGui.QFont.Weight.Bold)
                )

                # 根据置信度设置背景色
                if prob >= 0.8:
                    item.setBackground(QtGui.QColor("#E8F5E9"))  # 浅绿
                    item.setForeground(QtGui.QColor("#2E7D32"))  # 深绿
                elif prob >= 0.5:
                    item.setBackground(QtGui.QColor("#FFF3E0"))  # 浅橙
                    item.setForeground(QtGui.QColor("#EF6C00"))  # 深橙
                else:
                    item.setBackground(QtGui.QColor("#FFEBEE"))  # 浅红
                    item.setForeground(QtGui.QColor("#C62828"))  # 深红

            else:
                # Top-2,3 普通展示
                item_text = f"{flag} {country:<12} {prob * 100:>6.2f}%"
                item = QListWidgetItem(item_text)
                item.setFont(QtGui.QFont("Microsoft YaHei", 10))

            self.result_list.addItem(item)
            self.result_list.setSpacing(5)  # 增加行间距

        self.correct_btn.setEnabled(True)

    def _on_error(self, msg: str):
        QMessageBox.critical(self, "错误", msg)
        self.predict_btn.setEnabled(True)
        self.status_label.setText("预测失败")

    def _on_correct(self):
        """用户纠正（用况4）"""
        # 弹出简单选择框（Day 2完善为下拉框）

        countries = [
            "American",
            "Arabic",
            "British",
            "Chinese",
            "Dutch",
            "French",
            "German",
            "Indian",
            "Italian",
            "Japanese",
            "Korean",
            "Polish",
            "Portuguese",
            "Russian",
            "Spanish",
            "Vietnamese",
        ]

        country, ok = QInputDialog.getItem(
            self, "纠正结果", "请选择正确的国籍:", countries, 0, False
        )

        if ok and country:
            # 保存到缓存
            self.db_manager.save_correction(self.current_name, country)

            # 更新界面提示
            self.cache_label.setText(f"✅ 已纠正并缓存: {country}")
            self.cache_label.setStyleSheet("color: #FF5722; font-weight: bold;")

            QMessageBox.information(
                self,
                "纠正成功",
                f"已将 '{self.current_name}' 纠正为 '{country}'\n下次输入将优先显示此结果",
            )
