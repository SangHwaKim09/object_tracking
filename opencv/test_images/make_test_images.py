"""
색 검출 인식률 테스트용 예제 이미지 생성기

test2.jpg처럼 배경 위에 단색 도형을 그린 이미지를 50장 만들고,
각 도형의 정답(색, 모양, 위치)을 labels.csv에 저장합니다.

- 색 17가지, 모양 11가지를 섞어서 배치 (모든 이미지에 blue, orange 포함, 일부 예외)
- 조명: 보통 / 아주 밝음(과노출, 눈부심) / 어두움(거의 빛이 없음까지) / 불균일(그림자, 스포트라이트)
- 그 외: 비슷한 색끼리, 크기 변화, 노이즈·흐림, 배경 변화

실행: ../../.venv/bin/python make_test_images.py
(시드가 고정되어 있어서 다시 실행해도 같은 이미지가 만들어짐)
"""
import csv
from pathlib import Path

import cv2
import numpy as np

# ──────────────────────────────────────────────
# 설정값
# ──────────────────────────────────────────────
OUT_DIR = Path(__file__).resolve().parent
W, H = 640, 480        # RealSense 컬러 영상과 같은 크기
SEED = 2026            # 같은 시드 → 항상 같은 이미지
JPEG_QUALITY = 95

# 색 이름: (R, G, B)  ※ 사람이 읽기 쉬운 RGB로 적고, 그릴 때 OpenCV 순서(BGR)로 바꿈
COLORS = {
    "red": (220, 20, 30),
    "orange": (255, 128, 0),
    "yellow": (255, 225, 0),
    "lime": (160, 220, 30),
    "green": (40, 160, 60),
    "teal": (0, 140, 130),
    "cyan": (0, 200, 220),
    "sky_blue": (110, 180, 240),
    "blue": (0, 80, 200),
    "navy": (20, 30, 100),
    "purple": (120, 40, 190),
    "magenta": (220, 0, 180),
    "pink": (245, 130, 170),
    "brown": (130, 75, 30),
    "white": (250, 250, 250),
    "gray": (128, 128, 128),
    "black": (25, 25, 25),
}
SHAPES = ["circle", "square", "rectangle", "ellipse", "triangle", "pentagon",
          "hexagon", "star", "cross", "ring", "heart"]
COLOR_JITTER = 12      # 실제 물체처럼 색을 조금씩 다르게 (각 채널 ±12)

rng = np.random.default_rng(SEED)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)   # 조명 효과 계산용 좌표


# ──────────────────────────────────────────────
# 도형 그리기
# ──────────────────────────────────────────────
def rect(w, h):
    return np.array([(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)])


def regular_polygon(n, r):
    t = -np.pi / 2 + np.arange(n) * 2 * np.pi / n
    return np.stack([r * np.cos(t), r * np.sin(t)], 1)


def star(r, inner=0.45, n=5):
    t = -np.pi / 2 + np.arange(2 * n) * np.pi / n
    rr = np.where(np.arange(2 * n) % 2 == 0, r, r * inner)   # 바깥 꼭짓점, 안쪽 꼭짓점 번갈아
    return np.stack([rr * np.cos(t), rr * np.sin(t)], 1)


def cross(r, arm=0.35):
    a = r * arm
    return np.array([(-a, -r), (a, -r), (a, -a), (r, -a), (r, a), (a, a),
                     (a, r), (-a, r), (-a, a), (-r, a), (-r, -a), (-a, -a)])


def heart(r):
    t = np.linspace(0, 2 * np.pi, 60, endpoint=False)
    x = 16 * np.sin(t) ** 3
    y = -(13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t))
    return np.stack([x, y], 1) * (r / 17)


POLYGONS = {
    "square": lambda s, r: rect(s * 0.8, s * 0.8),
    "rectangle": lambda s, r: rect(s, s * 0.55),
    "triangle": lambda s, r: regular_polygon(3, r),
    "pentagon": lambda s, r: regular_polygon(5, r),
    "hexagon": lambda s, r: regular_polygon(6, r),
    "star": lambda s, r: star(r),
    "cross": lambda s, r: cross(r),
    "heart": lambda s, r: heart(r),
}


