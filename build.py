import PyInstaller.__main__
import os
import shutil

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# 清理
if os.path.exists("dist"):
    shutil.rmtree("dist")
if os.path.exists("build"):
    shutil.rmtree("build")

print("使用 onedir 模式打包（文件夹形式，手动放置模型）...")

params = [
    "main.py",
    "--onedir",
    "--windowed",
    "--name=NamePredictor_v1.0",
    "--exclude-module=PySide6",
    "--exclude-module=shiboken6",
    "--hidden-import=sqlite3",
    "--hidden-import=torch",
    "--hidden-import=numpy",
    "--hidden-import=PyQt6.sip",
    "--hidden-import=predictor",
    "--clean",
    "--noconfirm",
]

PyInstaller.__main__.run(params)

# ========== 打包后手动复制模型文件 ==========
print("复制模型文件到输出目录...")
dist_model_dir = os.path.join("dist", "NamePredictor_v1.0", "model")
os.makedirs(dist_model_dir, exist_ok=True)

import shutil

shutil.copy(
    os.path.join("model", "best_name_classifier.pth"),
    os.path.join(dist_model_dir, "best_name_classifier.pth"),
)
print(f"模型已复制到: {dist_model_dir}")

print("✅ 打包完成！")
print(f"位置: {os.path.abspath('dist/NamePredictor_v1.0/')}")
print("请进入该目录双击 exe 测试，查看 debug.log 了解启动详情")
