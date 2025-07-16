from flask import Flask, request, render_template, jsonify, send_from_directory, flash, redirect, url_for
import os
import uuid
from werkzeug.utils import secure_filename
import mimetypes
import json
import pandas as pd
from datetime import datetime
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # 실제 운영시에는 안전한 키로 변경

# 업로드 설정
UPLOAD_FOLDER = 'uploads'
EXCEL_FOLDER = 'excel_outputs'  # 엑셀 출력 폴더 추가
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'txt', 'doc', 'docx'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['EXCEL_FOLDER'] = EXCEL_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# 업로드 폴더와 엑셀 출력 폴더 생성
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(EXCEL_FOLDER):
    os.makedirs(EXCEL_FOLDER)

def allowed_file(filename):
    """허용된 파일 확장자인지 확인"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    """파일 타입 확인"""
    ext = filename.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        return 'PDF'
    elif ext in ['png', 'jpg', 'jpeg', 'gif']:
        return '이미지'
    elif ext in ['txt']:
        return '텍스트'
    elif ext in ['doc', 'docx']:
        return 'Word 문서'
    else:
        return '기타'

def run_async_analysis(analyzer, file_path, custom_prompt):
    """비동기 분석을 동기 컨텍스트에서 실행하는 헬퍼 함수"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(analyzer.analyze_document_async(file_path, custom_prompt))
    finally:
        loop.close()

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """파일 업로드 처리"""
    if 'file' not in request.files:
        flash('파일이 선택되지 않았습니다.')
        return redirect(url_for('index'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('파일이 선택되지 않았습니다.')
        return redirect(url_for('index'))
    
    if file and allowed_file(file.filename):
        # 원본 파일명 유지 (안전성 검사만)
        original_filename = file.filename or "unknown_file"
        # 중복 방지를 위한 고유 파일명 생성
        unique_filename = str(uuid.uuid4()) + '_' + original_filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        try:
            file.save(file_path)
            file_size = os.path.getsize(file_path)
            file_type = get_file_type(original_filename)
            
            # 업로드 성공 메시지
            flash(f'파일 업로드 성공: {original_filename} ({file_type}, {file_size:,} bytes)')
            
            # 추후 AI 분석을 위한 파일 정보 저장
            file_info = {
                'original_name': original_filename,
                'stored_name': unique_filename,
                'file_type': file_type,
                'file_size': file_size,
                'file_path': file_path
            }
            
            return render_template('upload_success.html', file_info=file_info)
            
        except Exception as e:
            flash(f'파일 업로드 중 오류가 발생했습니다: {str(e)}')
            return redirect(url_for('index'))
    
    else:
        flash('허용되지 않는 파일 형식입니다. PDF, 이미지, 텍스트, Word 문서만 업로드 가능합니다.')
        return redirect(url_for('index'))

@app.route('/files')
def list_files():
    """업로드된 파일 목록 조회"""
    files = []
    if os.path.exists(UPLOAD_FOLDER):
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(file_path):
                # 원본 파일명 추출 (UUID 제거)
                original_name = filename.split('_', 1)[1] if '_' in filename else filename
                file_size = os.path.getsize(file_path)
                file_type = get_file_type(original_name)
                
                files.append({
                    'stored_name': filename,
                    'original_name': original_name,
                    'file_type': file_type,
                    'file_size': file_size
                })
    
    return render_template('file_list.html', files=files)

@app.route('/download/<filename>')
def download_file(filename):
    """파일 다운로드"""
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except Exception as e:
        flash(f'파일 다운로드 중 오류가 발생했습니다: {str(e)}')
        return redirect(url_for('list_files'))

@app.route('/api/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """파일 삭제 API"""
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': '파일을 찾을 수 없습니다.'})
        
        # 파일 삭제
        os.remove(file_path)
        
        return jsonify({'success': True, 'message': '파일이 삭제되었습니다.'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'파일 삭제 중 오류 발생: {str(e)}'})

@app.route('/analyze')
def analyze_page():
    """AI 분석 페이지"""
    from ai_analyzer import AIAnalyzer
    analyzer = AIAnalyzer()
    files = analyzer.get_available_files()
    return render_template('analyze.html', files=files)

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """AI 분석 API 엔드포인트 (기본적으로 비동기식)"""
    try:
        from ai_analyzer import AIAnalyzer
        
        data = request.get_json()
        file_name = data.get('file_name')
        custom_prompt = data.get('custom_prompt')
        use_async = data.get('use_async', True)  # 기본값을 True로 변경
        
        if not file_name:
            return jsonify({'success': False, 'error': '파일명이 필요합니다.'})
        
        # 파일 경로 찾기
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': '파일을 찾을 수 없습니다.'})
        
        # AI 분석 수행
        analyzer = AIAnalyzer()
        
        if use_async:
            # 비동기 분석 수행 (기본값)
            print("비동기 분석을 시작합니다...")
            result = run_async_analysis(analyzer, file_path, custom_prompt)
        else:
            # 동기 분석 수행 (선택적)
            print("동기 분석을 시작합니다...")
            result = analyzer.analyze_document(file_path, custom_prompt=custom_prompt)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'분석 중 오류 발생: {str(e)}'})

@app.route('/api/analyze-async', methods=['POST'])
def api_analyze_async():
    """AI 분석 API 엔드포인트 (비동기식)"""
    try:
        from ai_analyzer import AIAnalyzer
        
        data = request.get_json()
        file_name = data.get('file_name')
        custom_prompt = data.get('custom_prompt')
        
        if not file_name:
            return jsonify({'success': False, 'error': '파일명이 필요합니다.'})
        
        # 파일 경로 찾기
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': '파일을 찾을 수 없습니다.'})
        
        # 비동기 분석 수행
        analyzer = AIAnalyzer()
        print("비동기 분석을 시작합니다...")
        
        # 별도 스레드에서 비동기 분석 실행
        def run_analysis():
            return run_async_analysis(analyzer, file_path, custom_prompt)
        
        # 스레드 풀을 사용하여 비동기 실행
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_analysis)
            result = future.result(timeout=300)  # 5분 타임아웃
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'비동기 분석 중 오류 발생: {str(e)}'})

