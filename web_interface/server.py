from flask import Flask, request, jsonify, send_from_directory, render_template_string
from flask_cors import CORS
import os
import sys
import subprocess
import tempfile
import csv

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# プロジェクトのルートディレクトリ
PROJECT_ROOT = '/Users/hayashimitsuhiro/Desktop/timetable_v5'
INPUT_DIR = os.path.join(PROJECT_ROOT, 'data', 'input')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'data', 'output')

@app.route('/')
def index():
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "index.html not found", 404

@app.route('/run-timetable', methods=['POST'])
def run_timetable():
    try:
        data = request.get_json()
        input_data = data.get('inputData', '')
        
        if not input_data:
            return jsonify({'success': False, 'error': '入力データがありません'})
        
        # 入力データをinput.csvに保存
        input_path = os.path.join(INPUT_DIR, 'input.csv')
        os.makedirs(INPUT_DIR, exist_ok=True)
        
        with open(input_path, 'w', encoding='utf-8', newline='') as f:
            f.write(input_data)
        
        # 時間割作成プログラムを実行
        # ここでは、時間割作成プログラムのメインスクリプトを実行します
        # 実際のプログラムのパスに合わせて調整してください
        timetable_script = os.path.join(PROJECT_ROOT, 'main.py')
        
        if not os.path.exists(timetable_script):
            # main.pyが存在しない場合は、別のスクリプト名を試す
            possible_scripts = ['timetable.py', 'run.py', 'generate_timetable.py']
            for script in possible_scripts:
                script_path = os.path.join(PROJECT_ROOT, script)
                if os.path.exists(script_path):
                    timetable_script = script_path
                    break
            else:
                return jsonify({
                    'success': False, 
                    'error': '時間割作成プログラムが見つかりません。プログラムのパスを確認してください。'
                })
        
        # Pythonスクリプトを実行
        result = subprocess.run(
            [sys.executable, timetable_script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.returncode != 0:
            error_message = result.stderr if result.stderr else '時間割作成プログラムの実行に失敗しました'
            return jsonify({'success': False, 'error': error_message})
        
        # 出力ファイルを読み込む
        output_path = os.path.join(OUTPUT_DIR, 'output.csv')
        
        if not os.path.exists(output_path):
            return jsonify({'success': False, 'error': '出力ファイルが生成されませんでした'})
        
        with open(output_path, 'r', encoding='utf-8') as f:
            output_data = f.read()
        
        return jsonify({
            'success': True,
            'outputData': output_data,
            'message': '時間割作成が完了しました'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    # ディレクトリが存在することを確認
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"サーバーが起動しました。")
    print(f"ブラウザで http://localhost:5000 にアクセスしてください。")
    print(f"")
    print(f"プロジェクトルート: {PROJECT_ROOT}")
    print(f"入力ディレクトリ: {INPUT_DIR}")
    print(f"出力ディレクトリ: {OUTPUT_DIR}")
    
    app.run(debug=True, host='127.0.0.1', port=5000)