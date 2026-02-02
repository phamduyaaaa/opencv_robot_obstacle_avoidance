import customtkinter as ctk
from PIL import Image
import cv2
import threading
import time
import numpy as np
import requests

# ===== 1. CẤU HÌNH IP =====
CAM_URL = "http://10.42.0.151/stream"
ROBOT_IP = "http://10.42.0.31"

# ===== 2. CẤU HÌNH NGƯỠNG NÉ =====
# Nếu mật độ vật cản chiếm quá 5% vùng nhìn -> NÉ NGAY
OBSTACLE_THRESHOLD = 0.4

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class RobotControllerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ROBOT OBSTACLE AVOIDANCE - COLOR BASED")
        self.geometry("1100x700")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- BIẾN XỬ LÝ ---
        self.obj_lower = None
        self.obj_upper = None
        self.calibrated = False
        self.frame_hsv = None
        
        self.last_cmd = ""
        self.last_sent_time = 0
        self.view_mode = "Real"
        
        self.cam_connected = False
        self.robot_connected = False

        self.setup_ui()

        # Start Systems
        self.vs = VideoStream(CAM_URL).start()
        self.update_gui() 
        threading.Thread(target=self.connection_monitor, daemon=True).start()

    def setup_ui(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)

        ctk.CTkLabel(self.sidebar, text="TRẠNG THÁI HỆ THỐNG", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.status_frame = ctk.CTkFrame(self.sidebar, fg_color="#2b2b2b")
        self.status_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        self.lbl_cam_status = ctk.CTkLabel(self.status_frame, text="● CAM: CHECKING...", font=("Arial", 12, "bold"), text_color="gray")
        self.lbl_cam_status.pack(pady=5, padx=10, anchor="w")
        self.lbl_robot_status = ctk.CTkLabel(self.status_frame, text="● ESP: CHECKING...", font=("Arial", 12, "bold"), text_color="gray")
        self.lbl_robot_status.pack(pady=5, padx=10, anchor="w")

        ctk.CTkLabel(self.sidebar, text="ĐIỀU KHIỂN", font=ctk.CTkFont(size=20, weight="bold")).grid(row=2, column=0, padx=20, pady=(20, 10))
        
        self.btn_reset = ctk.CTkButton(self.sidebar, text="CHỌN LẠI VẬT (R)", command=self.reset_calibration, fg_color="#c0392b", hover_color="#e74c3c")
        self.btn_reset.grid(row=3, column=0, padx=20, pady=10)
        
        self.switch_view = ctk.CTkSwitch(self.sidebar, text="Xem Mask Vật Cản", command=self.toggle_view)
        self.switch_view.grid(row=4, column=0, padx=20, pady=10)

        # Thanh hiển thị mức độ nguy hiểm
        self.create_sensor_bar("NGUY HIỂM TRÁI", 5)
        self.create_sensor_bar("NGUY HIỂM GIỮA", 7)
        self.create_sensor_bar("NGUY HIỂM PHẢI", 9)

        ctk.CTkLabel(self.sidebar, text="HÀNH ĐỘNG:", font=ctk.CTkFont(size=14)).grid(row=11, column=0, padx=20, pady=(10,0))
        self.lbl_cmd = ctk.CTkLabel(self.sidebar, text="CHỜ...", font=ctk.CTkFont(size=24, weight="bold"), text_color="#f1c40f")
        self.lbl_cmd.grid(row=12, column=0, padx=20, pady=(0, 20))

        # Camera Frame
        self.video_frame = ctk.CTkFrame(self, corner_radius=10)
        self.video_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.lbl_video = ctk.CTkLabel(self.video_frame, text="ĐANG KẾT NỐI...", font=ctk.CTkFont(size=20))
        self.lbl_video.pack(expand=True, fill="both", padx=10, pady=10)
        self.lbl_video.bind("<Button-1>", self.on_mouse_click)

    def create_sensor_bar(self, name, row):
        lbl = ctk.CTkLabel(self.sidebar, text=name, anchor="w", font=ctk.CTkFont(size=12))
        lbl.grid(row=row, column=0, padx=20, pady=(10, 0), sticky="w")
        bar = ctk.CTkProgressBar(self.sidebar, orientation="horizontal")
        bar.grid(row=row+1, column=0, padx=20, pady=(0, 5), sticky="ew")
        bar.set(0)
        # Set màu mặc định là Xanh (An toàn)
        bar.configure(progress_color="#2ecc71")
        if "TRÁI" in name: self.bar_left = bar
        elif "GIỮA" in name: self.bar_center = bar
        elif "PHẢI" in name: self.bar_right = bar

    # --- CORE ALGORITHM: NÉ VẬT CẢN (INVERTED LOGIC) ---
    def update_gui(self):
        frame = self.vs.read()
        
        if frame is not None:
            self.cam_connected = True
            
            # Resize & Blur
            self.display_h, self.display_w = 480, 640
            process_frame = cv2.resize(frame, (self.display_w, self.display_h), interpolation=cv2.INTER_LINEAR)
            blurred = cv2.GaussianBlur(process_frame, (11, 11), 0)
            self.frame_hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
            
            final_image = process_frame.copy()
            cmd_text = "CLICK VAO VAT CAN"
            cmd_color = "#95a5a6"

            if self.calibrated:
                # 1. Tạo Mask (Bây giờ Mask Trắng = Vật Cản)
                mask = cv2.inRange(self.frame_hsv, self.obj_lower, self.obj_upper)
                
                # 2. Lọc nhiễu
                kernel = np.ones((5, 5), np.uint8)
                mask = cv2.erode(mask, kernel, iterations=1)
                mask = cv2.dilate(mask, kernel, iterations=2)
                
                # 3. Cắt vùng quan tâm (ROI) - Lấy phần dưới chân robot
                h, w = mask.shape
                roi_h = int(h * 0.6)
                roi = mask[h - roi_h:h, :] 
                w_third = w // 3
                
                # 4. Tính mật độ VẬT CẢN (Density of Danger)
                total_pixels = roi_h * w_third
                danger_left = cv2.countNonZero(roi[:, :w_third]) / total_pixels
                danger_center = cv2.countNonZero(roi[:, w_third : 2*w_third]) / total_pixels
                danger_right = cv2.countNonZero(roi[:, 2*w_third:]) / total_pixels
                
                # Cập nhật thanh hiển thị (Càng cao càng nguy hiểm)
                self.bar_left.set(danger_left)
                self.bar_center.set(danger_center)
                self.bar_right.set(danger_right)
                
                # Đổi màu thanh bar: Đỏ nếu > ngưỡng, Xanh nếu an toàn
                self.update_bar_color(self.bar_left, danger_left)
                self.update_bar_color(self.bar_center, danger_center)
                self.update_bar_color(self.bar_right, danger_right)

                # 5. Logic Di Chuyển (Đảo ngược so với trước)
                action = "forward" # Mặc định là đi thẳng (nếu không thấy gì)

                # Nếu vùng GIỮA có vật cản
                if danger_center > OBSTACLE_THRESHOLD:
                    # So sánh 2 bên, bên nào ÍT vật cản hơn thì rẽ sang đó
                    if danger_left < danger_right and danger_left < OBSTACLE_THRESHOLD:
                        cmd_text = "<< NE SANG TRAI"
                        action = "left"
                        cmd_color = "#e74c3c"
                    elif danger_right < danger_left and danger_right < OBSTACLE_THRESHOLD:
                        cmd_text = "NE SANG PHAI >>"
                        action = "right"
                        cmd_color = "#e74c3c"
                    else:
                        # Cả 3 đường đều tắc -> Lùi
                        cmd_text = "TAC DUONG (LUI)"
                        action = "back"
                        cmd_color = "#c0392b"
                else:
                    # Giữa an toàn -> Đi thẳng
                    # Có thể thêm logic né nhẹ nếu vật cản mấp mé ở 2 bên
                    if danger_left > OBSTACLE_THRESHOLD:
                        cmd_text = "NE PHAI (NHE) >"
                        action = "forward" # Hoặc right nhẹ nếu muốn
                        cmd_color = "#f1c40f"
                    elif danger_right > OBSTACLE_THRESHOLD:
                        cmd_text = "< NE TRAI (NHE)"
                        action = "forward" # Hoặc left nhẹ nếu muốn
                        cmd_color = "#f1c40f"
                    else:
                        cmd_text = "DI THANG ^"
                        action = "forward"
                        cmd_color = "#2ecc71"

                # Gửi lệnh
                if self.robot_connected:
                    self.send_command(action)
                else:
                    cmd_text = "MAT KET NOI ROBOT"
                    cmd_color = "#7f8c8d"

                self.lbl_cmd.configure(text=cmd_text, text_color=cmd_color)

                # Vẽ khung bao quanh vật cản (Visualization)
                if self.view_mode == "Mask":
                    # Hiện Mask trắng đen
                    full_mask = np.zeros_like(process_frame)
                    roi_color = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
                    full_mask[h - roi_h:h, :] = roi_color
                    final_image = full_mask
                else:
                    # Vẽ khung đỏ quanh vùng nguy hiểm
                    self.draw_danger_box(final_image, danger_left, 0, w_third, h, roi_h)
                    self.draw_danger_box(final_image, danger_center, w_third, 2*w_third, h, roi_h)
                    self.draw_danger_box(final_image, danger_right, 2*w_third, w, h, roi_h)

            # Hiển thị
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

    def update_bar_color(self, bar, val):
        if val > OBSTACLE_THRESHOLD:
            bar.configure(progress_color="#e74c3c") # Đỏ (Nguy hiểm)
        else:
            bar.configure(progress_color="#2ecc71") # Xanh (An toàn)

    def draw_danger_box(self, img, val, x1, x2, h, roi_h):
        # Nếu nguy hiểm -> Vẽ khung ĐỎ đè lên
        if val > OBSTACLE_THRESHOLD:
            cv2.rectangle(img, (x1, h-roi_h), (x2, h), (0, 0, 255), 3)
            cv2.putText(img, "VAT CAN", (x1+10, h-roi_h+30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
        else:
            # Vẽ khung xanh mờ (An toàn)
            cv2.rectangle(img, (x1, h-roi_h), (x2, h), (0, 255, 0), 1)

    # --- INPUT & CONTROL ---
    def on_mouse_click(self, event):
        x, y = event.x, event.y
        if self.frame_hsv is not None and 0 <= x < self.display_w and 0 <= y < self.display_h:
            target = self.frame_hsv[y, x]
            # Chọn vật cản
            tolerance = np.array([40, 80, 100])
            self.obj_lower = np.clip(target - tolerance, 0, 255)
            self.obj_upper = np.clip(target + tolerance, 0, 255)
            self.calibrated = True
            print(f"Da chon Vat Can: {target}")

    def reset_calibration(self):
        self.calibrated = False
        self.lbl_cmd.configure(text="DUNG (RESET)", text_color="#95a5a6")
        self.send_command("stop")

    def toggle_view(self):
        self.view_mode = "Mask" if self.switch_view.get() == 1 else "Real"

    def send_command(self, cmd_name):
        curr_time = time.time()
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

# ===== CLASS VIDEO STREAM =====
class VideoStream:
    def __init__(self, src=0):
        self.stream = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
        self.stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.grabbed, self.frame = self.stream.read()
        self.stopped = False
        self.lock = threading.Lock()
    def start(self): threading.Thread(target=self.update, args=()).start(); return self
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