@app.route('/api/files')
def api_files():
    """업로드된 파일 목록 API"""
    files = []
    if os.path.exists(UPLOAD_FOLDER):
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(file_path):
                # 원본 파일명 추출 (UUID 제거)
                original_name = filename.split('_', 1)[1] if '_' in filename else filename
                file_size = os.path.getsize(file_path)
                file_type = get_file_type(original_name)
                
                files.append({
                    'stored_name': filename,
                    'original_name': original_name,
                    'file_type': file_type,
                    'file_size': file_size
                })
    
    return jsonify(files)

@app.route('/settings')
def settings_page():
    """설정 페이지"""
    return render_template('settings.html')

@app.route('/api/set-key', methods=['POST'])
def set_api_key():
    """API 키 설정"""
    try:
        data = request.get_json()
        api_key = data.get('api_key')
        
        if not api_key:
            return jsonify({'success': False, 'error': 'API 키가 필요합니다.'})
        
        # 환경 변수로 설정 (세션 동안만 유지)
        os.environ['OPENAI_API_KEY'] = api_key
        
        return jsonify({'success': True, 'message': 'API 키가 설정되었습니다.'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'API 키 설정 중 오류 발생: {str(e)}'})

def json_to_excel(json_data, original_filename):
    """JSON 분석 결과를 엑셀 파일로 변환"""
    try:
        # JSON 파싱
        if isinstance(json_data, str):
            try:
                data = json.loads(json_data)
            except json.JSONDecodeError as e:
                # JSON 파싱 실패시 텍스트로 처리
                data = {"분석결과": [{"내용": json_data}]}
        else:
            data = json_data
        
        # 엑셀 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(original_filename)[0]
        excel_filename = f"{base_name}_분석결과_{timestamp}.xlsx"
        excel_path = os.path.join(app.config['EXCEL_FOLDER'], excel_filename)
        
        # ExcelWriter 객체 생성
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # 각 문서 유형별로 시트 생성
            for doc_type, documents in data.items():
                try:
                    if isinstance(documents, list) and documents:
                        # 문서 리스트를 DataFrame으로 변환
                        df_data = []
                        for doc in documents:
                            if isinstance(doc, dict):
                                row = {}
                                for key, value in doc.items():
                                    if key != 'document_index':
                                        # 값이 리스트나 딕셔너리인 경우 문자열로 변환
                                        if isinstance(value, (list, dict)):
                                            row[key] = json.dumps(value, ensure_ascii=False)
                                        else:
                                            row[key] = str(value) if value is not None else ""
                                df_data.append(row)
                        
                        if df_data:
                            df = pd.DataFrame(df_data)
                            # 시트명에서 특수문자 제거 (Excel 제한)
                            sheet_name = doc_type[:31]  # Excel 시트명 최대 31자
                            df.to_excel(writer, sheet_name=sheet_name, index=False)
                            
                            # 열 너비 자동 조정
                            worksheet = writer.sheets[sheet_name]
                            for column in worksheet.columns:
                                max_length = 0
                                column_letter = column[0].column_letter
                                for cell in column:
                                    try:
                                        if len(str(cell.value)) > max_length:
                                            max_length = len(str(cell.value))
                                    except:
                                        pass
                                adjusted_width = min(max_length + 2, 50)  # 최대 50자
                                worksheet.column_dimensions[column_letter].width = adjusted_width
                    
                    elif isinstance(documents, dict):
                        # 단일 문서인 경우
                        df_data = []
                        row = {}
                        for key, value in documents.items():
                            if key != 'document_index':
                                # 값이 리스트나 딕셔너리인 경우 문자열로 변환
                                if isinstance(value, (list, dict)):
                                    row[key] = json.dumps(value, ensure_ascii=False)
                                else:
                                    row[key] = str(value) if value is not None else ""
                        df_data.append(row)
                        
                        if df_data:
                            df = pd.DataFrame(df_data)
                            sheet_name = doc_type[:31]
                            df.to_excel(writer, sheet_name=sheet_name, index=False)
                            
                            # 열 너비 자동 조정
                            worksheet = writer.sheets[sheet_name]
                            for column in worksheet.columns:
                                max_length = 0
                                column_letter = column[0].column_letter
                                for cell in column:
                                    try:
                                        if len(str(cell.value)) > max_length:
                                            max_length = len(str(cell.value))
                                    except:
                                        pass
                                adjusted_width = min(max_length + 2, 50)
                                worksheet.column_dimensions[column_letter].width = adjusted_width
                
                except Exception as e:
                    print(f"시트 '{doc_type}' 생성 중 오류: {str(e)}")
                    # 오류 발생시 기본 시트 생성
                    error_df = pd.DataFrame([{"오류": f"시트 생성 실패: {str(e)}"}])
                    sheet_name = f"오류_{doc_type[:25]}"  # 더 짧게
                    error_df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        return excel_filename, excel_path
        
    except Exception as e:
        raise Exception(f"엑셀 변환 중 오류 발생: {str(e)}")

