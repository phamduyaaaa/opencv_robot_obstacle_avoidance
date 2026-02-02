import cv2
import numpy as np

cap = cv2.VideoCapture(0)
ret, prev = cap.read()
prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    flow = cv2.calcOpticalFlowFarneback(
        prev_gray, gray, None,
        0.5, 3, 15, 3, 5, 1.2, 0
    )

    mag, ang = cv2.cartToPolar(flow[...,0], flow[...,1])

    h, w = mag.shape
    left   = mag[:, :w//3]
    center = mag[:, w//3:2*w//3]
    right  = mag[:, 2*w//3:]

    sum_l = np.sum(left)
    sum_c = np.sum(center)
    sum_r = np.sum(right)

    if sum_c > 1.5 * max(sum_l, sum_r):
        if sum_l < sum_r:
            decision = "TURN LEFT"
        else:
            decision = "TURN RIGHT"
    else:
        decision = "GO FORWARD"

    print(decision)

    prev_gray = gray

    cv2.imshow("frame", frame)
    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()

