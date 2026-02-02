import cv2
import threading
import time
import numpy as np
import requests # Thư viện gửi lệnh HTTP

# ===== CẤU HÌNH MẠNG =====
# 1. IP Camera (ESP32-CAM) - Giữ nguyên của bạn
CAM_URL = "http://192.168.1.14/stream" 

# 2. IP Xe Robot (ESP8266) - Đã cập nhật đúng IP mới
ROBOT_IP = "http://192.168.1.26" 

# --- HÀM GỬI LỆNH ĐIỀU KHIỂN (ĐÃ TỐI ƯU CHỐNG LAG) ---
last_cmd = ""
last_sent_time = 0 # Biến để giới hạn tốc độ gửi

def send_robot_command(cmd_name):
    global last_cmd, last_sent_time
    curr_time = time.time()

    # 1. Nếu lệnh GIỐNG lệnh cũ -> KHÔNG gửi lại (trừ khi quá lâu rồi)
    if cmd_name == last_cmd and (curr_time - last_sent_time < 1.0):
        return
    
    # 2. GIỚI HẠN TỐC ĐỘ: Chỉ gửi tối đa 4 lệnh/giây (cách nhau 0.25s)
    # Để tránh làm ESP8266 bị "ngộp" và treo
    if curr_time - last_sent_time < 0.25:
        return
    
    last_cmd = cmd_name
    last_sent_time = curr_time
    
    # Tạo luồng riêng để gửi lệnh
    def _send():
        try:
            # [QUAN TRỌNG] Tăng timeout lên 0.5s (0.1s là quá nhanh, robot không kịp trả lời)
            url = f"{ROBOT_IP}/{cmd_name}"
            requests.get(url, timeout=0.5) 
            print(f">>> Gửi thành công: {cmd_name}")
        except requests.exceptions.RequestException:
            # Lỗi mạng thì kệ nó, đừng in ra nhiều quá rối mắt
            pass 

    threading.Thread(target=_send).start()

# --- BIẾN TOÀN CỤC MÀU SẮC ---
calibrated = False        
floor_lower = None        
floor_upper = None        
frame_hsv = None

def select_floor_color(event, x, y, flags, param):
    global calibrated, floor_lower, floor_upper, frame_hsv
    if event == cv2.EVENT_LBUTTONDOWN:
        target_color = frame_hsv[y, x]
        print(f"Màu sàn đã chọn: {target_color}")
        # Tăng phạm vi nhận diện màu lên để robot dễ đi hơn
        tolerance = np.array([40, 80, 100]) 
        floor_lower = np.clip(target_color - tolerance, 0, 255)
        floor_upper = np.clip(target_color + tolerance, 0, 255)
        calibrated = True

class VideoStream:
    def __init__(self, src=0):
        self.stream = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
        self.stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.grabbed, self.frame = self.stream.read()
        self.stopped = False
        self.lock = threading.Lock()
        
    def start(self):
        threading.Thread(target=self.update, args=()).start()
        return self

    def update(self):
        while not self.stopped:
            if not self.stream.isOpened():
                time.sleep(0.1)
                continue
            grabbed, frame = self.stream.read()
            if grabbed:
                with self.lock:
                    self.grabbed = grabbed
                    self.frame = frame
            else:
                self.stream.release()
                time.sleep(1)
                self.stream.open(CAM_URL)

    def read(self):
        with self.lock:
            return self.frame

    def stop(self):
        self.stopped = True
        self.stream.release()

# --- MAIN ---
print("Đang kết nối Camera...")
vs = VideoStream(CAM_URL).start()
time.sleep(2.0)

cv2.namedWindow("Robot View")
cv2.setMouseCallback("Robot View", select_floor_color)

print(f"Hệ thống sẵn sàng. Kết nối Robot tại {ROBOT_IP}")
print("Click chuột vào SÀN NHÀ để robot bắt đầu chạy!")

while True:
    frame = vs.read()
    if frame is None: continue

    process_frame = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_LINEAR)
    blurred = cv2.GaussianBlur(process_frame, (11, 11), 0)
    frame_hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    cmd_display = "DUNG IM (CHO LENH)"
    color_display = (0, 0, 255)
    
    # Biến lưu lệnh gửi xuống xe
    robot_action = "stop" 

    if calibrated:
        mask = cv2.inRange(frame_hsv, floor_lower, floor_upper)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=2) 
        mask = cv2.erode(mask, kernel, iterations=1)

        h, w = mask.shape
        roi_h = int(h * 0.6) 
        roi = mask[h - roi_h:h, :] 
        
        w_third = w // 3
        left_zone = roi[:, :w_third]
        center_zone = roi[:, w_third : 2*w_third]
        right_zone = roi[:, 2*w_third:]
        
        total_pixels = roi_h * w_third
        left_r = cv2.countNonZero(left_zone) / total_pixels
        center_r = cv2.countNonZero(center_zone) / total_pixels
        right_r = cv2.countNonZero(right_zone) / total_pixels
        
        # Ngưỡng an toàn (Có thể tăng lên 0.3 nếu robot quá liều lĩnh)
        SAFE_THRESHOLD = 0.25 
        
        # --- LOGIC ĐIỀU KHIỂN XE ---
        if center_r < SAFE_THRESHOLD: 
            # Giữa bị chặn -> Phải rẽ
            if left_r > right_r and left_r > SAFE_THRESHOLD:
                cmd_display = "<< NE TRAI"
                color_display = (0, 0, 255)
                robot_action = "left" 
            elif right_r > left_r and right_r > SAFE_THRESHOLD:
                cmd_display = "NE PHAI >>"
                color_display = (0, 0, 255)
                robot_action = "right" 
            else:
                cmd_display = "KET DUONG (LUI)"
                color_display = (0, 0, 255)
                robot_action = "back" 
        else:
            # Đường giữa thoáng
            if left_r > 0.7 and right_r > 0.7:
                cmd_display = "DI THANG ^"
                color_display = (0, 255, 0)
                robot_action = "forward"
            elif left_r > right_r + 0.2:
                cmd_display = "< CHINH TRAI"
                color_display = (0, 255, 255)
                robot_action = "left" 
            elif right_r > left_r + 0.2:
                cmd_display = "CHINH PHAI >"
                color_display = (0, 255, 255)
                robot_action = "right" 
            else:
                cmd_display = "DI THANG ^"
                color_display = (0, 255, 0)
                robot_action = "forward"
                
        # --- GỬI LỆNH XUỐNG ESP8266 ---
        send_robot_command(robot_action)

        # Vẽ Visualization 
        color_L = (0, 255, 0) if left_r > SAFE_THRESHOLD else (0, 0, 255)
        cv2.rectangle(process_frame, (0, h-roi_h), (w_third, h), color_L, 2)
        
        color_C = (0, 255, 0) if center_r > SAFE_THRESHOLD else (0, 0, 255)
        cv2.rectangle(process_frame, (w_third, h-roi_h), (2*w_third, h), color_C, 2)

        color_R = (0, 255, 0) if right_r > SAFE_THRESHOLD else (0, 0, 255)
        cv2.rectangle(process_frame, (2*w_third, h-roi_h), (w, h), color_R, 2)
        
        cv2.imshow("Mask", mask)

    cv2.putText(process_frame, cmd_display, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, color_display, 3)
    cv2.imshow("Robot View", process_frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'): 
        send_robot_command("stop") 
        break
    elif key == ord('r'): 
        calibrated = False
        send_robot_command("stop") 

vs.stop()
cv2.destroyAllWindows()
