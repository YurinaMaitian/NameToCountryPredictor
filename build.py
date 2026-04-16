# build.py - 一键打包脚本
import PyInstaller.__main__
import os
import shutil

# 清理旧构建
if os.path.exists("dist"):
    shutil.rmtree("dist")
if os.path.exists("build"):
    shutil.rmtree("build")

# PyInstaller 参数
# --onefile: 单文件exe（方便提交作业）
# --windowed: 不显示控制台窗口
# --add-data: 将模型文件打包进exe（格式：源路径;目标路径）
params = [
    "main.py",  # 入口文件
    "--onefile",  # 单文件模式（如需快速启动可改为 --onedir）
    "--windowed",
    "--name=NamePredictor_v1.0",
    "--icon=resources/icon.ico",  # 如有图标文件，否则删除此行
    "--add-data=model/best_name_classifier.pth;model",  # 打包模型
    "--add-data=resources;resources",  # 打包资源目录
    "--hidden-import=sqlite3",
    "--hidden-import=torch",
    "--hidden-import=numpy",
    "--clean",
    "--noconfirm",
]

print("开始打包...")
PyInstaller.__main__.run(params)
print("打包完成！exe 位于 dist/NamePredictor_v1.0.exe")
