import customtkinter as ctk
from PIL import Image
import cv2
import threading
import time
import numpy as np
import requests

# ===== CẤU HÌNH IP (SỬA LẠI NẾU CẦN) =====
CAM_URL = "http://10.42.0.151/stream"
ROBOT_IP = "http://10.42.0.31"

# ===== GIAO DIỆN CONFIG =====
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class RobotControllerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- CẤU HÌNH CỬA SỔ ---
        self.title("ROBOT AI DASHBOARD - SYSTEM MONITOR")
        self.geometry("1100x700")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- BIẾN HỆ THỐNG ---
        self.floor_lower = None
        self.floor_upper = None
        self.calibrated = False
        self.frame_hsv = None
        
        self.last_cmd = ""
        self.last_sent_time = 0
        self.view_mode = "Real"
        
        # Biến trạng thái kết nối
        self.cam_connected = False
        self.robot_connected = False

        # --- [1] CỘT TRÁI: ĐIỀU KHIỂN & TRẠNG THÁI ---
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)

        # Tiêu đề
        ctk.CTkLabel(self.sidebar, text="SYSTEM STATUS", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10))

        # --- KHUNG TRẠNG THÁI KẾT NỐI (MỚI) ---
        self.status_frame = ctk.CTkFrame(self.sidebar, fg_color="#2b2b2b")
        self.status_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        # Đèn báo Camera
        self.lbl_cam_status = ctk.CTkLabel(self.status_frame, text="● CAMERA: CHECKING...", font=ctk.CTkFont(size=14, weight="bold"), text_color="gray")
        self.lbl_cam_status.pack(pady=5, padx=10, anchor="w")
        
        # Đèn báo Robot
        self.lbl_robot_status = ctk.CTkLabel(self.status_frame, text="● ESP8266: CHECKING...", font=ctk.CTkFont(size=14, weight="bold"), text_color="gray")
        self.lbl_robot_status.pack(pady=5, padx=10, anchor="w")

        # --- NÚT ĐIỀU KHIỂN ---
        ctk.CTkLabel(self.sidebar, text="CONTROLS", font=ctk.CTkFont(size=20, weight="bold")).grid(row=2, column=0, padx=20, pady=(20, 10))

        self.btn_reset = ctk.CTkButton(self.sidebar, text="CHỌN LẠI MÀU (R)", command=self.reset_calibration, fg_color="#c0392b", hover_color="#e74c3c")
        self.btn_reset.grid(row=3, column=0, padx=20, pady=10)

        self.switch_view = ctk.CTkSwitch(self.sidebar, text="Chế độ MASK (Debug)", command=self.toggle_view)
        self.switch_view.grid(row=4, column=0, padx=20, pady=10)

        # Thanh cảm biến
        self.create_sensor_bar("LEFT SENSOR", 5)
        self.create_sensor_bar("CENTER SENSOR", 7)
        self.create_sensor_bar("RIGHT SENSOR", 9)

        # Lệnh hiện tại
        ctk.CTkLabel(self.sidebar, text="COMMAND:", font=ctk.CTkFont(size=14)).grid(row=11, column=0, padx=20, pady=(10,0))
        self.lbl_cmd = ctk.CTkLabel(self.sidebar, text="WAITING...", font=ctk.CTkFont(size=24, weight="bold"), text_color="#f1c40f")
        self.lbl_cmd.grid(row=12, column=0, padx=20, pady=(0, 20))

        # --- [2] CỘT PHẢI: MÀN HÌNH CAMERA ---
        self.video_frame = ctk.CTkFrame(self, corner_radius=10)
        self.video_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        self.lbl_video = ctk.CTkLabel(self.video_frame, text="ĐANG TÌM TÍN HIỆU...", font=ctk.CTkFont(size=20))
        self.lbl_video.pack(expand=True, fill="both", padx=10, pady=10)
        self.lbl_video.bind("<Button-1>", self.on_mouse_click)

        # --- KHỞI ĐỘNG LUỒNG ---
        self.vs = VideoStream(CAM_URL).start()
        
        # Bắt đầu vòng lặp cập nhật giao diện
        self.update_gui() 
        
        # Bắt đầu luồng kiểm tra kết nối ngầm (Chạy riêng để không lag GUI)
        threading.Thread(target=self.connection_monitor, daemon=True).start()

    def create_sensor_bar(self, name, row):
        lbl = ctk.CTkLabel(self.sidebar, text=name, anchor="w", font=ctk.CTkFont(size=12))
        lbl.grid(row=row, column=0, padx=20, pady=(10, 0), sticky="w")
        bar = ctk.CTkProgressBar(self.sidebar, orientation="horizontal")
        bar.grid(row=row+1, column=0, padx=20, pady=(0, 5), sticky="ew")
        bar.set(0)
        if "LEFT" in name: self.bar_left = bar
        elif "CENTER" in name: self.bar_center = bar
        elif "RIGHT" in name: self.bar_right = bar

    # --- [NEW] HÀM KIỂM TRA KẾT NỐI (CHẠY NGẦM) ---
    def connection_monitor(self):
        while True:
            # 1. Check ESP8266 Robot (Ping trang chủ /)
            try:
                # Gửi request nhẹ, timeout cực ngắn
                requests.get(ROBOT_IP, timeout=0.5)
                self.robot_connected = True
            except:
                self.robot_connected = False

            # Cập nhật UI từ luồng chính (tránh lỗi Thread)
            self.after(0, self.update_connection_ui)
            
            # Nghỉ 2 giây rồi check lại
            time.sleep(2.0)

    def update_connection_ui(self):
        # Update UI Robot
        if self.robot_connected:
            self.lbl_robot_status.configure(text="● ESP8266: ONLINE", text_color="#2ecc71") # Xanh
        else:
            self.lbl_robot_status.configure(text="● ESP8266: OFFLINE", text_color="#e74c3c") # Đỏ

        # Update UI Camera (Dựa vào việc có nhận được frame hay không)
        if self.cam_connected:
            self.lbl_cam_status.configure(text="● CAMERA: ONLINE", text_color="#2ecc71")
        else:
            self.lbl_cam_status.configure(text="● CAMERA: OFFLINE", text_color="#e74c3c")

    # --- LOGIC XỬ LÝ ẢNH & GUI ---
    def update_gui(self):
        frame = self.vs.read()
        
        if frame is not None:
            self.cam_connected = True # Đánh dấu camera đang sống
            
            # Resize
            self.display_h = 480
            self.display_w = 640
            process_frame = cv2.resize(frame, (self.display_w, self.display_h), interpolation=cv2.INTER_LINEAR)
            
            blurred = cv2.GaussianBlur(process_frame, (11, 11), 0)
            self.frame_hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
            
            final_image = process_frame
            cmd_text = "CHUA CHON MAU"
            cmd_color = "#95a5a6"

            if self.calibrated:
                # --- CORE ALGORITHM ---
                mask = cv2.inRange(self.frame_hsv, self.floor_lower, self.floor_upper)
                kernel = np.ones((5, 5), np.uint8)
                mask = cv2.dilate(mask, kernel, iterations=2)
                mask = cv2.erode(mask, kernel, iterations=1)
                
                h, w = mask.shape
                roi_h = int(h * 0.6)
                roi = mask[h - roi_h:h, :]
                w_third = w // 3
                
                # Tính toán
                total = roi_h * w_third
                left_r = cv2.countNonZero(roi[:, :w_third]) / total
                center_r = cv2.countNonZero(roi[:, w_third : 2*w_third]) / total
                right_r = cv2.countNonZero(roi[:, 2*w_third:]) / total

                # Update Progress Bar
                self.bar_left.set(left_r)
                self.bar_center.set(center_r)
                self.bar_right.set(right_r)
                
                self.bar_center.configure(progress_color="#e74c3c" if center_r < 0.25 else "#2ecc71")

                # Decision Tree
                SAFE = 0.5
                action = "stop"
                
                # Chỉ gửi lệnh nếu Robot đang ONLINE (để tránh spam khi mất mạng)
                if self.robot_connected:
                    if center_r < SAFE:
                        if left_r > right_r and left_r > SAFE:
                            cmd_text = "NE TRAI <<"
                            action = "left"
                            cmd_color = "#e74c3c"
                        elif right_r > left_r and right_r > SAFE:
                            cmd_text = "NE PHAI >>"
                            action = "right"
                            cmd_color = "#e74c3c"
                        else:
                            cmd_text = "LUI GAP!"
                            action = "back"
                            cmd_color = "#c0392b"
                    else:
                        if left_r > 0.7 and right_r > 0.7:
                            cmd_text = "DI THANG"
                            action = "forward"
                            cmd_color = "#2ecc71"
                        elif left_r > right_r + 0.2:
                            cmd_text = "CHINH TRAI <"
                            action = "left"
                            cmd_color = "#f1c40f"
                        elif right_r > left_r + 0.2:
                            cmd_text = "CHINH PHAI >"
                            action = "right"
                            cmd_color = "#f1c40f"
                        else:
                            cmd_text = "DI THANG"
                            action = "forward"
                            cmd_color = "#2ecc71"
                    
                    self.send_command(action)
                else:
                    cmd_text = "MAT KET NOI ROBOT"
                    cmd_color = "#7f8c8d"

                self.lbl_cmd.configure(text=cmd_text, text_color=cmd_color)

                if self.view_mode == "Mask":
                    final_image = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
                else:
                    self.draw_debug_box(final_image, left_r, 0, w_third, h, roi_h)
                    self.draw_debug_box(final_image, center_r, w_third, 2*w_third, h, roi_h)
                    self.draw_debug_box(final_image, right_r, 2*w_third, w, h, roi_h)
            
            # Hiển thị ảnh
            if len(final_image.shape) == 2:
                img = Image.fromarray(final_image)
            else:
                img = Image.fromarray(cv2.cvtColor(final_image, cv2.COLOR_BGR2RGB))
            
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(self.display_w, self.display_h))
            self.lbl_video.configure(text="", image=ctk_img)
        else:
            self.cam_connected = False # Mất tín hiệu camera
            self.lbl_video.configure(text="MẤT TÍN HIỆU CAMERA...", image=None)

        self.after(30, self.update_gui)

    def draw_debug_box(self, img, ratio, x1, x2, h, roi_h):
        color = (0, 255, 0) if ratio > 0.25 else (0, 0, 255)
        cv2.rectangle(img, (x1, h-roi_h), (x2, h), color, 2)

    def on_mouse_click(self, event):
        x, y = event.x, event.y
        if self.frame_hsv is not None and 0 <= x < self.display_w and 0 <= y < self.display_h:
            target = self.frame_hsv[y, x]
            tolerance = np.array([40, 80, 100])
            self.floor_lower = np.clip(target - tolerance, 0, 255)
            self.floor_upper = np.clip(target + tolerance, 0, 255)
            self.calibrated = True
            self.lbl_cmd.configure(text="DA CALIB", text_color="#2ecc71")

    def reset_calibration(self):
        self.calibrated = False
        self.lbl_cmd.configure(text="DUNG (RESET)", text_color="#95a5a6")
        self.send_command("stop")

    def toggle_view(self):
        self.view_mode = "Mask" if self.switch_view.get() == 1 else "Real"

    def send_command(self, cmd_name):
        curr_time = time.time()
        # Logic gửi lệnh chống spam
        if cmd_name == self.last_cmd and (curr_time - self.last_sent_time < 1.0): return
        if curr_time - self.last_sent_time < 0.25: return
        
        self.last_cmd = cmd_name
        self.last_sent_time = curr_time
        threading.Thread(target=lambda: self._request(cmd_name)).start()

    def _request(self, cmd):
        try: requests.get(f"{ROBOT_IP}/{cmd}", timeout=0.5)
        except: pass

    def on_close(self):
        self.vs.stop()
        self.destroy()

# ===== CLASS VIDEO STREAM (GIỮ NGUYÊN) =====
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
                time.sleep(0.1); continue
            grabbed, frame = self.stream.read()
            if grabbed:
                with self.lock:
                    self.grabbed = grabbed
                    self.frame = frame
            else:
                self.stream.release(); time.sleep(1); self.stream.open(CAM_URL)

    def read(self):
        with self.lock: return self.frame

    def stop(self):
        self.stopped = True
        self.stream.release()

if __name__ == "__main__":
    app = RobotControllerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
