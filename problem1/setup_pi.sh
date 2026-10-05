#!/usr/bin/env bash
# 라즈베리파이에서 problem1 실행 환경 만들기 (Ubuntu 26.04 / ARM64 / Python 3.14 기준)
#
# 왜 필요한가: pyrealsense2는 ARM64용으로 Python 3.9, 3.10, 3.12만 배포되어 있어서
#             파이 기본 Python 3.14로는 설치되지 않음 → uv로 Python 3.12 가상환경(.venv)을 따로 만듦
#
# 사용법 (파이에서, 프로젝트 루트):
#   bash problem1/setup_pi.sh
# 끝나면:
#   .venv/bin/python problem1/Image_capture.py --headless
set -euo pipefail
cd "$(dirname "$0")/.."   # 어디서 실행하든 프로젝트 루트(object_tracking/)로 이동

echo "[1/5] 시스템 확인"
echo "  아키텍처: $(uname -m)   기본 파이썬: $(python3 -V 2>&1)"
if lsusb | grep -qi realsense; then
  echo "  RealSense 연결됨: $(lsusb | grep -i realsense)"
else
  echo "  ! RealSense가 보이지 않습니다. USB 3.0 포트(파란색)에 연결하세요. (설치는 계속 진행)"
fi

echo "[2/5] uv 설치 (이미 있으면 건너뜀)"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
uv --version

echo "[3/5] Python 3.12 가상환경 (.venv)"
if [ -x .venv/bin/python ]; then
  echo "  기존 .venv 사용: $(.venv/bin/python -V)"
else
  uv venv --python 3.12 --seed .venv
fi
if ! .venv/bin/python -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))'; then
  echo "  ! .venv가 Python 3.12가 아닙니다. 'rm -rf .venv' 후 다시 실행하세요."
  exit 1
fi

echo "[4/5] 패키지 설치 (화면 없는 파이용: GUI 없는 OpenCV, 튜너용 ruamel.yaml 제외)"
.venv/bin/python -m pip install \
  opencv-python-headless==5.0.0.93 numpy==2.5.3 PyYAML==6.0.3 pyrealsense2==2.58.4.10922

echo "[5/5] RealSense USB 권한(udev 규칙) — sudo 비밀번호가 필요할 수 있음"
RULES=/etc/udev/rules.d/99-realsense-libusb.rules
if [ -f "$RULES" ]; then
  echo "  이미 설치됨: $RULES"
else
  sudo curl -fsSL -o "$RULES" \
    https://raw.githubusercontent.com/IntelRealSense/librealsense/master/config/99-realsense-libusb.rules
  sudo udevadm control --reload-rules
  sudo udevadm trigger
  echo "  설치 완료 → RealSense를 뽑았다가 다시 꽂은 뒤 아래 확인 명령을 실행하세요."
fi

echo
echo "확인: RealSense 인식 ( ['Intel RealSense D435'] 가 나오면 준비 완료 )"
.venv/bin/python -c "import pyrealsense2 as rs; print([d.get_info(rs.camera_info.name) for d in rs.context().devices])"
