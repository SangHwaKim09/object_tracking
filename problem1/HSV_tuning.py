"""HSV 범위 튜너 (RealSense) — 트랙바로 조절하고 's'로 config에 저장, 'q'로 종료

실행: python HSV_tuning.py   (GUI 필요 → 노트북에서 실행)
※ 's'로 저장하면 Detector.yaml의 HSV 범위와 최소 크기 값만 바뀌고, 주석과 나머지 내용은 그대로 유지됨
"""
import os

import cv2
from ruamel.yaml import YAML  # 주석·순서·형식을 유지한 채 YAML 값을 고칠 수 있는 라이브러리

from Detector import CONFIG_PATH, RealSenseCamera, load_config, detect, draw

CFG_PATH = CONFIG_PATH
WIN = "tuner"

# Linux용 opencv-python에 들어 있는 Qt는 글꼴이 없어서 트랙바 이름이 표시되지 않음
# → 시스템 한글 글꼴 폴더를 알려줌 (cv2가 import될 때 이 값을 덮어쓰므로 반드시 import cv2 뒤에 설정)
KOREAN_FONT_DIR = "/usr/share/fonts/opentype/noto"  # Ubuntu 기본 한글 글꼴 (Noto Sans CJK)
if os.path.isdir(KOREAN_FONT_DIR):
    os.environ["QT_QPA_FONTDIR"] = KOREAN_FONT_DIR

# 트랙바: 코드에서 쓰는 이름 → 창에 보이는 이름 (창에는 "현재값/최댓값"도 함께 표시됨)
LABELS = {
    "H_min": "H 최소 (색상 시작)",
    "H_max": "H 최대 (색상 끝)",
    "S_min": "S 최소 (진하기 하한)",
    "S_max": "S 최대 (진하기 상한)",
    "V_min": "V 최소 (밝기 하한)",
    "V_max": "V 최대 (밝기 상한)",
    "area_x10000": "최소 크기 (화면의 1/10000)",
}


def nothing(_):
    pass


def save_config(path, hsv_range, min_area_ratio):
    """설정 파일에서 HSV 범위와 최소 크기 값만 바꿔 저장한다. (주석, 빈 줄, 나머지 항목은 그대로)

    튜너는 범위를 1개만 다루므로, 저장 후 범위는 1개가 된다. (기존 동작과 같음)
    """
    ry = YAML()                                   # 기본 모드(round-trip) = 주석과 형식 유지
    ry.indent(mapping=2, sequence=4, offset=2)    # Detector.yaml의 들여쓰기 모양 (  - lower: ...)
    with open(path, "r", encoding="utf-8") as f:
        data = ry.load(f)

    ranges = data["hsv"]["ranges"]
    ranges[0]["lower"][:] = hsv_range["lower"]    # 리스트 안의 숫자만 바꿔서 [a, b, c] 모양과 줄 끝 주석 유지
    ranges[0]["upper"][:] = hsv_range["upper"]
    del ranges[1:]
    data["min_area_ratio"] = min_area_ratio       # 줄 끝 주석은 그대로 남음

    with open(path, "w", encoding="utf-8") as f:
        ry.dump(data, f)


def main():
    cfg = load_config(CFG_PATH)
    cam = RealSenseCamera(cfg["camera"])

    lo, hi = cfg["hsv"]["ranges"][0]["lower"], cfg["hsv"]["ranges"][0]["upper"]
    cv2.namedWindow(WIN)
    for name, val, mx in [("H_min", lo[0], 179), ("H_max", hi[0], 179),
                          ("S_min", lo[1], 255), ("S_max", hi[1], 255),
                          ("V_min", lo[2], 255), ("V_max", hi[2], 255),
                          ("area_x10000", int(cfg["min_area_ratio"] * 10000), 500)]:
        cv2.createTrackbar(LABELS[name], WIN, val, mx, nothing)

    while True:
        ok, frame, depth = cam.read()
        if not ok:
            print("카메라 프레임을 못 읽음")
            break

        g = lambda n: cv2.getTrackbarPos(LABELS[n], WIN)
        cfg["hsv"]["ranges"] = [{"lower": [g("H_min"), g("S_min"), g("V_min")],
                                 "upper": [g("H_max"), g("S_max"), g("V_max")]}]
        cfg["min_area_ratio"] = g("area_x10000") / 10000

        res = detect(frame, cfg, depth, cam.depth_scale)
        mask_bgr = cv2.cvtColor(res["mask"], cv2.COLOR_GRAY2BGR)
        cv2.imshow(WIN, cv2.hconcat([draw(frame, res), mask_bgr]))

        key = cv2.waitKey(1) & 0xFF
        if key == ord("s"):
            save_config(CFG_PATH, cfg["hsv"]["ranges"][0], cfg["min_area_ratio"])
            print("저장:", cfg["hsv"]["ranges"], "min_area_ratio =", cfg["min_area_ratio"])
        elif key == ord("q"):
            break

    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()