def shape_alpha(shape, cx, cy, s, angle):
    """도형 하나를 그린 0~1 마스크 (가장자리는 부드럽게). s = 대략적인 지름(px)"""
    m = np.zeros((H, W), np.uint8)
    r = s / 2
    if shape == "circle":
        cv2.circle(m, (cx, cy), round(r), 255, -1, cv2.LINE_AA)
    elif shape == "ellipse":
        cv2.ellipse(m, (cx, cy), (round(r), round(r * 0.6)), angle, 0, 360, 255, -1, cv2.LINE_AA)
    elif shape == "ring":  # 가운데가 뚫린 원
        cv2.circle(m, (cx, cy), round(r), 255, -1, cv2.LINE_AA)
        cv2.circle(m, (cx, cy), round(r * 0.5), 0, -1, cv2.LINE_AA)
    else:  # 다각형은 꼭짓점을 회전시킨 뒤 채워서 그림
        th = np.deg2rad(angle)
        rot = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
        pts = POLYGONS[shape](s, r) @ rot.T + (cx, cy)
        cv2.fillPoly(m, [np.round(pts).astype(np.int32)], 255, cv2.LINE_AA)
    return m.astype(np.float32) / 255


def pick_colors(n, must=("blue", "orange"), pool=None):
    """반드시 넣을 색(must) + 나머지는 다른 색에서 골고루 뽑기"""
    pool = [c for c in (pool or COLORS) if c not in must]
    rest = rng.choice(pool, n - len(must), replace=n - len(must) > len(pool))
    return list(must) + [str(c) for c in rest]


def make_scene(colors, size_range=(60, 130), bg=(235, 235, 235)):
    """배경 위에 colors 순서대로 도형을 겹치지 않게 배치한다. → (이미지, 도형 정보 목록)"""
    if isinstance(bg, np.ndarray):
        img = bg.astype(np.float32).copy()
    else:
        img = np.full((H, W, 3), bg[::-1], np.float32)       # RGB → BGR
    occupied = np.zeros((H, W), np.uint8)                     # 이미 도형이 있는 자리
    gap = np.ones((15, 15), np.uint8)                         # 도형 사이 최소 간격 (~7px)
    objects = []
    for name in colors:
        for _ in range(300):                                  # 빈 자리를 찾을 때까지 시도
            s = int(rng.integers(size_range[0], size_range[1] + 1))
            shape = str(rng.choice(SHAPES))
            margin = s // 2 + 6
            cx = int(rng.integers(margin, W - margin))
            cy = int(rng.integers(margin, H - margin))
            alpha = shape_alpha(shape, cx, cy, s, float(rng.uniform(0, 360)))
            solid = (alpha > 0.5).astype(np.uint8)
            if not (cv2.dilate(solid, gap) & occupied).any():
                break
        else:
            continue                                          # 자리가 없으면 이 도형은 생략
        rgb = np.clip(np.array(COLORS[name]) + rng.integers(-COLOR_JITTER, COLOR_JITTER + 1, 3), 0, 255)
        a = alpha[..., None]
        img = img * (1 - a) + rgb[::-1].astype(np.float32) * a
        occupied |= cv2.dilate(solid, gap)
        objects.append({"color": name, "shape": shape, "rgb": rgb, "mask": solid.astype(bool)})
    return img, objects


# ──────────────────────────────────────────────
# 조명 / 화질 효과 (모두 float 이미지에 적용)
# ──────────────────────────────────────────────
def light(img, L):
    """조명 세기 L(숫자 또는 화면 위치별 지도)을 곱함. 1 = 보통, 2 = 두 배 밝게, 0.1 = 거의 깜깜"""
    return img * (L[..., None] if isinstance(L, np.ndarray) else L)


def gradient(start, end, direction):
    t = xx / (W - 1) if direction == "lr" else yy / (H - 1)
    return start + (end - start) * t


def spot(cx, cy, sigma):
    return np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma ** 2))


def noise(img, sigma):
    return img + rng.normal(0, sigma, img.shape)


def washed(img, a):
    """하얗게 날아간 느낌 (흰색과 섞기)"""
    return img * (1 - a) + 255 * a


def glare(img, cx, cy, sigma, strength):
    """강한 빛 반사 (해당 위치를 하얗게)"""
    return img + strength * spot(cx, cy, sigma)[..., None]


def cast(img, r, g, b):
    """조명 색 (예: 노란 전구, 푸른 밤빛)"""
    return img * np.array([b, g, r], np.float32)


def motion_blur(img, k, angle):
    kernel = np.zeros((k, k), np.float32)
    kernel[k // 2, :] = 1 / k
    rot = cv2.getRotationMatrix2D((k / 2 - 0.5, k / 2 - 0.5), angle, 1)
    kernel = cv2.warpAffine(kernel, rot, (k, k))
    return cv2.filter2D(img, -1, kernel / kernel.sum())


def jpeg(img, q):
    ok, buf = cv2.imencode(".jpg", np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, q])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR).astype(np.float32)


def shadow_band(strength=0.7, angle=30, width=110, soft=25):
    """대각선 그림자 띠"""
    th = np.deg2rad(angle)
    d = xx * np.cos(th) + yy * np.sin(th)
    c = float(rng.uniform(d.min() + width, d.max() - width))
    band = 1 / (1 + np.exp(-(d - (c - width / 2)) / soft)) - 1 / (1 + np.exp(-(d - (c + width / 2)) / soft))
    return 1 - strength * band


