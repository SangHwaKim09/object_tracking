"""HSV·Contour 단일 색상 목표 검출기 (ROS 비의존 — 나중에 ROS2 노드에서 import해서 사용)

파이프라인: 영상 → 블러 → HSV → 색상 마스크 → 잡음 제거 → 컨투어 → 대상 선택 → 중심 계산
대상 선택 규칙: min_area_ratio 이상인 컨투어 중 면적이 가장 큰 것 1개
카메라: Intel RealSense (컬러 + 깊이). 깊이를 주면 목표까지의 실제 거리(dist_cm)도 계산
"""
from pathlib import Path

import cv2
import numpy as np
import yaml

CONFIG_PATH = Path(__file__).resolve().parent / "Detector.yaml"  # 실행 위치와 상관없이 이 폴더의 설정 사용


def load_config(path=CONFIG_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class RealSenseCamera:
    """RealSense에서 컬러 영상과 (컬러 좌표에 맞춰 정렬된) 깊이 영상을 읽는다.

    cam_cfg: 설정 파일의 camera 항목 (width, height, fps)
    """

    def __init__(self, cam_cfg):
        import pyrealsense2 as rs  # 카메라를 쓸 때만 필요 → detect()만 쓰는 곳(ROS 노드 등)은 설치 불필요

        w, h, fps = cam_cfg["width"], cam_cfg["height"], cam_cfg.get("fps", 30)
        self.pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, w, h, rs.format.bgr8, fps)
        config.enable_stream(rs.stream.depth, w, h, rs.format.z16, fps)
        try:
            profile = self.pipeline.start(config)
        except RuntimeError as e:  # 연결 안 됨, 다른 프로그램이 사용 중, 지원하지 않는 해상도 등
            raise SystemExit(f"RealSense를 열 수 없습니다: {e}")
        self.depth_scale = profile.get_device().first_depth_sensor().get_depth_scale()  # 깊이 값 → 미터
        self.align = rs.align(rs.stream.color)  # 깊이를 컬러 좌표에 맞춤 (같은 픽셀 = 같은 지점)

    def read(self):
        """반환: (ok, color(BGR), depth(z16)). 실패하면 (False, None, None)"""
        try:
            frames = self.align.process(self.pipeline.wait_for_frames())
        except RuntimeError:  # 일정 시간 동안 프레임이 안 들어옴
            return False, None, None
        color, depth = frames.get_color_frame(), frames.get_depth_frame()
        if not color or not depth:
            return False, None, None
        return True, np.asanyarray(color.get_data()).copy(), np.asanyarray(depth.get_data()).copy()

    def flush(self, n=5):
        """쌓여 있던 오래된 프레임 버리기 (headless에서 입력을 기다린 뒤 사용)"""
        for _ in range(n):
            self.read()

    def release(self):
        self.pipeline.stop()


def make_mask(frame, cfg):
    k = cfg.get("blur_ksize", 5)
    if k > 1 and k % 2 == 0:  # GaussianBlur는 홀수 크기만 가능 → 짝수면 1 크게 보정
        k += 1
    blurred = cv2.GaussianBlur(frame, (k, k), 0) if k > 1 else frame
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for r in cfg["hsv"]["ranges"]:
        mask |= cv2.inRange(hsv, np.array(r["lower"]), np.array(r["upper"]))

    m = cfg.get("morph_ksize", 5)
    if m > 1:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (m, m))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)   # 작은 점 잡음 제거
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)  # 목표 내부 구멍 메우기
    return mask


