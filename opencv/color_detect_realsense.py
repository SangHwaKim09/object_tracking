"""
RealSense 카메라로 파란색 물체를 실시간 추적하는 프로그램

- 컬러 영상에서 파란색 영역을 찾아 파란 박스로 표시합니다.
- 깊이(Depth) 영상으로 카메라에서 물체까지의 거리(cm)를 박스 위에 표시합니다.
- 거리로 물체의 실제 크기(cm)를 계산해서, 너무 작은 것은 노이즈로 보고 무시합니다.
- 화면 중심점(초록 점)과 물체 중심점(빨간 점, 좌표 표시)을 함께 그립니다.

실행: ../.venv/bin/python color_detect_realsense.py
종료: 영상 창을 클릭한 뒤 q 또는 ESC
"""
import cv2                  # 영상 처리 (OpenCV)
import numpy as np          # 배열 계산
import pyrealsense2 as rs   # Intel RealSense 카메라 제어

# ──────────────────────────────────────────────
# 설정값 (필요하면 여기만 바꾸면 됩니다)
# ──────────────────────────────────────────────

# 파란색으로 인정할 HSV 범위 [색상(H), 채도(S), 밝기(V)]
# OpenCV에서 H는 0~179 (일반 색상표 각도 ÷ 2) → 파랑은 약 100~130
LOWER_BLUE = np.array([90, 80, 40])     # 하한
UPPER_BLUE = np.array([135, 255, 255])  # 상한

# 크기 필터: 아래 기준보다 작은 덩어리는 노이즈로 보고 무시
MIN_SIZE_CM = 3.0    # 실제 크기 기준. 약 3cm × 3cm보다 작은 물체는 무시 (거리와 상관없이 같은 기준)
MIN_PIXELS = 50      # 화면에서 50픽셀도 안 되는 작은 점은 카메라 잡음으로 보고 바로 무시
FALLBACK_AREA = 500  # 거리를 잴 수 없을 때(너무 가깝거나 빛 반사 등)는 화면 넓이 500픽셀로 대신 판단

W, H, FPS = 640, 480, 30   # 영상 크기(가로, 세로)와 초당 프레임 수
CX, CY = W // 2, H // 2    # 화면 중심점 좌표 (320, 240)

# ──────────────────────────────────────────────
# RealSense 카메라 시작
# ──────────────────────────────────────────────

pipeline = rs.pipeline()   # 카메라에서 프레임을 받아오는 통로
config = rs.config()       # 어떤 영상을 받을지 설정
config.enable_stream(rs.stream.color, W, H, rs.format.bgr8, FPS)  # 컬러 영상 (OpenCV와 같은 BGR 순서)
config.enable_stream(rs.stream.depth, W, H, rs.format.z16, FPS)   # 깊이 영상 (픽셀마다 거리 값)
try:
    profile = pipeline.start(config)
except RuntimeError as e:  # 카메라가 연결 안 됐거나 다른 프로그램이 사용 중일 때
    raise SystemExit(f"RealSense를 열 수 없습니다: {e}")

# 깊이 값은 정수 단위로 들어옴 → depth_scale을 곱하면 미터(m)가 됨 (D435는 보통 0.001)
depth_scale = profile.get_device().first_depth_sensor().get_depth_scale()

# 컬러 카메라의 초점거리(픽셀 단위, D435는 약 600)
# 거리와 함께 쓰면 화면 속 픽셀 크기를 실제 크기(cm)로 바꿀 수 있음
intr = profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
focal_px = (intr.fx * intr.fy) ** 0.5  # 가로(fx)·세로(fy) 초점거리의 평균

# 컬러 카메라와 깊이 카메라는 위치가 조금 달라서 화면이 어긋남
# → 깊이 영상을 컬러 영상 좌표에 맞춰(정렬) 같은 (x, y)가 같은 지점을 가리키게 함
align = rs.align(rs.stream.color)

# 마스크 노이즈 제거에 쓸 5x5 크기의 필터
kernel = np.ones((5, 5), np.uint8)


def object_distance(depth, mask, x, y, w, h):
    """박스 안 물체까지의 거리(m)를 구한다. 구할 수 없으면 None.

    박스 안에서 '파란색이면서 깊이 값이 있는(0이 아닌)' 픽셀만 골라
    그 거리들의 중앙값을 사용한다. (배경이나 측정 실패 픽셀의 영향을 줄이기 위함)
    """
    roi_depth = depth[y:y + h, x:x + w]       # 박스 영역의 깊이 값
    roi_mask = mask[y:y + h, x:x + w] > 0     # 박스 영역에서 파란색인 픽셀 (True/False)
    values = roi_depth[roi_mask & (roi_depth > 0)]  # 파란색이면서 깊이가 측정된 픽셀만
    if values.size == 0:  # 쓸 수 있는 픽셀이 하나도 없으면 (너무 가깝거나 반사 등)
        return None
    return float(np.median(values)) * depth_scale  # 중앙값을 미터로 변환


