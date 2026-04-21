"""
CryptoMind Pro Plus AI - KivyMD 移动端入口
直接使用 mobile/app.py 的类，避免相对导入路径问题
"""
import sys
import os

# 相对导入必须基于当前文件位置
this_dir = os.path.dirname(os.path.abspath(__file__))
project_root = this_dir
sys.path.insert(0, project_root)

from kivy.config import Config
Config.set('kivy', 'log_level', 'warning')

from kivymd.app import MDApp
from mobile.app import CryptoMindApp

if __name__ == '__main__':
    CryptoMindApp().run()
