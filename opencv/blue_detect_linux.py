import cv2
import numpy as np

# HSV 범위 (OpenCV의 H는 0~179, 파랑은 약 100~130)
LOWER_BLUE = np.array([90, 80, 40])
UPPER_BLUE = np.array([135, 255, 255])
MIN_AREA = 500  # 너무 작은 노이즈 무시

cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
if not cap.isOpened():
    raise SystemExit("웹캠을 열 수 없습니다.")

kernel = np.ones((5, 5), np.uint8)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    blurred = cv2.GaussianBlur(frame, (7, 7), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, LOWER_BLUE, UPPER_BLUE)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        if cv2.contourArea(c) < MIN_AREA:
            continue
        x, y, w, h = cv2.boundingRect(c)
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
        cv2.putText(frame, "Blue", (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

    result = cv2.bitwise_and(frame, frame, mask=mask)
    cv2.imshow("Blue Detection", frame)
    cv2.imshow("Mask", mask)
    cv2.imshow("Result", result)

    if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
        break

cap.release()
cv2.destroyAllWindows()
