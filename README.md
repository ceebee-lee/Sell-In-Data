# SELL-IN 분석 대시보드

화장품 ERP SELL-IN 데이터를 수량 중심으로 분석하는 Streamlit 대시보드입니다.

## 배포 전 주의

포함된 `26년 상반기 SELL-IN 데이터.xlsx`는 실제 분석 데이터입니다. GitHub 저장소와 Streamlit 앱을 **비공개(Private)** 로 설정하세요. 외부 공개가 필요한 경우에는 실제 데이터 파일을 제거하고 익명화된 예시 파일로 교체하세요.

## Streamlit Community Cloud 배포

1. GitHub에서 새 **Private repository**를 만듭니다.
2. 이 폴더 안의 파일과 `.streamlit` 폴더를 저장소 최상위에 업로드합니다.
3. [Streamlit Community Cloud](https://share.streamlit.io/)에 GitHub 계정으로 로그인합니다.
4. `Create app`을 선택합니다.
5. Repository와 Branch를 선택하고 Main file path에 `app.py`를 입력합니다.
6. Python 버전은 `3.12`를 선택하고 `Deploy`를 누릅니다.
7. 배포 후 App settings → Sharing에서 접근 권한이 비공개인지 확인합니다.

GitHub 저장소의 파일을 수정하고 커밋하면 배포된 앱에도 자동 반영됩니다.

## 데이터 사용 방식

- 앱을 처음 열면 포함된 상반기 데이터가 자동으로 표시됩니다.
- 사이드바에서 다른 `.xlsx` 또는 `.xlsm` 파일을 업로드하면 해당 파일로 즉시 교체됩니다.
- 업로드 파일은 앱 재시작 후 유지되지 않으므로, 기본 데이터를 영구 교체하려면 저장소의 엑셀 파일을 같은 이름으로 교체하세요.
- 대륙 매핑은 CSV로 내려받은 뒤 다음 접속에서 다시 업로드할 수 있습니다.

## 로컬 실행

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## 필수 원본 컬럼

- `출고일`
- `출고수량`
- `품목`
- `품목명`
- `출고금액` 또는 `조정출고금액`
