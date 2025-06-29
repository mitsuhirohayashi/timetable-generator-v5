#!/bin/bash
# 時間割編集サーバー起動スクリプト

echo "時間割編集サーバーを起動しています..."
cd "$(dirname "$0")"
python3 app.py