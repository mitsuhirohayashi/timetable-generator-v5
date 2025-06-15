#!/usr/bin/env python3
"""
時間割生成システム メインエントリーポイント
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.presentation.cli.main import main

if __name__ == "__main__":
    main()