import cv2
import threading
import time

# URL = "http://172.20.10.2/stream" 
URL = "http://192.168.1.3/stream" 

class VideoStream:
    def __init__(self, src=0):
        self.stream = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
        self.stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        self.grabbed, self.frame = self.stream.read()
        self.stopped = False
        self.lock = threading.Lock()
        self.frame_count = 0 

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
                    self.frame_count += 1
            else:
                self.stream.release()
                time.sleep(1)
                self.stream.open(URL)

    def read(self):
        with self.lock:
            return self.frame, self.frame_count

    def stop(self):
        self.stopped = True
        self.stream.release()

# --- MAIN PROGRAM ---
vs = VideoStream(URL).start()
print("Đang khởi động stream...")
time.sleep(2.0)

last_processed_frame_id = -1 

# --- BIẾN ĐỂ TÍNH FPS TRUNG BÌNH ---
fps_start_time = time.time()
fps_frame_counter = 0
fps_display = "FPS: 0" # Biến lưu chữ hiển thị FPS (không cập nhật liên tục)

while True:
    frame, current_frame_id = vs.read()

    # Nếu không có ảnh mới thì bỏ qua
    if frame is None or current_frame_id == last_processed_frame_id:
        time.sleep(0.001) 
        continue

    last_processed_frame_id = current_frame_id

    # --- TÍNH TOÁN FPS (Cập nhật 0.5 giây một lần) ---
    fps_frame_counter += 1
    if (time.time() - fps_start_time) > 0.5: # Sau mỗi 0.5 giây mới tính lại
        fps = fps_frame_counter / (time.time() - fps_start_time)
        fps_display = f"FPS: {int(fps)}"
        
        # Reset lại bộ đếm
        fps_frame_counter = 0
        fps_start_time = time.time()

    # --- XỬ LÝ ẢNH ---
    # [NÂNG CẤP]: Đổi sang INTER_LINEAR
    # Vì bạn đã tăng chất lượng ảnh ở ESP32, nên dùng Linear để ảnh mịn hơn, 
    # không bị vỡ hạt như pixel art (Nearest). Laptop dư sức xử lý cái này.
    frame_large = cv2.resize(frame, (640, 480), interpolation=cv2.INTER_LINEAR)

    # Vẽ FPS (Dùng biến fps_display đã lưu trữ)
    cv2.putText(frame_large, fps_display, (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("ESP32 Smooth Stream", frame_large)

    if cv2.waitKey(1) == ord('q'):
        break

vs.stop()
cv2.destroyAllWindows()
