#!/usr/bin/env python3
"""
シンプルなHTTPサーバーでWebインターフェースを起動する代替スクリプト
"""
import http.server
import socketserver
import os
import json
import subprocess
import sys
from urllib.parse import parse_qs, urlparse

PORT = 8000
PROJECT_ROOT = '/Users/hayashimitsuhiro/Desktop/timetable_v5'
INPUT_DIR = os.path.join(PROJECT_ROOT, 'data', 'input')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'data', 'output')

class TimetableHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/run-timetable':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                input_data = data.get('inputData', '')
                
                if not input_data:
                    self.send_json_response({'success': False, 'error': '入力データがありません'})
                    return
                
                # 入力データをinput.csvに保存
                os.makedirs(INPUT_DIR, exist_ok=True)
                input_path = os.path.join(INPUT_DIR, 'input.csv')
                
                with open(input_path, 'w', encoding='utf-8', newline='') as f:
                    f.write(input_data)
                
                # 時間割作成プログラムを実行
                timetable_script = os.path.join(PROJECT_ROOT, 'main.py')
                
                if not os.path.exists(timetable_script):
                    possible_scripts = ['timetable.py', 'run.py', 'generate_timetable.py']
                    for script in possible_scripts:
                        script_path = os.path.join(PROJECT_ROOT, script)
                        if os.path.exists(script_path):
                            timetable_script = script_path
                            break
                    else:
                        self.send_json_response({
                            'success': False, 
                            'error': '時間割作成プログラムが見つかりません。'
                        })
                        return
                
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
                    self.send_json_response({'success': False, 'error': error_message})
                    return
                
                # 出力ファイルを読み込む
                output_path = os.path.join(OUTPUT_DIR, 'output.csv')
                
                if not os.path.exists(output_path):
                    self.send_json_response({'success': False, 'error': '出力ファイルが生成されませんでした'})
                    return
                
                with open(output_path, 'r', encoding='utf-8') as f:
                    output_data = f.read()
                
                self.send_json_response({
                    'success': True,
                    'outputData': output_data,
                    'message': '時間割作成が完了しました'
                })
                
            except Exception as e:
                self.send_json_response({'success': False, 'error': str(e)})
        else:
            self.send_error(404)
    
    def send_json_response(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # ディレクトリが存在することを確認
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    with socketserver.TCPServer(("", PORT), TimetableHTTPRequestHandler) as httpd:
        print(f"サーバーが起動しました。")
        print(f"ブラウザで http://localhost:{PORT} にアクセスしてください。")
        print(f"")
        print(f"プロジェクトルート: {PROJECT_ROOT}")
        print(f"入力ディレクトリ: {INPUT_DIR}")
        print(f"出力ディレクトリ: {OUTPUT_DIR}")
        print(f"")
        print(f"終了するには Ctrl+C を押してください。")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nサーバーを終了します。")