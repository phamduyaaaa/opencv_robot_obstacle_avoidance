import customtkinter as ctk
from PIL import Image
import cv2
import threading
import time
import numpy as np
import requests

# ===== 1. CẤU HÌNH IP (Cập nhật đúng IP của bạn) =====
CAM_URL = "http://10.42.0.114/stream"
ROBOT_IP = "http://10.42.0.31"

# ===== 2. CẤU HÌNH THỜI GIAN RẼ (QUAN TRỌNG) =====
# Thời gian robot sẽ "nhắm mắt rẽ" thêm để né hẳn vật (giây)
# Tăng lên nếu robot vẫn bị va quệt, giảm đi nếu robot quay quá nhiều
BLIND_TURN_DURATION = 0.7 

# ===== GIAO DIỆN CONFIG =====
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class RobotControllerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- SETUP CỬA SỔ ---
        self.title("ROBOT AI - FORCE TURN v3.0")
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
        self.view_mode = "Real"
        
        # --- [MỚI] BIẾN XỬ LÝ RẼ DỨT KHOÁT ---
        self.force_turn_until = 0     # Thời điểm kết thúc rẽ cưỡng bức
        self.force_turn_cmd = "stop"  # Lệnh rẽ đang bị khóa
        
        # Biến trạng thái kết nối
        self.cam_connected = False
        self.robot_connected = False

        self.setup_ui()

        # --- KHỞI ĐỘNG HỆ THỐNG ---
        self.vs = VideoStream(CAM_URL).start()
        self.update_gui() 
        threading.Thread(target=self.connection_monitor, daemon=True).start()

    def setup_ui(self):
        # Giao diện cột trái
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)

        ctk.CTkLabel(self.sidebar, text="SYSTEM STATUS", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.status_frame = ctk.CTkFrame(self.sidebar, fg_color="#2b2b2b")
        self.status_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        self.lbl_cam_status = ctk.CTkLabel(self.status_frame, text="● CAM: CHECKING...", font=("Arial", 12, "bold"), text_color="gray")
        self.lbl_cam_status.pack(pady=5, padx=10, anchor="w")
        self.lbl_robot_status = ctk.CTkLabel(self.status_frame, text="● ESP: CHECKING...", font=("Arial", 12, "bold"), text_color="gray")
        self.lbl_robot_status.pack(pady=5, padx=10, anchor="w")

        ctk.CTkLabel(self.sidebar, text="CONTROLS", font=ctk.CTkFont(size=20, weight="bold")).grid(row=2, column=0, padx=20, pady=(20, 10))
        
        self.btn_reset = ctk.CTkButton(self.sidebar, text="RESET MÀU (R)", command=self.reset_calibration, fg_color="#c0392b", hover_color="#e74c3c")
        self.btn_reset.grid(row=3, column=0, padx=20, pady=10)
        
        self.switch_view = ctk.CTkSwitch(self.sidebar, text="Chế độ MASK (Debug)", command=self.toggle_view)
        self.switch_view.grid(row=4, column=0, padx=20, pady=10)

        # Hiển thị lệnh
        ctk.CTkLabel(self.sidebar, text="CURRENT ACTION:", font=ctk.CTkFont(size=14)).grid(row=9, column=0, padx=20, pady=(10,0))
        self.lbl_cmd = ctk.CTkLabel(self.sidebar, text="WAITING...", font=ctk.CTkFont(size=24, weight="bold"), text_color="#f1c40f")
        self.lbl_cmd.grid(row=10, column=0, padx=20, pady=(0, 20))

        # Giao diện Camera
        self.video_frame = ctk.CTkFrame(self, corner_radius=10)
        self.video_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.lbl_video = ctk.CTkLabel(self.video_frame, text="ĐANG KẾT NỐI CAMERA...", font=ctk.CTkFont(size=20))
        self.lbl_video.pack(expand=True, fill="both", padx=10, pady=10)
        self.lbl_video.bind("<Button-1>", self.on_mouse_click)

    # --- CORE ALGORITHM: CÓ LOGIC RẼ DỨT KHOÁT ---
    def update_gui(self):
        frame = self.vs.read()
        
        if frame is not None:
            self.cam_connected = True
            
            # Xử lý ảnh
            self.display_h, self.display_w = 480, 640
            process_frame = cv2.resize(frame, (self.display_w, self.display_h), interpolation=cv2.INTER_LINEAR)
            blurred = cv2.GaussianBlur(process_frame, (15, 15), 0)
            self.frame_hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
            
            final_image = process_frame.copy()
            cmd_text = "CLICK VAO SAN"
            cmd_color = "#95a5a6"
            action = "stop" # Mặc định dừng

            # --- [LOGIC 1] KIỂM TRA XEM CÓ ĐANG "RẼ DỨT KHOÁT" KHÔNG? ---
            current_time = time.time()
            if current_time < self.force_turn_until:
                # Vẫn đang trong thời gian "nhắm mắt rẽ"
                action = self.force_turn_cmd
                cmd_text = f"QUAY MANH... ({int((self.force_turn_until - current_time)*10)})"
                cmd_color = "#d35400" # Màu cam đậm (Cảnh báo)
                
                # Vẽ mũi tên chỉ hướng rẽ lên màn hình
                if action == "left":
                    cv2.arrowedLine(final_image, (400, 240), (200, 240), (0, 165, 255), 5)
                elif action == "right":
                    cv2.arrowedLine(final_image, (240, 240), (400, 240), (0, 165, 255), 5)

            elif self.calibrated:
                # --- [LOGIC 2] NẾU KHÔNG BỊ ÉP RẼ -> CHẠY AI CAMERA ---
                mask = cv2.inRange(self.frame_hsv, self.floor_lower, self.floor_upper)
                kernel = np.ones((7, 7), np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
                mask = cv2.dilate(mask, kernel, iterations=2)
                
                h, w = mask.shape
                roi_h = int(h * 0.6)
                roi = mask[h - roi_h:h, :] 
                
                contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                path_found = False
                cx = -1 
                
                if len(contours) > 0:
                    c = max(contours, key=cv2.contourArea)
                    area = cv2.contourArea(c)
                    
                    if area > 3000:
                        path_found = True
                        M = cv2.moments(c)
                        if M["m00"] != 0:
                            cx = int(M["m10"] / M["m00"])
                            cy = int(M["m01"] / M["m00"])
                            
                            # Vẽ
                            shifted_contour = c + [0, h - roi_h] 
                            cv2.drawContours(final_image, [shifted_contour], -1, (0, 255, 0), 2)
                            cv2.circle(final_image, (cx, cy + (h-roi_h)), 10, (0, 0, 255), -1)
                            
                            # --- RA QUYẾT ĐỊNH ---
                            center_x = w // 2
                            dead_zone = 80 
                            
                            if cx < center_x - dead_zone:
                                # -> RẼ TRÁI
                                action = "left"
                                cmd_text = "<< NE TRAI"
                                cmd_color = "#e74c3c"
                                
                                # [TRIGGER] KÍCH HOẠT CHẾ ĐỘ RẼ DỨT KHOÁT
                                # Chỉ kích hoạt nếu trước đó chưa rẽ (để tránh reset thời gian liên tục)
                                if self.last_cmd != "left":
                                    self.force_turn_until = current_time + BLIND_TURN_DURATION
                                    self.force_turn_cmd = "left"

                            elif cx > center_x + dead_zone:
                                # -> RẼ PHẢI
                                action = "right"
                                cmd_text = "NE PHAI >>"
                                cmd_color = "#e74c3c"
                                
                                # [TRIGGER] KÍCH HOẠT CHẾ ĐỘ RẼ DỨT KHOÁT
                                if self.last_cmd != "right":
                                    self.force_turn_until = current_time + BLIND_TURN_DURATION
                                    self.force_turn_cmd = "right"
                                    
                            else:
                                action = "forward"
                                cmd_text = "DI THANG ^"
                                cmd_color = "#2ecc71"
                    else:
                        action = "back"
                        cmd_text = "SAN QUA NHO (LUI)"
                        cmd_color = "#c0392b"
                else:
                    action = "back"
                    cmd_text = "MAT DUONG (LUI)"
                    cmd_color = "#c0392b"

                if self.view_mode == "Mask":
                    full_mask_display = np.zeros_like(process_frame)
                    roi_color = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
                    full_mask_display[h - roi_h:h, :] = roi_color
                    final_image = full_mask_display

            # Gửi lệnh
            if self.robot_connected:
                self.send_command(action)
            else:
                cmd_text = "MAT KET NOI ROBOT"
                cmd_color = "#7f8c8d"

            self.lbl_cmd.configure(text=cmd_text, text_color=cmd_color)

            # Hiển thị ảnh
            if len(final_image.shape) == 2:
                img = Image.fromarray(final_image)
            else:
                img = Image.fromarray(cv2.cvtColor(final_image, cv2.COLOR_BGR2RGB))
            ctk_img = ctk.CTkImage(img, img, (self.display_w, self.display_h))
            self.lbl_video.configure(text="", image=ctk_img)
        else:
            self.cam_connected = False
            self.lbl_video.configure(text="MAT CAMERA...", image=None)

        self.after(30, self.update_gui)

    # --- CÁC HÀM HỖ TRỢ KHÁC (GIỮ NGUYÊN) ---
    def on_mouse_click(self, event):
        x, y = event.x, event.y
        if self.frame_hsv is not None and 0 <= x < self.display_w and 0 <= y < self.display_h:
            target = self.frame_hsv[y, x]
            tolerance = np.array([50, 90, 110])
            self.floor_lower = np.clip(target - tolerance, 0, 255)
            self.floor_upper = np.clip(target + tolerance, 0, 255)
            self.calibrated = True
            print(f"Calib: {target}")

    def reset_calibration(self):
        self.calibrated = False
        self.force_turn_until = 0 # Reset cả chế độ rẽ
        self.lbl_cmd.configure(text="DUNG (RESET)", text_color="#95a5a6")
        self.send_command("stop")

    def toggle_view(self):
        self.view_mode = "Mask" if self.switch_view.get() == 1 else "Real"

    def send_command(self, cmd_name):
        curr_time = time.time()
        # Logic đặc biệt cho Force Turn: Gửi liên tục để đảm bảo lệnh
        if curr_time < self.force_turn_until:
             if curr_time - self.last_sent_time < 0.1: return # Gửi dày hơn (0.1s)
        else:
             # Logic bình thường
             if cmd_name == self.last_cmd and (curr_time - self.last_sent_time < 1.0): return
             if curr_time - self.last_sent_time < 0.25: return
        
        self.last_cmd = cmd_name
        self.last_sent_time = curr_time
        threading.Thread(target=lambda: self._request(cmd_name)).start()

    def _request(self, cmd):
        try: requests.get(f"{ROBOT_IP}/{cmd}", timeout=0.3)
        except: pass
        
    def connection_monitor(self):
        while True:
            try:
                requests.get(ROBOT_IP, timeout=0.5)
                self.robot_connected = True
            except:
                self.robot_connected = False
            self.after(0, self.update_connection_ui)
            time.sleep(2.0)
            
    def update_connection_ui(self):
        if self.robot_connected: self.lbl_robot_status.configure(text="● ESP: ONLINE", text_color="#2ecc71")
        else: self.lbl_robot_status.configure(text="● ESP: OFFLINE", text_color="#e74c3c")
        if self.cam_connected: self.lbl_cam_status.configure(text="● CAM: ONLINE", text_color="#2ecc71")
        else: self.lbl_cam_status.configure(text="● CAM: OFFLINE", text_color="#e74c3c")
        
    def on_close(self):
        self.vs.stop()
        self.destroy()

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
            if not self.stream.isOpened(): time.sleep(0.1); continue
            grabbed, frame = self.stream.read()
            if grabbed:
                with self.lock: self.grabbed = grabbed; self.frame = frame
            else: self.stream.release(); time.sleep(1); self.stream.open(CAM_URL)
    def read(self):
        with self.lock: return self.frame
    def stop(self): self.stopped = True; self.stream.release()

if __name__ == "__main__":
    app = RobotControllerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