def target_distance_cm(depth, mask, contour, depth_scale, min_valid_ratio=0.5, max_spread_cm=5.0):
    """목표까지의 거리(cm). 믿을 수 없으면 None

    목표 컨투어 안에서 색 마스크에 해당하는 픽셀들의 깊이 중앙값을 쓴다.
    단, 아래 경우에는 틀린 값일 가능성이 커서 None을 돌려준다. (실측 근거: 아래 두 기준으로
    정상 측정은 모두 통과하고, 카메라 바로 앞을 손으로 가렸을 때의 틀린 값은 모두 걸러짐)
      - 깊이가 측정된 픽셀 비율 < min_valid_ratio  → 대부분 측정 실패
      - 깊이 값의 흩어짐(p25~p75) > max_spread_cm  → 다른 물체·배경의 깊이가 섞임
    RealSense는 약 5cm 떨어진 적외선 카메라 두 대로 거리를 재므로, 카메라 가까이에 손 같은 물체가 있어
    한쪽 카메라의 시야만 가리면 컬러 화면에 목표가 보여도 깊이는 비거나 엉뚱한 값이 된다.
    """
    region = np.zeros(mask.shape, np.uint8)
    cv2.drawContours(region, [contour], -1, 255, -1)  # 목표 영역을 채운 마스크
    target = depth[(region > 0) & (mask > 0)]          # 목표 픽셀들의 깊이 (0 = 측정 실패)
    values = target[target > 0]
    if values.size == 0 or values.size / target.size < min_valid_ratio:
        return None
    p25, p50, p75 = np.percentile(values, [25, 50, 75]) * depth_scale * 100
    if p75 - p25 > max_spread_cm:
        return None
    return float(p50)


def detect(frame, cfg, depth=None, depth_scale=0.001):
    """반환: dict(found, ex, ey, z, dist_cm, cx, cy, contour, n_candidates, mask)

    미검출이면 found=False, ex=ey=z=0 (이전 좌표를 재사용하지 않음)
    ex=(cx-W/2)/(W/2), ey=(cy-H/2)/(H/2)  → 오른쪽·아래가 +
    z = contour_area / (W*H)
    dist_cm = 깊이 영상(depth, 컬러에 정렬된 z16)으로 잰 목표까지의 거리.
              depth가 없거나, 측정에 실패했거나, 믿을 수 없으면 None (기준: 설정 파일의 depth 항목)
    """
    H, W = frame.shape[:2]
    mask = make_mask(frame, cfg)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = cfg["min_area_ratio"] * W * H
    candidates = [c for c in contours if cv2.contourArea(c) >= min_area]

    result = dict(found=False, ex=0.0, ey=0.0, z=0.0, dist_cm=None, cx=None, cy=None,
                  contour=None, n_candidates=len(candidates), mask=mask)
    if not candidates:
        return result

    target = max(candidates, key=cv2.contourArea)
    M = cv2.moments(target)
    if M["m00"] == 0:
        return result

    cx, cy = M["m10"] / M["m00"], M["m01"] / M["m00"]
    dcfg = cfg.get("depth") or {}  # 설정 파일에 depth 항목이 없으면 기본값 사용
    result.update(
        found=True,
        cx=cx, cy=cy,
        ex=(cx - W / 2) / (W / 2),
        ey=(cy - H / 2) / (H / 2),
        z=cv2.contourArea(target) / (W * H),
        dist_cm=None if depth is None else target_distance_cm(
            depth, mask, target, depth_scale,
            min_valid_ratio=dcfg.get("min_valid_ratio", 0.5),
            max_spread_cm=dcfg.get("max_spread_cm", 5.0)),
        contour=target,
    )
    return result


def draw(frame, res):
    """원본 위에 영상 중심(흰 십자), 컨투어(초록), 목표 중심(빨강), 수치 표시"""
    out = frame.copy()
    H, W = out.shape[:2]
    cv2.drawMarker(out, (W // 2, H // 2), (255, 255, 255), cv2.MARKER_CROSS, 30, 2)

    if res["found"]:
        cv2.drawContours(out, [res["contour"]], -1, (0, 255, 0), 2)
        c = (int(res["cx"]), int(res["cy"]))
        cv2.circle(out, c, 6, (0, 0, 255), -1)
        cv2.line(out, (W // 2, H // 2), c, (0, 0, 255), 1)
        text = f"ex={res['ex']:+.3f} ey={res['ey']:+.3f} z={res['z']:.4f}"
        color = (0, 255, 0)
    else:
        text = "NOT DETECTED (z=0)"
        color = (0, 0, 255)
    dist = "--" if res["dist_cm"] is None else f"{res['dist_cm']:.0f} cm"
    cv2.putText(out, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    cv2.putText(out, f"candidates={res['n_candidates']}  dist={dist}", (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return out