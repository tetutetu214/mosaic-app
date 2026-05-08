"""pytest 実行時にプロジェクトルートを sys.path 先頭に追加する"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
