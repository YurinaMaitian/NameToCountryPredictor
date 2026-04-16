from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QProgressBar,
    QFileDialog,
    QMessageBox,
    QHeaderView,
    QAbstractItemView,
    QTextEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import csv
import os
from typing import List, Tuple


class BatchPredictWorker(QThread):
    """批量预测后台线程，防止处理大文件时UI卡死"""

    progress = pyqtSignal(int, int)  # 当前进度，总数
    item_ready = pyqtSignal(str, list)  # 名字，预测结果
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, predictor_thread, names: List[str]):
        super().__init__()
        self.predictor_thread = predictor_thread
        self.names = names
        self._is_running = True

    def run(self):
        try:
            for idx, name in enumerate(self.names, 1):
                if not self._is_running:
                    break

                # 调用模型预测（同步调用，但在线程中不阻塞UI）
                # 注意：这里我们直接使用predictor，避免递归线程问题
                results = self.predictor_thread.predictor.guess(name, top_k=3)
                self.item_ready.emit(name, results)
                self.progress.emit(idx, len(self.names))

            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._is_running = False


class BatchTab(QWidget):
    """
    批量文件预测（用况2）
    支持上传CSV/TXT，批量预测，导出结果
    """

    batch_finished = pyqtSignal()  # 批量预测完成信号
    batch_progress = pyqtSignal(int, int)  # 进度信号（可选）

    def __init__(self, predictor_thread, db_manager, parent=None):
        super().__init__(parent)
        self.predictor_thread = predictor_thread
        self.db_manager = db_manager
        self.current_results = []  # 存储批量结果用于导出
        self.worker = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 文件选择区域
        file_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("选择包含英文名字的CSV或TXT文件...")
        self.file_path_edit.setReadOnly(True)

        self.browse_btn = QPushButton("📁 浏览...")
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        self.browse_btn.clicked.connect(self._browse_file)

        file_layout.addWidget(self.file_path_edit, stretch=4)
        file_layout.addWidget(self.browse_btn, stretch=1)
        layout.addLayout(file_layout)

        # 格式说明
        hint_label = QLabel(
            "💡 支持格式：CSV文件（单列名字，有无表头均可）或TXT文件（每行一个名字）"
        )
        hint_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(hint_label)

        # 进度条（初始隐藏）
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #2196F3;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
            }
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # 操作按钮区域
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ 开始批量预测")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.start_btn.clicked.connect(self._start_batch)
        self.start_btn.setEnabled(False)  # 未选文件前禁用

        self.export_btn = QPushButton("💾 导出结果")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border-radius: 4px;
                padding: 8px 20px;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        self.export_btn.clicked.connect(self._export_results)
        self.export_btn.setEnabled(False)  # 无结果前禁用

        self.clear_btn = QPushButton("🗑 清空")
        self.clear_btn.clicked.connect(self._clear_all)

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.export_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.clear_btn)
        layout.addLayout(btn_layout)

        # 结果显示表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["序号", "名字", "Top-1预测", "置信度", "Top-2备选"]
        )

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(3, 80)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)

        # 状态栏
        self.status_label = QLabel("就绪 - 请选择文件")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)

    def _browse_file(self):
        """选择文件对话框"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择名字列表文件",
            "",
            "CSV文件 (*.csv);;文本文件 (*.txt);;所有文件 (*.*)",
        )

        if file_path:
            self.file_path_edit.setText(file_path)
            self.start_btn.setEnabled(True)
            self.status_label.setText(f"已选择: {file_path}")

    def _parse_file(self, file_path: str) -> List[str]:
        """解析CSV或TXT文件，返回名字列表"""
        names = []
        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext == ".csv":
                with open(
                    file_path, "r", encoding="utf-8-sig"
                ) as f:  # utf-8-sig处理BOM
                    # 尝试检测是否有表头
                    sample = f.read(1024)
                    f.seek(0)

                    sniffer = csv.Sniffer()
                    try:
                        has_header = sniffer.has_header(sample)
                    except:
                        has_header = False

                    reader = csv.reader(f)
                    if has_header:
                        next(reader)  # 跳过表头

                    for row in reader:
                        if row and row[0].strip():  # 取第一列非空值
                            names.append(row[0].strip())

            elif ext == ".txt":
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        name = line.strip()
                        if name:
                            names.append(name)
            else:
                raise ValueError(f"不支持的文件格式: {ext}")

        except Exception as e:
            raise ValueError(f"文件解析失败: {str(e)}")

        return names

    def _start_batch(self):
        """开始批量预测"""
        file_path = self.file_path_edit.text()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "错误", "请首先选择有效的文件")
            return

        try:
            names = self._parse_file(file_path)
            if not names:
                QMessageBox.warning(self, "错误", "文件中没有解析到有效的名字")
                return

            if len(names) > 10000:
                reply = QMessageBox.question(
                    self,
                    "确认",
                    f"文件包含 {len(names)} 条记录，预测可能需要较长时间，是否继续？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            # 准备开始
            self.current_results = []
            self.table.setRowCount(0)
            self.progress_bar.setMaximum(len(names))
            self.progress_bar.setValue(0)
            self.progress_bar.show()
            self.start_btn.setEnabled(False)
            self.export_btn.setEnabled(False)
            self.browse_btn.setEnabled(False)
            self.status_label.setText(f"正在处理 0/{len(names)}...")

            # 启动后台线程
            self.worker = BatchPredictWorker(self.predictor_thread, names)
            self.worker.progress.connect(self._update_progress)
            self.worker.item_ready.connect(self._add_result_item)
            self.worker.finished_signal.connect(self._batch_finished)
            self.worker.error_signal.connect(self._batch_error)
            self.worker.start()

        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def _update_progress(self, current: int, total: int):
        """更新进度条"""
        self.progress_bar.setValue(current)
        self.status_label.setText(f"正在处理 {current}/{total}...")

    def _add_result_item(self, name: str, results: list):
        """添加单条结果到表格"""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # 序号
        self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))

        # 名字
        self.table.setItem(row, 1, QTableWidgetItem(name))

        # Top-1 预测
        if results:
            top_country, top_prob = results[0]
            self.table.setItem(row, 2, QTableWidgetItem(top_country))

            conf_item = QTableWidgetItem(f"{top_prob * 100:.1f}%")
            conf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, conf_item)

            # 保存到数据库（批量标记）
            self.db_manager.save_prediction(
                name, top_country, float(top_prob), source="batch"
            )

            # Top-2 备选（如果有）
            if len(results) > 1:
                second_country = results[1][0]
                self.table.setItem(row, 4, QTableWidgetItem(second_country))
            else:
                self.table.setItem(row, 4, QTableWidgetItem("-"))
        else:
            self.table.setItem(row, 2, QTableWidgetItem("预测失败"))
            self.table.setItem(row, 3, QTableWidgetItem("-"))
            self.table.setItem(row, 4, QTableWidgetItem("-"))

        self.current_results.append({"name": name, "results": results})

    def _batch_finished(self):
        """批量处理完成"""
        self.progress_bar.hide()
        self.start_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.status_label.setText(f"完成！共处理 {len(self.current_results)} 条记录")
        # 发射信号通知外部（关键）
        self.batch_finished.emit()
        QMessageBox.information(
            self, "完成", f"批量预测完成！共处理 {len(self.current_results)} 条记录"
        )

    def _batch_error(self, error_msg: str):
        """处理错误"""
        self.progress_bar.hide()
        self.start_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        QMessageBox.critical(self, "预测错误", error_msg)

    def _export_results(self):
        """导出结果到CSV"""
        if not self.current_results:
            QMessageBox.warning(self, "错误", "没有可导出的结果")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出预测结果", "batch_prediction_result.csv", "CSV文件 (*.csv)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "Name",
                        "Top1_Country",
                        "Top1_Confidence",
                        "Top2_Country",
                        "Top2_Confidence",
                        "Top3_Country",
                        "Top3_Confidence",
                    ]
                )

                for item in self.current_results:
                    name = item["name"]
                    results = item["results"]

                    row = [name]
                    for i in range(3):
                        if i < len(results):
                            country, conf = results[i]
                            row.extend([country, f"{conf:.4f}"])
                        else:
                            row.extend(["", ""])

                    writer.writerow(row)

            QMessageBox.information(self, "导出成功", f"结果已保存到:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _clear_all(self):
        """清空当前结果"""
        self.table.setRowCount(0)
        self.current_results = []
        self.file_path_edit.clear()
        self.start_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.status_label.setText("就绪 - 请选择文件")
