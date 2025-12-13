# 🤖 GPT API Key 설정 가이드

Advanced Explorer의 **GPT 요약 기능**을 사용하려면 OpenAI API Key가 필요합니다.

---

## 📋 목차
1. [API Key 발급 방법](#1-api-key-발급-방법)
2. [API Key 설정 방법](#2-api-key-설정-방법)
3. [사용 방법](#3-사용-방법)
4. [비용 안내](#4-비용-안내)
5. [문제 해결](#5-문제-해결)

---

## 1. API Key 발급 방법

### 단계 1: OpenAI 계정 생성
1. **웹사이트 방문**: https://platform.openai.com/signup
2. **회원가입**:
   - 이메일 주소 입력
   - 또는 Google/Microsoft 계정으로 로그인
3. **이메일 인증** 완료

### 단계 2: 결제 수단 등록
1. **대시보드 접속**: https://platform.openai.com/account/billing
2. **"Add payment method"** 클릭
3. **신용카드 정보 입력**
   - 💡 첫 가입 시 $5 무료 크레딧 제공 (3개월 유효)
   - 무료 크레딧으로 수백 번의 요약 가능!

### 단계 3: API Key 생성
1. **API Keys 페이지 이동**: https://platform.openai.com/api-keys
2. **"Create new secret key"** 버튼 클릭
3. **이름 설정** (예: "Advanced Explorer")
4. **권한 설정**: 
   - "All" 또는 "Chat" 권한 선택
5. **"Create secret key"** 클릭
6. **⚠️ 중요**: API Key를 **안전한 곳에 복사 저장**하세요!
   - 형식: `sk-proj-xxxxxxxxxxxxxxxxxxxx...`
   - 이 창을 닫으면 다시 볼 수 없습니다!

---

## 2. API Key 설정 방법

### 방법 1: 프로그램 내에서 설정 (추천)

1. **Advanced Explorer 실행**
2. **파일 선택** 및 **내용 보기**
3. **"🤖 GPT 요약" 버튼** 클릭
4. **팝업창에서 API Key 입력**
5. API Key는 자동으로 저장됩니다 (브라우저 localStorage)

### 방법 2: 브라우저 개발자 도구에서 설정

1. **F12** 눌러서 개발자 도구 열기
2. **Console** 탭 선택
3. 다음 코드 입력:
```javascript
localStorage.setItem('gptApiKey', 'sk-proj-여기에_당신의_API_KEY_입력');
```
4. **Enter** 키 누르기
5. 페이지 새로고침 (F5)

---

## 3. 사용 방법

### 로컬 요약 vs GPT 요약

| 기능 | 로컬 요약 (TextRank) | GPT 요약 🤖 |
|------|---------------------|------------|
| **비용** | 무료 | 유료 (API 사용량) |
| **속도** | 빠름 (1-2초) | 보통 (3-5초) |
| **품질** | 양호 | 우수 |
| **인터넷** | 불필요 | 필요 |
| **API Key** | 불필요 | 필요 |

### 사용 순서

1. **파일 인덱싱**
   - 폴더 선택 후 "시작" 버튼으로 인덱싱

2. **파일 선택**
   - 인덱싱된 파일 클릭

3. **요약 버튼 클릭**
   - **파란색 "로컬 요약"**: 무료, 빠름
   - **보라색 "🤖 GPT 요약"**: 유료, 고품질

4. **요약 결과 확인**
   - 내용 보기 패널에 요약 표시
   - 📋 복사 버튼으로 클립보드 복사 가능

---

## 4. 비용 안내

### GPT-4o-mini 가격 (2024년 12월 기준)
- **입력**: $0.150 / 1M 토큰
- **출력**: $0.600 / 1M 토큰

### 예상 비용
- **1회 요약**: 약 $0.001 ~ $0.005 (₩1-7원)
- **100회 요약**: 약 $0.10 ~ $0.50 (₩130-650원)
- **1000회 요약**: 약 $1 ~ $5 (₩1,300-6,500원)

### 무료 크레딧
- 🎁 **신규 가입**: $5 무료 크레딧 (3개월 유효)
- 약 **1,000~5,000회** 요약 가능!

### 비용 절약 팁
1. **짧은 문서**는 **로컬 요약** 사용 (무료)
2. **중요한 문서**만 **GPT 요약** 사용
3. **API 사용량 모니터링**: https://platform.openai.com/usage

---

## 5. 문제 해결

### ❌ "API Key가 유효하지 않습니다"

**원인**:
- API Key가 잘못 입력됨
- API Key가 삭제되었거나 만료됨

**해결책**:
1. API Key 다시 확인: https://platform.openai.com/api-keys
2. 새 API Key 생성
3. 프로그램에 다시 입력

### ❌ "API 사용량 한도를 초과했습니다"

**원인**:
- 무료 크레딧 소진
- 사용량 한도 초과
- 결제 수단 문제

**해결책**:
1. **사용량 확인**: https://platform.openai.com/usage
2. **크레딧 충전**: https://platform.openai.com/account/billing
3. **잠시 후 재시도** (Rate Limit인 경우)

### ❌ "openai 라이브러리가 설치되지 않았습니다"

**원인**:
- Python 백엔드 라이브러리 누락

**해결책**:
```bash
cd python-backend
.\venv\Scripts\pip.exe install openai==1.54.0
```

---

## 🔐 보안 주의사항

### API Key 보호
- ✅ API Key를 **절대 공유하지 마세요**
- ✅ GitHub 등 공개 저장소에 **업로드하지 마세요**
- ✅ 유출 시 즉시 **삭제 후 재발급**하세요

### API Key 삭제
유출이 의심되면 즉시 삭제:
1. https://platform.openai.com/api-keys 방문
2. 해당 API Key의 **"Revoke"** 버튼 클릭
3. 새 API Key 재발급

---

## 📞 추가 정보

### 공식 문서
- **OpenAI Platform**: https://platform.openai.com
- **API 문서**: https://platform.openai.com/docs/api-reference
- **가격**: https://openai.com/api/pricing

### 커뮤니티
- **OpenAI 커뮤니티**: https://community.openai.com
- **Discord**: https://discord.com/invite/openai

---

## 🎉 시작하기

1. **API Key 발급**: https://platform.openai.com/api-keys
2. **Advanced Explorer 실행**
3. **파일 인덱싱 및 선택**
4. **"🤖 GPT 요약" 버튼** 클릭
5. **API Key 입력** (처음 1회만)
6. **요약 결과 확인!**

**즐거운 문서 관리 되세요!** 🚀