def texture_bg():
    """얼룩덜룩한 배경 (낮은 해상도 노이즈를 크게 늘림)"""
    small = rng.uniform(110, 210, (H // 40, W // 40, 3)).astype(np.float32)
    return cv2.resize(small, (W, H), interpolation=cv2.INTER_CUBIC)


# ──────────────────────────────────────────────
# 50장 구성: (폴더, 조건 이름, 장면 만들기, 효과 적용)
# ──────────────────────────────────────────────
def normal_scene():
    return make_scene(pick_colors(int(rng.integers(6, 10))), bg=(int(rng.integers(225, 241)),) * 3)


BLUE_FAMILY = ["navy", "sky_blue", "cyan", "purple", "teal"]
ORANGE_FAMILY = ["red", "yellow", "brown", "pink", "magenta"]
NO_TARGET = [c for c in COLORS if c not in ("blue", "orange")]

PLAN = (
    # 01 보통 조명 (10장)
    [("01_normal", "normal", normal_scene, lambda im: im)] * 10
    # 02 아주 밝은 조명 (8장): 과노출, 하얗게 날아감, 눈부신 반사
    + [
        ("02_bright", "gain1.4", normal_scene, lambda im: light(im, 1.4)),
        ("02_bright", "gain1.8", normal_scene, lambda im: light(im, 1.8)),
        ("02_bright", "washed30", normal_scene, lambda im: washed(im, 0.30)),
        ("02_bright", "washed55", normal_scene, lambda im: washed(im, 0.55)),
        ("02_bright", "glare", normal_scene, lambda im: glare(im, W * 0.5, H * 0.45, 90, 230)),
        ("02_bright", "glare_multi", normal_scene,
         lambda im: glare(glare(glare(im, 120, 120, 50, 220), 470, 160, 60, 220), 320, 380, 45, 220)),
        ("02_bright", "side_light", normal_scene, lambda im: light(im, gradient(0.9, 2.0, "lr"))),
        ("02_bright", "overexposed", normal_scene, lambda im: washed(light(im, 2.2), 0.2)),
    ]
    # 03 어두운 조명 (8장): 어두워질수록 카메라 잡음도 커짐, 마지막은 거의 빛이 없음
    + [
        ("03_dark", "x0.60", normal_scene, lambda im: light(im, 0.60)),
        ("03_dark", "x0.40", normal_scene, lambda im: noise(light(im, 0.40), 3)),
        ("03_dark", "x0.25_noise", normal_scene, lambda im: noise(light(im, 0.25), 6)),
        ("03_dark", "x0.15_noise", normal_scene, lambda im: noise(light(im, 0.15), 8)),
        ("03_dark", "x0.08_noise", normal_scene, lambda im: noise(light(im, 0.08), 8)),
        ("03_dark", "x0.04_nolight", normal_scene, lambda im: noise(light(im, 0.04), 5)),
        ("03_dark", "x0.25_warm_bulb", normal_scene, lambda im: noise(cast(light(im, 0.25), 1.2, 1.0, 0.6), 5)),
        ("03_dark", "x0.25_blue_night", normal_scene, lambda im: noise(cast(light(im, 0.25), 0.7, 0.9, 1.2), 5)),
    ]
    # 04 불균일한 조명 (6장): 한쪽만 밝음, 가장자리 어두움, 그림자
    + [
        ("04_uneven", "gradient_lr", normal_scene, lambda im: light(im, gradient(1.6, 0.25, "lr"))),
        ("04_uneven", "gradient_tb", normal_scene, lambda im: light(im, gradient(0.3, 1.5, "tb"))),
        ("04_uneven", "vignette", normal_scene, lambda im: light(im, 0.2 + 1.0 * spot(W / 2, H / 2, 220))),
        ("04_uneven", "spotlight", normal_scene, lambda im: light(im, 0.25 + 1.6 * spot(W * 0.4, H * 0.5, 120))),
        ("04_uneven", "shadow_band", normal_scene, lambda im: light(im, shadow_band())),
        ("04_uneven", "patchy_light", normal_scene,
         lambda im: light(im, 0.3 + 1.2 * np.maximum.reduce([spot(*rng.uniform((0, 0), (W, H)), 110) for _ in range(3)]))),
    ]
    # 05 비슷한 색끼리 (6장): 파랑 계열, 주황 계열, 목표 색이 아예 없는 이미지
    + [
        ("05_similar", "blue_family", lambda: make_scene(["blue"] + BLUE_FAMILY + ["blue"]), lambda im: im),
        ("05_similar", "blue_family_2", lambda: make_scene(["blue", "orange"] + BLUE_FAMILY), lambda im: im),
        ("05_similar", "orange_family", lambda: make_scene(["orange"] + ORANGE_FAMILY + ["orange"]), lambda im: im),
        ("05_similar", "orange_family_2", lambda: make_scene(["orange", "blue"] + ORANGE_FAMILY), lambda im: im),
        ("05_similar", "no_target", lambda: make_scene(pick_colors(8, must=(), pool=NO_TARGET)), lambda im: im),
        ("05_similar", "no_target_2", lambda: make_scene(pick_colors(8, must=(), pool=NO_TARGET)), lambda im: im),
    ]
    # 06 크기 (4장)
    + [
        ("06_size", "tiny_12px", lambda: make_scene(pick_colors(12), size_range=(12, 12)), lambda im: im),
        ("06_size", "small_25px", lambda: make_scene(pick_colors(10), size_range=(25, 25)), lambda im: im),
        ("06_size", "medium_40px", lambda: make_scene(pick_colors(10), size_range=(40, 40)), lambda im: im),
        ("06_size", "large_220px", lambda: make_scene(pick_colors(3), size_range=(200, 230)), lambda im: im),
    ]
    # 07 노이즈 / 흐림 (4장)
    + [
        ("07_noise_blur", "noise20", normal_scene, lambda im: noise(im, 20)),
        ("07_noise_blur", "blur15", normal_scene, lambda im: cv2.GaussianBlur(im, (15, 15), 0)),
        ("07_noise_blur", "motion_blur25", normal_scene, lambda im: motion_blur(im, 25, 20)),
        ("07_noise_blur", "jpeg_q8", normal_scene, lambda im: jpeg(im, 8)),
    ]
    # 08 배경 (4장)
    + [
        ("08_background", "white", lambda: make_scene(pick_colors(8), bg=(252, 252, 252)), lambda im: im),
        ("08_background", "black", lambda: make_scene(pick_colors(8), bg=(20, 20, 20)), lambda im: im),
        ("08_background", "bluish_gray", lambda: make_scene(pick_colors(8), bg=(175, 195, 225)), lambda im: im),
        ("08_background", "texture", lambda: make_scene(pick_colors(8), bg=texture_bg()), lambda im: im),
    ]
)


# ──────────────────────────────────────────────
# 생성 + 정답(labels.csv) 저장
# ──────────────────────────────────────────────
def main():
    rows = []
    counter = {}
    for folder, cond, scene_fn, effect in PLAN:
        clean, objects = scene_fn()
        final = np.clip(effect(clean), 0, 255).astype(np.uint8)

        counter[folder] = counter.get(folder, 0) + 1
        prefix = folder.split("_", 1)[1]
        name = f"{prefix}_{counter[folder]:02d}" + ("" if cond == "normal" else f"_{cond}") + ".jpg"
        (OUT_DIR / folder).mkdir(exist_ok=True)
        cv2.imwrite(str(OUT_DIR / folder / name), final, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])

        gray_clean = cv2.cvtColor(np.clip(clean, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
        gray_final = cv2.cvtColor(final, cv2.COLOR_BGR2GRAY).astype(np.float32)
        hsv_final = cv2.cvtColor(final, cv2.COLOR_BGR2HSV)
        for i, o in enumerate(objects, 1):
            m = o["mask"]
            x, y, w, h = cv2.boundingRect(m.astype(np.uint8))
            mo = cv2.moments(m.astype(np.uint8), binaryImage=True)
            hue, sat, val = cv2.cvtColor(np.uint8([[o["rgb"][::-1]]]), cv2.COLOR_BGR2HSV)[0, 0]
            fh, fs, fv = np.median(hsv_final[m], axis=0)
            rows.append({
                "file": f"{folder}/{name}", "category": folder, "condition": cond, "obj_id": i,
                "color": o["color"], "shape": o["shape"],
                "r": int(o["rgb"][0]), "g": int(o["rgb"][1]), "b": int(o["rgb"][2]),
                "hue": int(hue), "sat": int(sat), "val": int(val),
                "bbox_x": x, "bbox_y": y, "bbox_w": w, "bbox_h": h,
                "cx": round(mo["m10"] / mo["m00"]), "cy": round(mo["m01"] / mo["m00"]),
                "area_px": int(m.sum()),
                "brightness_ratio": round(float(gray_final[m].mean() / max(gray_clean[m].mean(), 1)), 2),
                "final_hue": int(fh), "final_sat": int(fs), "final_val": int(fv),
            })

    with open(OUT_DIR / "labels.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    n_images = sum(counter.values())
    print(f"이미지 {n_images}장, 도형 {len(rows)}개 → {OUT_DIR}")
    for folder, n in counter.items():
        print(f"  {folder}: {n}장")


if __name__ == "__main__":
    main()