def real_size_cm(area_px, dist_m):
    """화면 넓이(픽셀)와 거리(m)로 물체의 실제 크기(cm)를 구한다.

    카메라에서 d(m) 떨어진 곳에서는 화면의 1픽셀이 실제로 d / 초점거리 (m) 길이에 해당한다.
    → 같은 물체라도 멀어지면 화면에서 작아지지만, 이 값은 거리와 상관없이 일정하다.
    넓이를 정사각형으로 봤을 때 한 변의 길이를 돌려준다. (예: 3.0 → 약 3cm × 3cm)
    """
    side_px = area_px ** 0.5                   # 넓이를 정사각형으로 봤을 때 한 변의 픽셀 수
    return side_px * dist_m / focal_px * 100   # 픽셀 → 미터 → 센티미터


# ──────────────────────────────────────────────
# 메인 루프: 프레임을 계속 받아서 처리하고 화면에 표시
# ──────────────────────────────────────────────
try:
    while True:
        # 1) 카메라에서 컬러 + 깊이 프레임을 받아 정렬
        frames = align.process(pipeline.wait_for_frames())
        color_frame = frames.get_color_frame()
        depth_frame = frames.get_depth_frame()
        if not color_frame or not depth_frame:  # 한쪽이라도 빠지면 이번 프레임은 건너뜀
            continue
        frame = np.asanyarray(color_frame.get_data()).copy()  # 컬러 영상 (그림을 그릴 것이라 복사본 사용)
        depth = np.asanyarray(depth_frame.get_data())         # 깊이 영상

        # 2) 파란색 영역만 흰색(255)으로 남긴 마스크 만들기
        blurred = cv2.GaussianBlur(frame, (7, 7), 0)          # 살짝 흐리게 해서 잡티 줄이기
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)        # BGR → HSV (색 범위로 고르기 쉬움)
        mask = cv2.inRange(hsv, LOWER_BLUE, UPPER_BLUE)       # 범위 안 = 흰색, 밖 = 검은색
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)   # 작은 흰 점(노이즈) 지우기
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)  # 물체 안의 작은 구멍 메우기

        # 3) 화면 중심점 표시 (초록 점, 반지름 3px)
        #    ※ OpenCV 색상은 (B, G, R) 순서: (0, 255, 0) = 초록
        cv2.circle(frame, (CX, CY), 3, (0, 255, 0), -1)  # -1 = 속을 채운 원

        # 4) 마스크에서 파란 덩어리의 외곽선을 찾아 하나씩 처리
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            area_px = cv2.contourArea(c)  # 덩어리의 화면 넓이(픽셀 수)
            if area_px < MIN_PIXELS:      # 아주 작은 점은 카메라 잡음 → 건너뜀
                continue

            x, y, w, h = cv2.boundingRect(c)  # 박스의 왼쪽 위 좌표(x, y)와 가로(w), 세로(h)
            dist = object_distance(depth, mask, x, y, w, h)

            # 4-1) 크기 필터: 거리를 알면 실제 크기(cm)로, 모르면 화면 넓이(픽셀)로 판단
            if dist is not None:
                if real_size_cm(area_px, dist) < MIN_SIZE_CM:
                    continue
            elif area_px < FALLBACK_AREA:
                continue

            # 4-2) 물체를 감싸는 박스와 거리 표시 (파란색)
            # 거리는 m로 계산하고, 화면에는 cm(정수)로 표시. 거리를 못 구하면 --
            label = f"Blue {dist * 100:.0f} cm" if dist is not None else "Blue --"
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
            cv2.putText(frame, label, (x, max(y - 8, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

            # 4-3) 물체 중심점 표시 (빨간 점 + 좌표)
            #      moments로 외곽선의 무게중심을 계산: x = m10/m00, y = m01/m00
            m = cv2.moments(c)
            tx, ty = int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"])
            cv2.circle(frame, (tx, ty), 6, (0, 0, 255), -1)
            cv2.putText(frame, f"Target ({tx}, {ty})", (tx + 10, ty + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        # 5) 화면 3개 띄우기
        result = cv2.bitwise_and(frame, frame, mask=mask)  # 원본에서 파란 부분만 남긴 영상
        cv2.imshow("Blue Detection", frame)  # 박스, 거리, 중심점이 그려진 영상
        cv2.imshow("Mask", mask)             # 흑백 마스크 (흰색 = 파란색으로 인식된 곳)
        cv2.imshow("Result", result)         # 파란 부분만 보이는 영상

        # 6) q 또는 ESC(27)를 누르면 종료
        if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
            break
finally:
    # 오류가 나거나 종료할 때도 항상 카메라를 멈추고 창을 닫음
    pipeline.stop()
    cv2.destroyAllWindows()
