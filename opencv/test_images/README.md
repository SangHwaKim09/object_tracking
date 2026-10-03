# 색 검출 인식률 테스트 이미지 (50장)

`test2.jpg`처럼 배경 위에 단색 도형을 그린 640×480 이미지입니다. (RealSense 컬러 영상과 같은 크기)
각 도형의 정답(색, 모양, 위치)은 `labels.csv`에 있어서, 검출 결과와 비교해 인식률을 계산할 수 있습니다.

## 폴더 구성

| 폴더 | 장수 | 조건 |
|---|---|---|
| `01_normal` | 10 | 보통 조명 |
| `02_bright` | 8 | 아주 밝은 조명: 1.4~2.2배 과노출, 하얗게 날아감, 눈부신 반사, 한쪽에서 강한 빛 |
| `03_dark` | 8 | 어두운 조명: 0.6배 → 0.04배(거의 빛 없음), 어두울수록 카메라 잡음 증가, 노란 전구·푸른 밤빛 |
| `04_uneven` | 6 | 불균일한 조명: 한쪽만 밝음, 가장자리 어두움, 스포트라이트, 그림자 띠, 얼룩진 빛 |
| `05_similar` | 6 | 비슷한 색끼리: 파랑 계열(navy, sky_blue, cyan, purple, teal), 주황 계열(red, yellow, brown, pink, magenta), 목표 색이 없는 이미지 2장 |
| `06_size` | 4 | 크기: 12px, 25px, 40px, 200~230px |
| `07_noise_blur` | 4 | 노이즈, 흐림, 움직임 흐림, 심한 JPEG 압축 |
| `08_background` | 4 | 배경: 흰색, 검은색, 푸르스름한 회색, 얼룩무늬 |

파일 이름 = `폴더이름_번호_조건.jpg` (예: `03_dark/dark_06_x0.04_nolight.jpg`)

## 색과 모양

- **색 17가지:** red, orange, yellow, lime, green, teal, cyan, sky_blue, blue, navy, purple, magenta, pink, brown, white, gray, black
  (실제 물체처럼 도형마다 색을 조금씩 다르게 함, RGB 각 ±12)
- **모양 11가지:** circle, square, rectangle, ellipse, triangle, pentagon, hexagon, star, cross, ring(가운데 뚫린 원), heart
- 대부분의 이미지에 **blue와 orange가 1개 이상** 들어 있습니다. 예외:
  - `similar_01_blue_family`: blue만 (orange 없음)
  - `similar_03_orange_family`: orange만 (blue 없음)
  - `similar_05_no_target`, `similar_06_no_target_2`: 둘 다 없음 → 아무것도 검출되지 않아야 정상

## labels.csv (도형 1개 = 1줄)

| 열 | 뜻 |
|---|---|
| `file` | 이미지 경로 (이 폴더 기준) |
| `category`, `condition` | 폴더, 조건 이름 |
| `obj_id` | 이미지 안에서 도형 번호 |
| `color`, `shape` | 정답 색 이름, 모양 |
| `r`, `g`, `b` | 실제로 칠한 색 (조명 효과 적용 전) |
| `hue`, `sat`, `val` | 위 색을 OpenCV HSV로 바꾼 값 (H: 0~179) |
| `bbox_x`, `bbox_y`, `bbox_w`, `bbox_h` | 도형을 감싸는 박스 (왼쪽 위 좌표, 가로, 세로) |
| `cx`, `cy` | 도형 중심점 (무게중심) |
| `area_px` | 도형 넓이 (픽셀 수) |
| `brightness_ratio` | 조명 효과 후 밝기 ÷ 원래 밝기 (1 = 그대로, 0.1 = 10배 어두워짐) |
| `final_hue`, `final_sat`, `final_val` | 조명 효과 후 이미지에서 실제로 측정되는 HSV (도형 영역의 중앙값) |

`final_*`을 보면 조명 때문에 색이 HSV 범위 밖으로 벗어났는지 바로 확인할 수 있습니다.
(빨강은 H가 0과 179 양쪽에 걸쳐 있어서 중앙값이 어색하게 나올 수 있습니다.)

## 인식률 계산 방법 (예)

1. 이미지마다 검출 프로그램을 돌려 물체 중심점 목록을 얻습니다.
2. 중심점이 `labels.csv`의 어떤 도형 박스 안에 있는지 찾습니다.
   - 찾는 색과 정답 색이 같으면 **정답(검출 성공)**
   - 다른 색 도형이나 배경이면 **오검출**
3. 인식률 = 검출 성공한 도형 수 ÷ 찾는 색 도형 수

## 다시 만들기

```bash
cd opencv/test_images
../../.venv/bin/python make_test_images.py
```

시드가 고정되어 있어 다시 실행해도 같은 이미지가 만들어집니다.
조건이나 장수를 바꾸려면 `make_test_images.py`의 `PLAN` 목록을 수정하면 됩니다.
