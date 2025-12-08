# -*- coding: utf-8 -*-
"""
가상환경 설정 검증 스크립트
이 스크립트는 가상환경이 올바르게 설정되어 있는지 확인합니다.
"""

import sys
import os
import subprocess

def check_virtual_environment():
    """가상환경 사용 여부 확인"""
    print("=" * 60)
    print("가상환경 설정 검증")
    print("=" * 60)
    
    # Python 실행 파일 경로
    python_exe = sys.executable
    print(f"\n✓ Python 실행 파일: {python_exe}")
    print(f"✓ Python 버전: {sys.version}")
    
    # 가상환경 확인
    is_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    if is_venv:
        print(f"\n✅ 가상환경에서 실행 중")
        print(f"   - 가상환경 경로: {sys.prefix}")
        print(f"   - 기본 Python: {sys.base_prefix}")
    else:
        print(f"\n⚠️  시스템 Python 사용 중 (가상환경 아님)")
        print(f"   - Python 경로: {sys.prefix}")
        return False
    
    # requirements.txt 확인
    requirements_file = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    if not os.path.exists(requirements_file):
        print(f"\n⚠️  requirements.txt를 찾을 수 없습니다")
        return False
    
    print(f"\n✓ requirements.txt 확인됨")
    
    # 필수 패키지 확인
    print(f"\n필수 패키지 확인 중...")
    required_packages = [
        'flask',
        'flask_cors',
        'chardet',
        'docx',
        'pptx',
        'fitz',  # PyMuPDF
        'openpyxl',
        'win32com.client',  # pywin32
        'olefile',
        'pynput'  # 새로 추가된 패키지
    ]
    
    missing_packages = []
    installed_packages = []
    
    for package in required_packages:
        try:
            if package == 'fitz':
                __import__('fitz')
                package_name = 'PyMuPDF (fitz)'
            elif package == 'docx':
                __import__('docx')
                package_name = 'python-docx'
            elif package == 'pptx':
                __import__('pptx')
                package_name = 'python-pptx'
            else:
                __import__(package)
                package_name = package
            
            print(f"   ✓ {package_name}")
            installed_packages.append(package_name)
        except ImportError:
            print(f"   ✗ {package} (설치 필요)")
            missing_packages.append(package)
    
    # 결과 출력
    print(f"\n" + "=" * 60)
    print(f"검증 결과")
    print("=" * 60)
    print(f"✓ 설치됨: {len(installed_packages)}개")
    print(f"✗ 누락됨: {len(missing_packages)}개")
    
    if missing_packages:
        print(f"\n⚠️  누락된 패키지를 설치하려면:")
        print(f"   cd python-backend")
        print(f"   .\\venv\\Scripts\\activate")
        print(f"   pip install -r requirements.txt")
        return False
    else:
        print(f"\n✅ 모든 패키지가 올바르게 설치되었습니다!")
        return True

if __name__ == "__main__":
    success = check_virtual_environment()
    sys.exit(0 if success else 1)

