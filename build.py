import PyInstaller.__main__
import os
import shutil
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# 清理
if os.path.exists("dist"):
    shutil.rmtree("dist")
if os.path.exists("build"):
    shutil.rmtree("build")

# 检查模型路径
model_path = os.path.join(script_dir, "model", "best_name_classifier.pth")
if not os.path.exists(model_path):
    print(f"错误：找不到模型: {model_path}")
    sys.exit(1)

print(f"工作目录: {script_dir}")
print(f"模型路径: {model_path}")

# ========== 关键：排除 PySide6，强制使用 PyQt6 ==========
params = [
    "main.py",
    "--onefile",
    "--windowed",
    "--name=NamePredictor_v1.0",
    f"--add-data={model_path};model",
    "--exclude-module=PySide6",  # 排除 PySide6
    "--exclude-module=shiboken6",  # 排除其依赖
    "--hidden-import=sqlite3",
    "--hidden-import=torch",
    "--hidden-import=numpy",
    "--hidden-import=PyQt6.sip",
    "--clean",
    "--noconfirm",
]

PyInstaller.__main__.run(params)
print("✅ 打包完成！exe 在 dist/NamePredictor_v1.0.exe")
