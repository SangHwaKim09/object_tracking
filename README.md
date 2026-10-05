## windows 웹캠프로그램을 이용한 실시간 object 추적

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
python opencv/color_detect_linux.py
```

---

## 문제 1: RealSense 단일 색상 목표 검출 (`problem1/`)

RealSense 카메라 영상에서 정해진 색(기본: 파랑)의 목표를 찾아, **화면 중심에서 얼마나 벗어났는지(ex, ey)**,
**화면에서 차지하는 크기(z)**, **실제 거리(dist_cm)** 를 계산합니다.
HSV 범위를 조절하는 튜너와, 장면별 결과를 사진·기록으로 남기는 캡처 프로그램이 함께 있습니다.

### 파일 구성

| 파일 | 역할 |
|---|---|
| `problem1/Detector.py` | 검출기 본체. RealSense 카메라 읽기(`RealSenseCamera`), 검출(`detect`), 결과 그리기(`draw`) |
| `problem1/Detector.yaml` | 설정 파일. 카메라 해상도, HSV 색 범위, 최소 크기 등 |
| `problem1/HSV_tuning.py` | **1단계.** 트랙바로 HSV 범위를 조절하고 설정 파일에 저장 |
| `problem1/Image_capture.py` | **2단계.** 정상 / 목표 없음 / 일부 가림 장면을 사진과 `log.csv`로 저장 |
| `problem1/setup_pi.sh` | 라즈베리파이 실행 환경을 한 번에 만드는 설치 스크립트 (아래 "라즈베리파이에서 실행" 참고) |

검출 순서: 영상 → 블러 → HSV 변환 → 색 마스크 → 잡음 제거 → 외곽선 → **가장 큰 덩어리 1개 선택** → 중심·거리 계산

### 준비

1. 위의 "Linux 실행 방법"대로 가상환경을 만들고 `pip install -r requirements.txt`를 실행합니다.
   (`pyrealsense2`, `PyYAML`, 튜너 저장용 `ruamel.yaml`이 함께 설치됩니다.)
2. RealSense D435를 **USB 3.0 포트**에 연결합니다.
3. 아래 명령은 모두 **프로젝트 루트(`object_tracking/`)에서 가상환경을 activate한 상태**로 실행합니다.

### 1단계: HSV 범위 조절 (`HSV_tuning.py`)

```bash
python problem1/HSV_tuning.py
```

`tuner` 창이 뜨고, 왼쪽에 검출 결과, 오른쪽에 마스크(흰색 = 목표 색으로 인식된 곳)가 보입니다.
목표 물체를 카메라 앞에 두고, **목표만 흰색으로 깔끔하게 보이도록** 트랙바를 조절합니다.

트랙바 이름 옆의 괄호는 `(현재값/최댓값)`입니다.

| 트랙바 | 뜻 | 조절 요령 |
|---|---|---|
| `H 최소 (색상 시작)`, `H 최대 (색상 끝)` | 색상 범위 (OpenCV는 0~179, 일반 색상표 각도 ÷ 2) | 파랑 ≈ 100~130, 주황 ≈ 5~25 |
| `S 최소 (진하기 하한)`, `S 최대 (진하기 상한)` | 채도 (0 = 흰색·회색, 255 = 진한 색) | 배경의 흰색·회색이 잡히면 `S 최소`를 올림 |
| `V 최소 (밝기 하한)`, `V 최대 (밝기 상한)` | 밝기 (0 = 검정, 255 = 가장 밝음) | 어두운 그림자가 잡히면 `V 최소`를 올림 |
| `최소 크기 (화면의 1/10000)` | 최소 크기 = 화면 넓이 × (값 ÷ 10000) | 작은 잡티가 잡히면 올림 (16 ≈ 640×480에서 약 500px) |

> 트랙바 이름이 보이지 않으면 한글 글꼴(`fonts-noto-cjk`)이 설치되어 있는지 확인하세요.
> (Linux용 OpenCV에는 글꼴이 들어 있지 않아, 튜너가 `/usr/share/fonts/opentype/noto`의 글꼴을 사용합니다.)

| 키 | 동작 |
|---|---|
| `s` | 현재 값을 `problem1/Detector.yaml`에 저장 (HSV 범위와 최소 크기만 바뀌고, 주석과 다른 항목은 그대로 유지) |
| `q` | 종료 |

> 주의: 튜너는 색 범위를 1개만 다루므로, `s`로 저장하면 **색 범위가 1개로 바뀝니다.**
> 빨강처럼 범위가 2개 필요한 색은 저장 후 `Detector.yaml`을 직접 고쳐야 합니다.
> 값 옆의 주석(예: `약 614px`)은 그대로 남으므로, 값이 바뀌면 주석 내용과 달라질 수 있습니다.

### 2단계: 장면 캡처 (`Image_capture.py`)

과제용 증거로 세 가지 장면을 저장합니다.

```bash
python problem1/Image_capture.py              # 화면이 있는 노트북
python problem1/Image_capture.py --headless   # 화면 없는 SSH 접속 (예: 라즈베리파이)
```

| 키 | 장면 | 준비할 상황 |
|---|---|---|
| `n` | normal (정상) | 목표가 잘 보이는 상태 |
| `e` | empty (목표 없음) | 목표를 화면 밖으로 치운 상태 → `found=False`가 나와야 정상 |
| `o` | occluded (일부 가림) | 목표의 일부를 손이나 물건으로 가린 상태 |
| `q` | 종료 | |

- **GUI 모드:** 영상 창을 클릭한 뒤 키를 누릅니다. 왼쪽에 검출 결과, 오른쪽에 마스크가 보입니다.
- **headless 모드:** 터미널에 `n`, `e`, `o`, `q` 중 하나를 입력하고 Enter를 누르면, 그 순간의 최신 영상이 저장됩니다.
  라즈베리파이에서 쓰는 방법은 아래 "라즈베리파이에서 실행"을 참고하세요.

#### 저장되는 결과

`problem1/results/scenes/`에 저장됩니다. (`.gitignore`에 등록되어 있어 git에는 올라가지 않음)

| 파일 | 내용 |
|---|---|
| `<장면>_<날짜_시각>_raw.png` | 원본 영상 |
| `<장면>_<날짜_시각>_mask.png` | 색 마스크 (흰색 = 목표 색) |
| `<장면>_<날짜_시각>_det.png` | 검출 결과를 그린 영상 |
| `log.csv` | 저장할 때마다 한 줄씩 기록 (열 설명은 아래) |

> 같은 장면을 같은 초에 다시 저장하면 덮어쓰지 않고 이름 뒤에 `_2`, `_3`이 붙습니다. (`log.csv`의 `time`에도 같은 이름으로 기록)

### 결과 값의 의미

검출 결과 화면 왼쪽 위와 `log.csv`에 표시되는 값입니다.

| 값 | 뜻 | 예시 |
|---|---|---|
| `time`, `scene` | 저장 시각, 장면 이름 (`log.csv`에만 있음) | `20261005_152309`, `normal` |
| `found` | 목표를 찾았는지 | 못 찾으면 `False`, 이때 ex = ey = z = 0 |
| `ex` | 가로 방향 어긋남. −1(왼쪽 끝) ~ 0(중앙) ~ +1(오른쪽 끝) | `+0.40` → 중앙보다 오른쪽 |
| `ey` | 세로 방향 어긋남. −1(위쪽 끝) ~ 0(중앙) ~ +1(아래쪽 끝) | `-0.33` → 중앙보다 위쪽 |
| `z` | 목표 넓이 ÷ 화면 넓이. 가까울수록 커짐 | `0.0547` → 화면의 약 5.5% |
| `dist_cm` | 깊이로 잰 목표까지의 실제 거리(cm) | `38.7`, 측정에 실패했거나 믿을 수 없으면 빈칸(화면에는 `--`) |
| `n_candidates` | 최소 크기를 넘은 같은 색 덩어리 수 | 2 이상이면 비슷한 색 물체가 더 있다는 뜻 |
| `width`, `height` | 영상 크기 | `640`, `480` |
| `hsv_ranges`, `min_area_ratio` | 저장 당시 사용한 설정 | |

화면 표시: 흰 십자 = 화면 중심, 초록 선 = 목표 외곽선, 빨간 점 = 목표 중심, 빨간 선 = 화면 중심과 목표 중심을 잇는 선

### 설정 파일 (`problem1/Detector.yaml`)

| 항목 | 예시 값 | 뜻 |
|---|---|---|
| `camera.width`, `camera.height` | 640, 480 | RealSense 컬러·깊이 해상도 |
| `camera.fps` | 30 | 초당 프레임 (없으면 30) |
| `hsv.ranges` | `[93, 120, 35]` ~ `[130, 255, 255]` | 목표 색의 HSV 범위. 여러 개를 적으면 합쳐서 검출 |
| `min_area_ratio` | 0.002 | 화면 넓이 대비 최소 크기 |
| `blur_ksize` | 5 | 블러 크기. 홀수 (짝수를 적으면 1 크게 자동 보정, 1이면 블러 안 함) |
| `morph_ksize` | 5 | 잡음 제거 크기 |
| `depth.min_valid_ratio` | 0.5 | 목표 영역에서 깊이가 측정된 픽셀 비율이 이보다 낮으면 거리를 비움 (없으면 0.5) |
| `depth.max_spread_cm` | 5.0 | 목표 영역 깊이 값의 흩어짐(25~75% 구간 폭)이 이보다 크면 거리를 비움 (없으면 5.0) |

### 라즈베리파이에서 실행

파이(Ubuntu 26.04)의 기본 파이썬은 3.14인데, `pyrealsense2`는 ARM64용으로 Python 3.9 / 3.10 / 3.12만 배포되어 있습니다.
그래서 `setup_pi.sh`가 [uv](https://github.com/astral-sh/uv)로 **Python 3.12 가상환경(`.venv`)** 을 따로 만듭니다. (시스템 파이썬은 건드리지 않음)

1. **코드를 파이로 옮기기** (노트북의 프로젝트 루트에서. GitHub에 올렸다면 파이에서 `git clone`/`git pull`로 받아도 됨)
   ```bash
   ssh pa16@pa05.local mkdir -p object_tracking/problem1
   scp problem1/*.py problem1/*.sh problem1/Detector.yaml pa16@pa05.local:~/object_tracking/problem1/
   ```
2. **RealSense를 파이의 USB 3.0 포트(파란색)에 연결**합니다. 전원은 3A 어댑터를 권장합니다.
3. **설치** (파이에서)
   ```bash
   cd ~/object_tracking
   bash problem1/setup_pi.sh
   ```
   uv 설치 → Python 3.12 가상환경 → 패키지(화면 없는 파이용 OpenCV 등) → USB 권한(udev 규칙, sudo 비밀번호 필요) 순서로 진행되고,
   마지막에 `['Intel RealSense D435']`가 나오면 준비 완료입니다.
   udev 규칙을 새로 설치한 경우에는 카메라를 뽑았다가 다시 꽂은 뒤 스크립트를 한 번 더 실행하면 확인까지 됩니다.
4. **HSV 범위는 노트북에서 조절** (튜너는 화면이 필요) 하고, 설정 파일만 파이로 보냅니다.
   조명에 따라 색이 달라지므로 파이를 실제로 쓸 장소에서 조절하는 것이 좋습니다.
   ```bash
   scp problem1/Detector.yaml pa16@pa05.local:~/object_tracking/problem1/
   ```
5. **실행** (파이에서)
   ```bash
   .venv/bin/python problem1/Image_capture.py --headless
   ```
6. **결과를 노트북으로 가져와 확인**
   ```bash
   scp -r pa16@pa05.local:~/object_tracking/problem1/results ./pi_results
   ```

### 다른 코드에서 검출기 사용하기

`detect()`는 영상만 받아서 결과를 돌려주므로, 나중에 ROS 2 노드 등에서 그대로 불러 쓸 수 있습니다.
(`detect()`만 쓸 때는 `pyrealsense2`가 필요 없음)

```python
import sys; sys.path.insert(0, "problem1")    # problem1 폴더 밖에서 불러올 때만 필요
from Detector import load_config, detect

cfg = load_config()                            # problem1/Detector.yaml
res = detect(color_bgr, cfg)                   # 거리 없이
res = detect(color_bgr, cfg, depth, 0.001)     # 컬러에 정렬된 깊이(z16)와 깊이 배율을 주면 dist_cm도 계산
print(res["found"], res["ex"], res["ey"], res["z"], res["dist_cm"])
```

### 알아둘 점

- **목표는 가장 큰 덩어리 1개만 고릅니다.** 비슷한 색의 더 큰 물체(예: 남색, 하늘색)가 있으면 그쪽을 목표로 잡을 수 있습니다.
  `n_candidates`가 2 이상이면 화면에 다른 후보가 있는지 확인하세요.
- **`z`는 거리가 아닙니다.** 거리의 제곱에 반비례하고, 목표가 일부 가려지면 작아져서 멀어진 것처럼 보입니다. 실제 거리는 `dist_cm`을 보세요.
- **`dist_cm`의 정확도 (D435, 640×480에서 실측):**
  - 가린 것이 없으면 **약 17cm ~ 68cm 구간에서 오차 3% 이내**였습니다. (17cm보다 가까운 거리는 측정하지 않음)
  - 목표 **바로 앞을 손으로 가려도**(목표의 절반 이상 가림) 거리는 정확했습니다.
  - 손 같은 물체가 **카메라 가까이**에서 목표를 가리면 거리를 잴 수 없습니다. RealSense는 약 5cm 떨어진
    적외선 카메라 두 대로 거리를 재는데, 렌즈 가까이의 물체가 한쪽 카메라의 시야만 가리기 때문입니다.
    이때는 틀린 값 대신 `--`(빈칸)가 나오도록 `depth` 설정의 두 기준으로 걸러냅니다.
  - 빛을 강하게 반사하는 표면도 깊이가 측정되지 않아 `--`가 나올 수 있습니다.
- 종료 키는 `q`만 동작합니다. (`ESC`는 동작하지 않음)
