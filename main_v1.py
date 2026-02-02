import cv2
import threading
import time
import numpy as np

# IP của ESP32-CAM
URL = "http://172.20.10.2/stream"

class VideoStream:
    def __init__(self, src=0):
        self.stream = cv2.VideoCapture(src)
        self.grabbed, self.frame = self.stream.read()
        self.stopped = False
        self.lock = threading.Lock()
        threading.Thread(target=self.update, args=()).start()

    def update(self):
        while not self.stopped:
            if not self.stream.isOpened(): continue
            grabbed, frame = self.stream.read()
            if grabbed:
                with self.lock:
                    self.grabbed = grabbed
                    self.frame = frame
            else:
                self.stream.release()
                time.sleep(1)
                self.stream.open(URL)

    def read(self):
        with self.lock:
            return self.frame

    def stop(self):
        self.stopped = True
        self.stream.release()

# --- HÀM XỬ LÝ NÉ VẬT CẢN ---
def process_obstacle(frame):
    # 1. Cắt bỏ phần trên của ảnh (trần nhà, đèn) để tránh nhiễu
    # Giữ lại phần dưới để nhìn sàn và vật cản thấp
    height, width = frame.shape[:2]
    roi = frame[int(height/3):, :] # Cắt bỏ 1/3 phía trên
    
    # 2. Chuyển xám và làm mờ (Quan trọng với ảnh chất lượng thấp)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0) 

    # 3. Tách biên (Canny)
    # Ngưỡng (50, 150) cần tinh chỉnh tùy ánh sáng phòng bạn
    edges = cv2.Canny(blurred, 50, 150)

    # 4. Chia 3 vùng: Trái, Giữa, Phải
    w_zone = width // 3
    left_zone = edges[:, :w_zone]
    center_zone = edges[:, w_zone:2*w_zone]
    right_zone = edges[:, 2*w_zone:]

    # 5. Đếm số lượng điểm trắng (pixel cạnh)
    left_score = cv2.countNonZero(left_zone)
    center_score = cv2.countNonZero(center_zone)
    right_score = cv2.countNonZero(right_zone)

    # Ngưỡng cảnh báo (cần chỉnh tùy thực tế)
    THRESHOLD = 100 

    command = "DI THANG"
    color = (0, 255, 0) # Xanh lá

    # Logic điều khiển đơn giản
    if center_score > THRESHOLD:
        command = "DUNG LAI / LUI"
        color = (0, 0, 255) # Đỏ
    elif left_score > THRESHOLD and right_score > THRESHOLD:
         command = "KET KET -> LUI"
         color = (0, 0, 255)
    elif left_score > THRESHOLD:
        command = "RE PHAI >>"
        color = (0, 255, 255) # Vàng
    elif right_score > THRESHOLD:
        command = "<< RE TRAI"
        color = (0, 255, 255)
    
    return edges, command, color, (left_score, center_score, right_score)

# --- MAIN ---
vs = VideoStream(URL)
time.sleep(2.0)

print("Bắt đầu xử lý...")

while True:
    frame = vs.read()
    if frame is None: continue

    # Xử lý thuật toán
    edges_img, cmd, cmd_color, scores = process_obstacle(frame)

    # --- HIỂN THỊ (VISUALIZATION) ---
    # Phóng to ảnh gốc để xem
    display_frame = cv2.resize(frame, (480, 360))
    
    # Vẽ thông số lên màn hình
    cv2.putText(display_frame, f"L:{scores[0]} C:{scores[1]} R:{scores[2]}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(display_frame, cmd, (10, 340),
                cv2.FONT_HERSHEY_SIMPLEX, 1, cmd_color, 3)

    # Hiển thị ảnh biên (Edges) để debug xem Canny có bắt đúng không
    display_edges = cv2.resize(edges_img, (480, 240)) # Ảnh này lùn hơn vì đã cắt 1/3

    cv2.imshow("Camera View", display_frame)
    cv2.imshow("Thuat toan Canny", display_edges)

    if cv2.waitKey(1) == ord('q'):
        break

vs.stop()
cv2.destroyAllWindows()
