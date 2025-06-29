#!/usr/bin/env python3
"""
時間割編集用Webサーバー
input.csvとoutput.csvの読み込み・編集・保存機能を提供
"""
from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
import os
import sys
import csv
import json
import shutil
from datetime import datetime

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# プロジェクトのパス設定
PROJECT_ROOT = '/Users/hayashimitsuhiro/Desktop/timetable_v5'
INPUT_PATH = os.path.join(PROJECT_ROOT, 'data', 'input', 'input.csv')
OUTPUT_PATH = os.path.join(PROJECT_ROOT, 'data', 'output', 'output.csv')
BACKUP_DIR = os.path.join(PROJECT_ROOT, 'data', 'backup')

# バックアップディレクトリを作成
os.makedirs(BACKUP_DIR, exist_ok=True)

@app.route('/')
def index():
    """メインページを返す"""
    return send_from_directory('.', 'timetable_editor_server.html')

@app.route('/api/load-input', methods=['GET'])
def load_input():
    """input.csvを読み込んで返す"""
    try:
        if not os.path.exists(INPUT_PATH):
            return jsonify({
                'success': False,
                'error': 'input.csvが見つかりません'
            })
        
        with open(INPUT_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            'success': True,
            'data': content
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/load-output', methods=['GET'])
def load_output():
    """output.csvを読み込んで返す"""
    try:
        if not os.path.exists(OUTPUT_PATH):
            return jsonify({
                'success': False,
                'error': 'output.csvが見つかりません'
            })
        
        with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            'success': True,
            'data': content
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/save-input', methods=['POST'])
def save_input():
    """input.csvを保存する"""
    try:
        data = request.get_json()
        content = data.get('content', '')
        
        if not content:
            return jsonify({
                'success': False,
                'error': '保存するデータがありません'
            })
        
        # バックアップを作成
        if os.path.exists(INPUT_PATH):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(BACKUP_DIR, f'input_{timestamp}.csv')
            shutil.copy2(INPUT_PATH, backup_path)
        
        # 新しいデータを保存
        with open(INPUT_PATH, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        
        return jsonify({
            'success': True,
            'message': 'input.csvを保存しました'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/download-output', methods=['GET'])
def download_output():
    """output.csvをダウンロード用に返す"""
    try:
        if not os.path.exists(OUTPUT_PATH):
            return jsonify({
                'success': False,
                'error': 'output.csvが見つかりません'
            })
        
        with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        response = make_response(content)
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = 'attachment; filename=output.csv'
        return response
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/run-timetable', methods=['POST'])
def run_timetable():
    """時間割生成プログラムを実行する"""
    try:
        import subprocess
        
        # main.pyを実行
        main_script = os.path.join(PROJECT_ROOT, 'main.py')
        
        if not os.path.exists(main_script):
            return jsonify({
                'success': False,
                'error': 'main.pyが見つかりません'
            })
        
        # Pythonスクリプトを実行（デフォルトのstrategyを指定）
        result = subprocess.run(
            [sys.executable, main_script, 'generate', '--strategy', 'ultrathink'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.returncode != 0:
            error_message = result.stderr if result.stderr else '時間割生成に失敗しました'
            return jsonify({
                'success': False,
                'error': error_message
            })
        
        # 生成されたoutput.csvを読み込む
        if os.path.exists(OUTPUT_PATH):
            with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
                output_data = f.read()
            
            return jsonify({
                'success': True,
                'message': '時間割生成が完了しました',
                'outputData': output_data
            })
        else:
            return jsonify({
                'success': False,
                'error': 'output.csvが生成されませんでした'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    print("時間割編集サーバーを起動しています...")
    print(f"プロジェクトルート: {PROJECT_ROOT}")
    print(f"入力ファイル: {INPUT_PATH}")
    print(f"出力ファイル: {OUTPUT_PATH}")
    print("")
    print("ブラウザで http://localhost:5000 にアクセスしてください")
    print("終了するには Ctrl+C を押してください")
    
    app.run(debug=True, host='127.0.0.1', port=5000)