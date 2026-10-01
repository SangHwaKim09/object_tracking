from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np

lower_orange = (5, 100, 100)    # OpenCV HSV 기준 주황 (H: 0~179)
upper_orange = (25, 255, 255)

# 스크립트 위치 기준 경로 (실행 위치와 무관)
img_path = Path(__file__).resolve().parent / "test2.jpg"
if not img_path.exists():
    raise FileNotFoundError(f"{img_path}를 찾을 수 없음")

# cv2.imread는 Windows 한글 경로를 못 읽으므로 imdecode 사용 (BGR로 읽음)
img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
if img is None:
    raise ValueError(f"{img_path}를 이미지로 읽을 수 없음")

img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
img_mask = cv2.inRange(img_hsv, lower_orange, upper_orange)

# 마스크의 작은 점 노이즈 제거
kernel = np.ones((3, 3), np.uint8)
img_mask = cv2.morphologyEx(img_mask, cv2.MORPH_OPEN, kernel)

img_result = cv2.bitwise_and(img, img, mask=img_mask)

# 원본 / 마스크 / 결과 비교 (표시할 때만 RGB로)
fig, axes = plt.subplots(1, 3, figsize=(12, 4))
axes[0].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
axes[0].set_title("Original")
axes[1].imshow(img_mask, cmap="gray")
axes[1].set_title("Mask")
axes[2].imshow(cv2.cvtColor(img_result, cv2.COLOR_BGR2RGB))
axes[2].set_title("Result")
for ax in axes:
    ax.axis("off")
plt.tight_layout()
plt.show()
