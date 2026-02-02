import customtkinter as ctk
from PIL import Image
import cv2
import threading
import time
import numpy as np
import requests

# ===== 1. CẤU HÌNH MẠNG (Đã cập nhật theo IP của bạn) =====
CAM_URL = "http://10.42.0.114/stream"
ROBOT_IP = "http://10.42.0.31"

# ===== 2. CẤU HÌNH GIAO DIỆN =====
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class RobotControllerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- SETUP CỬA SỔ ---
        self.title("ROBOT AI COMMAND CENTER - v2.0 Stable")
        self.geometry("1100x700")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- BIẾN XỬ LÝ ẢNH ---
        self.floor_lower = None
        self.floor_upper = None
        self.calibrated = False
        self.frame_hsv = None
        
        self.last_cmd = ""
        self.last_sent_time = 0
        self.view_mode = "Real" # 'Real' hoặc 'Mask'
        
        # Biến trạng thái kết nối
        self.cam_connected = False
        self.robot_connected = False

        # --- GIAO DIỆN CỘT TRÁI (CONTROLS) ---
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)

        # Tiêu đề Status
        ctk.CTkLabel(self.sidebar, text="SYSTEM STATUS", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10))

        # Khung đèn báo trạng thái
        self.status_frame = ctk.CTkFrame(self.sidebar, fg_color="#2b2b2b")
        self.status_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        self.lbl_cam_status = ctk.CTkLabel(self.status_frame, text="● CAMERA: CHECKING...", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
        self.lbl_cam_status.pack(pady=5, padx=10, anchor="w")
        
        self.lbl_robot_status = ctk.CTkLabel(self.status_frame, text="● ESP8266: CHECKING...", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
        self.lbl_robot_status.pack(pady=5, padx=10, anchor="w")

        # Nút điều khiển
        ctk.CTkLabel(self.sidebar, text="CONTROLS", font=ctk.CTkFont(size=20, weight="bold")).grid(row=2, column=0, padx=20, pady=(20, 10))

        self.btn_reset = ctk.CTkButton(self.sidebar, text="RESET MÀU (R)", command=self.reset_calibration, fg_color="#c0392b", hover_color="#e74c3c")
        self.btn_reset.grid(row=3, column=0, padx=20, pady=10)

        self.switch_view = ctk.CTkSwitch(self.sidebar, text="Chế độ MASK (Debug)", command=self.toggle_view)
        self.switch_view.grid(row=4, column=0, padx=20, pady=10)

        # Hiển thị lệnh hiện tại
        ctk.CTkLabel(self.sidebar, text="CURRENT ACTION:", font=ctk.CTkFont(size=14)).grid(row=9, column=0, padx=20, pady=(10,0))
        self.lbl_cmd = ctk.CTkLabel(self.sidebar, text="WAITING...", font=ctk.CTkFont(size=24, weight="bold"), text_color="#f1c40f")
        self.lbl_cmd.grid(row=10, column=0, padx=20, pady=(0, 20))

        # --- GIAO DIỆN CỘT PHẢI (CAMERA) ---
        self.video_frame = ctk.CTkFrame(self, corner_radius=10)
        self.video_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        self.lbl_video = ctk.CTkLabel(self.video_frame, text="ĐANG KẾT NỐI CAMERA...", font=ctk.CTkFont(size=20))
        self.lbl_video.pack(expand=True, fill="both", padx=10, pady=10)
        self.lbl_video.bind("<Button-1>", self.on_mouse_click) # Click để chọn màu

        # --- KHỞI ĐỘNG HỆ THỐNG ---
        # 1. Start Stream Video
        self.vs = VideoStream(CAM_URL).start()
        
        # 2. Start Vòng lặp chính
        self.update_gui() 
        
        # 3. Start Luồng kiểm tra kết nối (Heartbeat)
        threading.Thread(target=self.connection_monitor, daemon=True).start()

    # --- HÀM KIỂM TRA KẾT NỐI (PING) ---
    def connection_monitor(self):
        while True:
            # Check Robot
            try:
                requests.get(ROBOT_IP, timeout=0.5)
                self.robot_connected = True
            except:
                self.robot_connected = False
            
            # Update đèn báo (chuyển về luồng chính)
            self.after(0, self.update_connection_ui)
            time.sleep(2.0)

    def update_connection_ui(self):
        if self.robot_connected:
            self.lbl_robot_status.configure(text="● ESP8266: ONLINE", text_color="#2ecc71")
        else:
            self.lbl_robot_status.configure(text="● ESP8266: OFFLINE", text_color="#e74c3c")

        if self.cam_connected:
            self.lbl_cam_status.configure(text="● CAMERA: ONLINE", text_color="#2ecc71")
        else:
            self.lbl_cam_status.configure(text="● CAMERA: OFFLINE", text_color="#e74c3c")

    # --- CORE ALGORITHM: XỬ LÝ ẢNH & RA QUYẾT ĐỊNH ---
    def update_gui(self):
        frame = self.vs.read()
        
        if frame is not None:
            self.cam_connected = True
            
            # Resize & Blur mạnh để giảm nhiễu hạt và bóng loáng
            self.display_h, self.display_w = 480, 640
            process_frame = cv2.resize(frame, (self.display_w, self.display_h), interpolation=cv2.INTER_LINEAR)
            blurred = cv2.GaussianBlur(process_frame, (15, 15), 0)
            self.frame_hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
            
            final_image = process_frame.copy()
            cmd_text = "CLICK CHUOT VAO SAN"
            cmd_color = "#95a5a6"

            if self.calibrated:
                # 1. Tạo Mask màu
                mask = cv2.inRange(self.frame_hsv, self.floor_lower, self.floor_upper)
                
                # 2. Xử lý Morphology (Quan trọng: Vá lỗ thủng do bóng đèn)
                kernel = np.ones((7, 7), np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
                mask = cv2.dilate(mask, kernel, iterations=2) # Nối liền đường đi
                
                # 3. Cắt ROI (Chỉ lấy 60% dưới)
                h, w = mask.shape
                roi_h = int(h * 0.75)
                roi = mask[h - roi_h:h, :] 
                
                # 4. Tìm Contours
                contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                action = "stop"
                path_found = False
                cx = -1 
                
                if len(contours) > 0:
                    # [TRÁNH HOẢNG LOẠN] Chỉ lấy vùng sàn LỚN NHẤT
                    c = max(contours, key=cv2.contourArea)
                    area = cv2.contourArea(c)
                    
                    # Chỉ đi nếu vùng sàn đủ lớn (>3000px)
                    if area > 3000:
                        path_found = True
                        
                        # Tính tâm (Centroid)
                        M = cv2.moments(c)
                        if M["m00"] != 0:
                            cx = int(M["m10"] / M["m00"])
                            cy = int(M["m01"] / M["m00"])
                            
                            # Vẽ Visualization (phải cộng offset Y vì đang dùng ROI)
                            shifted_contour = c + [0, h - roi_h] 
                            cv2.drawContours(final_image, [shifted_contour], -1, (0, 255, 0), 2)
                            cv2.circle(final_image, (cx, cy + (h-roi_h)), 10, (0, 0, 255), -1)
                            
                            # --- LOGIC ĐIỀU KHIỂN ---
                            center_x = w // 2
                            dead_zone = 40 # Vùng an toàn (Robot đi thẳng)
                            
                            if cx < center_x - dead_zone:
                                cmd_text = "<< NE TRAI"
                                action = "left"
                                cmd_color = "#e74c3c"
                            elif cx > center_x + dead_zone:
                                cmd_text = "NE PHAI >>"
                                action = "right"
                                cmd_color = "#e74c3c"
                            else:
                                cmd_text = "DI THANG ^"
                                action = "forward"
                                cmd_color = "#2ecc71"
                    else:
                        cmd_text = "SAN QUA NHO (LUI)"
                        action = "back"
                        cmd_color = "#c0392b"
                else:
                    cmd_text = "MAT DUONG (LUI)"
                    action = "back"
                    cmd_color = "#c0392b"

                # Gửi lệnh đi (chỉ khi Robot online)
                if self.robot_connected:
                    self.send_command(action)
                else:
                    cmd_text = "MAT KET NOI ROBOT"
                    cmd_color = "#7f8c8d"

                self.lbl_cmd.configure(text=cmd_text, text_color=cmd_color)

                # Chế độ Debug Mask
                if self.view_mode == "Mask":
                    full_mask_display = np.zeros_like(process_frame)
                    roi_color = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
                    full_mask_display[h - roi_h:h, :] = roi_color
                    final_image = full_mask_display

            # Convert OpenCV Image -> Tkinter Image
            if len(final_image.shape) == 2:
                img = Image.fromarray(final_image)
            else:
                img = Image.fromarray(cv2.cvtColor(final_image, cv2.COLOR_BGR2RGB))
            
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(self.display_w, self.display_h))
            self.lbl_video.configure(text="", image=ctk_img)
        else:
            self.cam_connected = False
            self.lbl_video.configure(text="KHÔNG CÓ TÍN HIỆU CAMERA...", image=None)

        self.after(30, self.update_gui)

    # --- CÁC HÀM HỖ TRỢ ---
    def on_mouse_click(self, event):
        x, y = event.x, event.y
        # Đảm bảo click trong vùng ảnh
        if self.frame_hsv is not None and 0 <= x < self.display_w and 0 <= y < self.display_h:
            target = self.frame_hsv[y, x]
            # Tolerance rộng để dễ bắt màu (H: +-50, S: +-90, V: +-110)
            tolerance = np.array([50, 90, 110])
            self.floor_lower = np.clip(target - tolerance, 0, 255)
            self.floor_upper = np.clip(target + tolerance, 0, 255)
            self.calibrated = True
            print(f"Da Calib mau: {target}")

    def reset_calibration(self):
        self.calibrated = False
        self.lbl_cmd.configure(text="DUNG (RESET)", text_color="#95a5a6")
        self.send_command("stop")

    def toggle_view(self):
        self.view_mode = "Mask" if self.switch_view.get() == 1 else "Real"

    def send_command(self, cmd_name):
        curr_time = time.time()
        # Chống Spam lệnh: Nếu lệnh giống cũ và chưa quá 1s -> Không gửi
        if cmd_name == self.last_cmd and (curr_time - self.last_sent_time < 1.0): return
        # Giới hạn tốc độ gửi (tối đa 4 lệnh/giây)
        if curr_time - self.last_sent_time < 0.25: return
        
        self.last_cmd = cmd_name
        self.last_sent_time = curr_time
        threading.Thread(target=lambda: self._request(cmd_name)).start()

    def _request(self, cmd):
        try:
            requests.get(f"{ROBOT_IP}/{cmd}", timeout=0.5)
            print(f"> Sent: {cmd}")
        except:
            pass

    def on_close(self):
        self.vs.stop()
        self.destroy()

# ===== CLASS VIDEO STREAM (SỬA LỖI SYNTAX HOÀN CHỈNH) =====
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
                time.sleep(1) # Chờ 1s rồi thử kết nối lại
                self.stream.open(CAM_URL)

    def read(self):
        # Đã tách dòng lệnh with chuẩn Python
        with self.lock:
            return self.frame

    def stop(self):
        self.stopped = True
        self.stream.release()

if __name__ == "__main__":
    app = RobotControllerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
