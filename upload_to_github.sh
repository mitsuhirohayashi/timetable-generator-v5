#!/bin/bash

# GitHubにプロジェクトをアップロードするスクリプト

echo "GitHubへのアップロード手順："
echo "================================"
echo ""
echo "1. GitHubで新しいリポジトリを作成"
echo "   - https://github.com/new にアクセス"
echo "   - リポジトリ名: timetable-generator-v5"
echo "   - Public/Privateを選択"
echo ""
echo "2. ローカルでGitを初期化（既に初期化済みの場合はスキップ）"
echo "   git init"
echo ""
echo "3. リモートリポジトリを追加"
echo "   git remote add origin https://github.com/YOUR_USERNAME/timetable-generator-v5.git"
echo ""
echo "4. ファイルをコミット"
echo "   git add ."
echo "   git commit -m \"Initial commit: School timetable generator v5\""
echo ""
echo "5. GitHubにプッシュ"
echo "   git push -u origin main"
echo ""
echo "6. ClaudeにGitHubのURLを共有"
echo "   例: https://github.com/YOUR_USERNAME/timetable-generator-v5"