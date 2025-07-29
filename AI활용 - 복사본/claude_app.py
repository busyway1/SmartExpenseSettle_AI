#!/usr/bin/env python3
"""
Claude AI 분석기를 사용하는 Flask 웹 애플리케이션
"""

import os
import sys
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename

# 현재 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from claude_analyzer.claude_ai_analyzer import ClaudeAIAnalyzer

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB 제한
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['EXCEL_OUTPUT_FOLDER'] = 'excel_outputs'

# 업로드 폴더 생성
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['EXCEL_OUTPUT_FOLDER'], exist_ok=True)

# 허용된 파일 확장자
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'gif', 'txt', 'md'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('claude_index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """파일 업로드 및 분석"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '파일이 선택되지 않았습니다.'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '파일이 선택되지 않았습니다.'}), 400
        
        if file and allowed_file(file.filename):
            # 파일명 보안 처리
            filename = secure_filename(file.filename)
            
            # 고유한 파일명 생성
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            
            # 파일 저장
            file.save(file_path)
            
            # Claude 분석기 초기화 (고품질 이미지 전처리 활성화, 속도 제한 비활성화)
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                return jsonify({'error': 'ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.'}), 500
            analyzer = ClaudeAIAnalyzer(api_key=api_key, use_advanced_opencv=True, enable_rate_limit=False)
            
            # 문서 분석
            result = analyzer.analyze_document(file_path)
            
            if result.get('success'):
                # 결과를 JSON 파일로 저장
                output_filename = f"{uuid.uuid4()}_{os.path.splitext(filename)[0]}_분석결과_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                output_path = os.path.join(app.config['EXCEL_OUTPUT_FOLDER'], output_filename)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                # analysis 필드가 문자열인지 확인하고 디버깅 정보 추가
                analysis_text = result.get('analysis', '')
                print(f"DEBUG: analysis 타입: {type(analysis_text)}")
                print(f"DEBUG: analysis 길이: {len(str(analysis_text))}")
                print(f"DEBUG: analysis 시작 부분: {str(analysis_text)[:100]}...")
                
                return jsonify({
                    'success': True,
                    'message': '분석이 완료되었습니다.',
                    'filename': filename,
                    'result': result,
                    'output_file': output_filename
                })
            else:
                return jsonify({
                    'success': False,
                    'error': result.get('error', '분석 중 오류가 발생했습니다.')
                }), 500
        else:
            return jsonify({'error': '지원하지 않는 파일 형식입니다.'}), 400
            
    except Exception as e:
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

@app.route('/files')
def list_files():
    """업로드된 파일 목록"""
    try:
        files = []
        upload_folder = app.config['UPLOAD_FOLDER']
        
        if os.path.exists(upload_folder):
            for filename in os.listdir(upload_folder):
                if allowed_file(filename):
                    file_path = os.path.join(upload_folder, filename)
                    file_stat = os.stat(file_path)
                    files.append({
                        'name': filename,
                        'size': file_stat.st_size,
                        'uploaded': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    })
        
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': f'파일 목록 조회 오류: {str(e)}'}), 500

@app.route('/analyze/<filename>')
def analyze_file(filename):
    """기존 파일 분석"""
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': '파일을 찾을 수 없습니다.'}), 404
        
        # Claude 분석기 초기화 (고품질 이미지 전처리 활성화, 속도 제한 비활성화)
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            return jsonify({'error': 'ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.'}), 500
        analyzer = ClaudeAIAnalyzer(api_key=api_key, use_advanced_opencv=True, enable_rate_limit=False)
        
        # 문서 분석
        result = analyzer.analyze_document(file_path)
        
        if result.get('success'):
            # 결과를 JSON 파일로 저장
            output_filename = f"{uuid.uuid4()}_{os.path.splitext(filename)[0]}_분석결과_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            output_path = os.path.join(app.config['EXCEL_OUTPUT_FOLDER'], output_filename)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            return jsonify({
                'success': True,
                'message': '분석이 완료되었습니다.',
                'filename': filename,
                'result': result,
                'output_file': output_filename
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '분석 중 오류가 발생했습니다.')
            }), 500
            
    except Exception as e:
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """분석 결과 파일 다운로드"""
    try:
        return send_from_directory(app.config['EXCEL_OUTPUT_FOLDER'], filename, as_attachment=True)
    except Exception as e:
        return jsonify({'error': f'파일 다운로드 오류: {str(e)}'}), 500

if __name__ == '__main__':
    print("🚀 Claude AI 분석기 웹 서버 시작...")
    print("📱 브라우저에서 http://localhost:5001 접속")
    app.run(host='0.0.0.0', port=5001, debug=True) 