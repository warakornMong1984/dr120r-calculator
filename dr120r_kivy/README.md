# DR-120R Kivy Android App
Casio DR-120R Printing Calculator — Python/Kivy → Android APK

## โครงสร้างไฟล์
```
dr120r_kivy/
├── Dockerfile          ← build APK อัตโนมัติ
├── README.md
└── app/
    ├── main.py         ← Kivy app (calculator + printer)
    └── buildozer.spec  ← Android build config
```

---

## วิธี Build APK (ง่ายที่สุด — ใช้ Docker)

### ต้องการ
- Docker Desktop (Windows/Mac/Linux)
- พื้นที่ว่าง ~8GB (Android SDK + NDK)
- เวลา build ครั้งแรก ~20-40 นาที

### ขั้นตอน

```bash
# 1. เข้าโฟลเดอร์
cd dr120r_kivy

# 2. สร้าง Docker image (ครั้งแรก ~10-15 นาที)
docker build -t dr120r-builder .

# 3. Build APK (รอ ~10-20 นาที)
mkdir -p output
docker run --rm -v $(pwd)/output:/output dr120r-builder

# 4. APK จะอยู่ที่
ls output/
# → DR-120R-1.0.0-arm64-v8a-debug.apk
```

### Windows (PowerShell)
```powershell
cd dr120r_kivy
docker build -t dr120r-builder .
New-Item -ItemType Directory -Force output
docker run --rm -v "${PWD}/output:/output" dr120r-builder
```

---

## ติดตั้ง APK บน Android

```bash
# ผ่าน ADB (USB debug mode)
adb install output/DR-120R-1.0.0-arm64-v8a-debug.apk

# หรือ copy ไฟล์ไปมือถือแล้วเปิดติดตั้งเองได้เลย
# (ต้องเปิด "แหล่งที่มาที่ไม่รู้จัก" ใน Settings → Security)
```

---

## ตั้งค่า IP Printer

เปิด app → กด **🖨 Print** → ใส่ IP ของ Rongta RP326

| ค่า | Default |
|-----|---------|
| IP  | 192.168.1.100 |
| Port | 9100 |
| กระดาษ | 80mm (42 cols) |

หา IP เครื่องพิมพ์: กด Self-Test ค้างไว้ตอนเปิดเครื่อง → ดูบน slip

---

## Build โดยไม่ใช้ Docker (Linux/Mac)

```bash
# ติดตั้ง dependencies
pip install buildozer cython kivy

# build
cd app
buildozer android debug

# APK อยู่ที่
ls bin/*.apk
```

---

## ฟีเจอร์

| ฟีเจอร์ | รายละเอียด |
|---------|-----------|
| เทปคำนวณ | แสดง real-time เหมือน DR-120R |
| ×/÷ grouping | แสดงเส้นคั่น + เว้นบรรทัด |
| พิมพ์ตรง | TCP Socket → Rongta RP326 Port 9100 |
| Export JPG | บันทึกเทปเป็นรูปภาพ |
| ไม่ต้อง Bridge | Python ส่ง ESC/POS ตรง ไม่ต้องมี middleware |
