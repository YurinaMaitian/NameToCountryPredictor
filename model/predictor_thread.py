from PyQt6.QtCore import QThread, pyqtSignal
import sys
import os
import traceback


# ========== 日志系统（与 main.py 共享同一个日志文件）==========
def log(msg):
    try:
        # 尝试多种可能的路径找到日志文件
        if getattr(sys, "frozen", False):
            log_dir = os.path.dirname(sys.executable)
        else:
            log_dir = os.path.abspath(".")

        log_path = os.path.join(log_dir, "debug.log")
        with open(log_path, "a", encoding="utf-8") as f:
            from datetime import datetime

            f.write(f"[{datetime.now()}] [PredictorThread] {msg}\n")
            f.flush()
    except Exception as e:
        print(f"日志写入失败: {e}, 原消息: {msg}")


# ========== 模块级导出 ==========
__all__ = ["PredictorThread", "get_resource_path"]


def get_resource_path(relative_path):
    """获取资源绝对路径（兼容开发、onedir、onefile 三种环境）"""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    elif getattr(sys, "frozen", False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")

    full_path = os.path.join(base_path, relative_path)
    log(f"get_resource_path: {relative_path} -> {full_path}")
    return full_path


class PredictorThread(QThread):
    result_ready = pyqtSignal(str, list)
    error_occurred = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    def __init__(self, model_path=None):
        super().__init__()
        self.predictor = None
        self.model_path = model_path or get_resource_path(
            "model/best_name_classifier.pth"
        )
        self._names = []
        self._is_batch = False
        log(f"PredictorThread 初始化，模型路径: {self.model_path}")

    def initialize(self):
        """初始化模型（带详细日志）"""
        log("开始 initialize()...")
        try:
            # 步骤1：导入 NamePredictor
            log("步骤1: 尝试导入 NamePredictor...")
            try:
                from model.predictor import NamePredictor

                log("从 model.predictor 导入成功")
            except ImportError as e1:
                log(f"从 model.predictor 导入失败: {e1}，尝试 predictor...")
                try:
                    from predictor import NamePredictor

                    log("从 predictor 导入成功")
                except ImportError as e2:
                    log(f"从 predictor 导入也失败: {e2}")
                    raise ImportError(f"无法导入 NamePredictor: 尝试1-{e1}, 尝试2-{e2}")

            # 步骤2：检查模型路径
            log(f"步骤2: 检查模型路径: {self.model_path}")
            if not os.path.exists(self.model_path):
                log(f"模型文件不存在！尝试备选路径...")
                # 备选：当前文件所在目录
                alt_path = os.path.join(
                    os.path.dirname(__file__), "best_name_classifier.pth"
                )
                log(f"备选路径: {alt_path}")
                if os.path.exists(alt_path):
                    self.model_path = alt_path
                    log(f"使用备选路径: {alt_path}")
                else:
                    raise FileNotFoundError(
                        f"模型文件不存在: {self.model_path} 且备选也不存在"
                    )
            else:
                log(f"模型文件存在，大小: {os.path.getsize(self.model_path)} bytes")

            # 步骤3：实例化 NamePredictor（这里最可能出错）
            log("步骤3: 实例化 NamePredictor...")
            try:
                self.predictor = NamePredictor(self.model_path)
                log("NamePredictor 实例化成功")
            except Exception as e:
                log(f"NamePredictor 实例化失败: {str(e)}")
                log(traceback.format_exc())
                raise

            # 步骤4：验证 predictor 可用（尝试一次简单预测）
            log("步骤4: 验证模型可用性...")
            try:
                test_result = self.predictor.guess("test", top_k=1)
                log(f"测试预测成功: {test_result}")
            except Exception as e:
                log(f"测试预测失败: {str(e)}")
                log(traceback.format_exc())
                # 测试失败不阻止初始化，但记录日志

            log("initialize() 成功返回 True")
            return True

        except Exception as e:
            error_msg = f"模型初始化失败: {str(e)}"
            log(error_msg)
            log(traceback.format_exc())
            self.error_occurred.emit(error_msg)
            return False

    def predict_single(self, name: str):
        self._names = [name]
        self._is_batch = False
        self.start()

    def predict_batch(self, names: list):
        self._names = names
        self._is_batch = True
        self.start()

    def run(self):
        if not self.predictor:
            self.error_occurred.emit("预测器未初始化")
            return

        try:
            if self._is_batch:
                for idx, name in enumerate(self._names, 1):
                    results = self.predictor.guess(name, top_k=3)
                    self.progress.emit(idx, len(self._names))
                    self.result_ready.emit(name, results)
            else:
                name = self._names[0]
                results = self.predictor.guess(name, top_k=3)
                self.result_ready.emit(name, results)

        except Exception as e:
            error_msg = f"预测错误: {str(e)}"
            log(error_msg)
            log(traceback.format_exc())
            self.error_occurred.emit(error_msg)
