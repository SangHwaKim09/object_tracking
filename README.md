## windows 웹캠프로그램을 이용한 실시간 blue object 추적

## Linux 실행 방법

프로젝트 루트(`object_tracking/`)에서 가상환경을 만들고 activate합니다.

```bash
cd object_tracking
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

activate한 상태에서 실행합니다. (종료: `q` 또는 `ESC`)

```bash
python opencv/blue_detect_linux.py
```