@app.route('/api/export-excel', methods=['POST'])
def export_to_excel():
    """분석 결과를 엑셀 파일로 내보내기"""
    try:
        data = request.get_json()
        json_result = data.get('json_result')
        html_content = data.get('html_content')  # HTML 내용도 받을 수 있도록
        original_filename = data.get('original_filename', 'unknown_file')
        
        if not json_result and not html_content:
            return jsonify({'success': False, 'error': 'JSON 결과 또는 HTML 내용이 필요합니다.'})
        
        print(f"엑셀 변환 시작: {original_filename}")
        
        # JSON 결과가 있는 경우
        if json_result:
            print(f"JSON 결과 타입: {type(json_result)}")
            print(f"JSON 결과 길이: {len(str(json_result))}")
            print(f"JSON 결과 내용 (처음 200자): {str(json_result)[:200]}")
            
            # 빈 문자열이나 None 체크
            if not json_result or json_result.strip() == "":
                print("JSON 결과가 비어있음")
                return jsonify({'success': False, 'error': 'JSON 결과가 비어있습니다.'})
            
            # JSON 데이터가 이미 딕셔너리인 경우 그대로 사용, 문자열인 경우 파싱
            if isinstance(json_result, str):
                try:
                    # 문자열 앞뒤 공백 제거
                    json_result = json_result.strip()
                    if json_result:
                        json_result = json.loads(json_result)
                        print("JSON 문자열 파싱 완료")
                    else:
                        print("JSON 문자열이 비어있음")
                        return jsonify({'success': False, 'error': 'JSON 문자열이 비어있습니다.'})
                except json.JSONDecodeError as e:
                    print(f"JSON 파싱 오류: {e}")
                    print(f"파싱 시도한 문자열: {repr(json_result)}")
                    
                    # JSON 파싱 실패 시 HTML 처리로 전환
                    print("JSON 파싱 실패, HTML 처리로 전환")
                    html_content = json_result  # 원본 문자열을 HTML로 처리
                    json_result = None
            
            if json_result:
                # 엑셀 파일 생성
                excel_filename, excel_path = json_to_excel(json_result, original_filename)
        
        # HTML 내용만 있는 경우 (JSON 파싱 실패한 경우)
        if html_content and not json_result:
            print(f"HTML 내용 처리: {len(html_content)} 문자")
            print(f"HTML 내용 (처음 200자): {html_content[:200]}")
            
            # HTML에서 간단한 구조화된 데이터 추출 시도
            try:
                # HTML에서 테이블 데이터를 추출하여 간단한 JSON 구조 생성
                import re
                
                # 문서 유형 추출
                doc_types = re.findall(r'📄 ([^(]+) \((\d+)개\)', html_content)
                
                if doc_types:
                    # 간단한 구조화된 데이터 생성
                    structured_data = {}
                    for doc_type, count in doc_types:
                        structured_data[doc_type] = [{"내용": f"{doc_type} 문서 {i+1}"} for i in range(int(count))]
                    
                    excel_filename, excel_path = json_to_excel(structured_data, original_filename)
                else:
                    # 문서 유형을 찾을 수 없는 경우 기본 구조로 엑셀 생성
                    basic_data = {"분석결과": [{"내용": html_content[:1000] + "..."}]}
                    excel_filename, excel_path = json_to_excel(basic_data, original_filename)
                
            except Exception as e:
                print(f"HTML 처리 오류: {e}")
                # 기본 구조로 엑셀 생성
                basic_data = {"분석결과": [{"내용": html_content[:1000] + "..."}]}
                excel_filename, excel_path = json_to_excel(basic_data, original_filename)
        
        print(f"엑셀 파일 생성 완료: {excel_filename}")
        print(f"파일 경로: {excel_path}")
        print(f"파일 존재 여부: {os.path.exists(excel_path)}")
        
        return jsonify({
            'success': True,
            'excel_filename': excel_filename,
            'message': '엑셀 파일이 생성되었습니다.'
        })
        
    except Exception as e:
        print(f"엑셀 내보내기 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'엑셀 내보내기 중 오류 발생: {str(e)}'})

@app.route('/download-excel/<filename>')
def download_excel(filename):
    """생성된 엑셀 파일 다운로드"""
    try:
        return send_from_directory(app.config['EXCEL_FOLDER'], filename, as_attachment=True)
    except Exception as e:
        flash(f'엑셀 파일 다운로드 중 오류가 발생했습니다: {str(e)}')
        return redirect(url_for('analyze_page'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 