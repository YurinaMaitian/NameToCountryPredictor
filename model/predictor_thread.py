from PyQt6.QtCore import QThread, pyqtSignal
from typing import List, Tuple
import sys
import os

# 添加父目录到路径以导入predictor
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from predictor import NamePredictor


def get_resource_path(relative_path):
    """获取资源绝对路径（兼容开发环境和PyInstaller打包后）"""
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller 打包后的临时目录
        base_path = sys._MEIPASS
    else:
        # 正常开发环境
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# 使用时：
model_path = get_resource_path("model/best_name_classifier.pth")


class PredictorThread(QThread):
    """
    预测工作线程 - 防止模型推理时UI冻结
    信号:
        result_ready: 预测完成 (name, [(country, prob), ...])
        error_occurred: 错误发生 (error_msg)
        progress: 批量预测进度 (current, total)
    """

    result_ready = pyqtSignal(str, list)  # name, [(country, prob), ...]
    error_occurred = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # current, total

    def __init__(self, model_path: str = "model/best_name_classifier.pth"):
        super().__init__()
        self.predictor = None
        self.model_path = model_path
        self._names = []  # 支持批量
        self._is_batch = False

    def initialize(self):
        """在主线程中初始化模型（避免在子线程加载大文件）"""
        try:
            # 使用相对于exe的路径或绝对路径
            if not os.path.exists(self.model_path):
                # 尝试同级目录
                alt_path = os.path.join(
                    os.path.dirname(__file__), "best_name_classifier.pth"
                )
                if os.path.exists(alt_path):
                    self.model_path = alt_path

            self.predictor = NamePredictor(self.model_path)
            return True
        except Exception as e:
            self.error_occurred.emit(f"模型加载失败: {str(e)}")
            return False

    def predict_single(self, name: str):
        """设置单预测模式"""
        self._names = [name]
        self._is_batch = False
        self.start()

    def predict_batch(self, names: List[str]):
        """设置批量预测模式"""
        self._names = names
        self._is_batch = True
        self.start()

    def run(self):
        """线程执行体 - 在后台运行预测"""
        if not self.predictor:
            self.error_occurred.emit("预测器未初始化")
            return

        try:
            if self._is_batch:
                # 批量预测
                for idx, name in enumerate(self._names, 1):
                    results = self.predictor.guess(name, top_k=3)
                    self.progress.emit(idx, len(self._names))
                    # 批量模式每次发射结果，由上层收集
                    self.result_ready.emit(name, results)
            else:
                # 单预测
                name = self._names[0]
                results = self.predictor.guess(name, top_k=3)
                self.result_ready.emit(name, results)

        except Exception as e:
            self.error_occurred.emit(f"预测错误: {str(e)}")
