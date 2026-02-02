# 🚗 OpenCV Obstacle Avoidance Robot
> **Vision-Based Navigation using OpenCV + ESP8266 (WiFi Control)**

---

<p align="center">
  <img width="45%" alt="System View 1" src="https://github.com/user-attachments/assets/56da62e5-13a0-4d12-98d5-42acd4bc5187" />
  <img width="45%" alt="System View 2" src="https://github.com/user-attachments/assets/08621213-1cb2-44b0-8fc0-4a8ecfc467f8" />
</p>

---

## 📌 Giới thiệu
Dự án xây dựng một **robot tự hành tránh vật cản** sử dụng **thị giác máy tính (OpenCV)** thay cho cảm biến siêu âm. Robot phân tích luồng video từ Camera WiFi, xử lý tại máy tính trung tâm và điều khiển động cơ thông qua giao thức HTTP gửi tới ESP8266.

### 🌟 Tính năng nổi bật
* **Vision-based:** Không phụ thuộc vào cảm biến khoảng cách vật lý.
* **Real-time Calibration:** Click chuột trực tiếp để chọn màu sàn (HSV), thích nghi mọi môi trường.
* **GUI Dashboard:** Hiển thị trực quan mức độ an toàn của các hướng di chuyển.
* **WiFi Control:** Điều khiển không dây qua mạng nội bộ.

---

## 🧩 Kiến trúc hệ thống

```text
Camera WiFi (MJPEG Stream)
      │
      ▼
Laptop / PC (Xử lý Python + OpenCV) ───┐
      │                                │
      ▼ (Lệnh HTTP GET)                │ (Hiển thị)
ESP8266 Web Server                     │
      │                                ▼
Mạch cầu H (L298N/DRV8833)        Giao diện GUI (Tkinter/CV2)
      │
      ▼
Động cơ DC (Robot di chuyển)
```
## 🧠 Thuật toán xử lý ảnh & Ra quyết định

---

### 1️⃣ Quy trình xử lý ảnh (Image Pipeline)

**Tiền xử lý (Pre-processing):**
- Resize khung hình về **640 × 480**
- Áp dụng **Gaussian Blur** để khử nhiễu

**Phân đoạn ảnh (Segmentation):**
- Chuyển ảnh từ không gian màu **BGR → HSV**
- Tạo **Mask** dựa trên màu sàn đã được calibrate bằng thao tác click chuột

**Hậu xử lý (Post-processing):**
- **Dilate**: làm đầy các vùng sàn bị đứt đoạn
- **Erode**: loại bỏ nhiễu nhỏ không mong muốn

**Phân tích vùng quan tâm (ROI):**
- Chọn **60% diện tích phía dưới ảnh**
- Chia ROI thành 3 vùng:
  | LEFT | CENTER | RIGHT |

---

### 2️⃣ Logic điều hướng (Decision Logic)

Robot tính toán **tỷ lệ pixel trắng (ratio)** đại diện cho diện tích sàn trống trong mỗi vùng.

#### Ngưỡng an toàn
```text
SAFE = 0.5
```
| Trạng thái vùng CENTER | Điều kiện ưu tiên | Hành động            |
| ---------------------- | ----------------- | -------------------- |
| An toàn (Ratio > 0.5)  | Mặc định          | FORWARD (Tiến)       |
| Vật cản (Ratio < 0.5)  | LEFT > RIGHT      | TURN LEFT (Rẽ trái)  |
| Vật cản (Ratio < 0.5)  | RIGHT > LEFT      | TURN RIGHT (Rẽ phải) |
| Kẹt (All Ratio < 0.2)  | Mặc định          | BACK (Lùi)           |

## ⚙️ Cài đặt & Sử dụng

---

### 🔧 Phần cứng

- **Vi điều khiển:**  
  ESP8266 (NodeMCU / D1 Mini)

- **Thị giác:**  
  ESP32-CAM hoặc IP Camera hỗ trợ MJPEG Stream

- **Động lực học:**  
  - Mạch cầu H **L298N**  
  - **2 động cơ DC**  
  - **Khung xe 3 bánh**

---

### 💻 Phần mềm

#### Cài đặt thư viện (Python)
```bash
pip install opencv-python numpy requests
```
### ▶️ Hướng dẫn sử dụng

Tìm IP của esp32_cam và esp8266 bằng cách đọc serial port trên phần mềm Arduino IDE

Thay đổi IP tương ứng trong code algo_v1.py và chạy:
```bash
python3 algo_v1.py
```
Click chuột vào vùng sàn trống trên stream GUI

Robot bắt đầu nhận diện bề mặt và tự động di chuyển

🚀 Hướng phát triển

 Áp dụng PID Controller để chuyển hướng mượt hơn

 Tích hợp Deep Learning (YOLO) để nhận diện & phân loại vật cản

 Chuyển sang C++ / ROS2 và chạy trên Raspberry Pi để tăng độ ổn định
