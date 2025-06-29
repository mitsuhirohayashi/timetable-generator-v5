#!/bin/bash
# 時間割編集サーバー起動スクリプト（ダブルクリック用）

cd "$(dirname "$0")"
echo "時間割編集サーバーを起動しています..."
echo ""
echo "ブラウザで http://127.0.0.1:5000 にアクセスしてください"
echo ""
echo "終了するには、このウィンドウを閉じるか Ctrl+C を押してください"
echo ""
python3 app.py