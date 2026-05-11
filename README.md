# 🚢 TUNA — Yer Kontrol İstasyonu (YKİ)

> **Teknofest 2025 İnsansız Deniz Aracı Yarışması — Finalist**

TUNA takımının insansız deniz aracı için geliştirilmiş gerçek zamanlı yer kontrol istasyonu yazılımıdır. PyQt5 ile sıfırdan inşa edilmiş olup HC-12 RF modülü üzerinden araçla çift yönlü haberleşme sağlar.

---

## 📸 Ekran Görüntüleri

<!-- Fotoğrafları buraya ekle: ![Arayüz](screenshots/dashboard.png) -->

---

## ✨ Özellikler

- **Gerçek Zamanlı Harita** — GPS verisini canlı olarak haritaya yansıtır, waypoint ekleme/silme destekler
- **Sensör Kartları** — GPS, IMU, LIDAR ve su sensörü verilerini anlık gösterir
- **Görev Planlama** — 3 farklı parkur için koordinat girişi ve renk seçimi
- **Motor Kontrol** — Hız/yön kontrolü, otonom/manuel mod geçişi
- **Acil Durdurma** — 150ms aralıkla tekrarlı sinyal gönderen kilitli acil durum sistemi
- **HC-12 Kanal Ayarı** — TX/RX kanallarını arayüzden yapılandırma
- **PID Parametre Gönderimi** — Kp, Ki, Kd değerlerini araça iletme
- **Log Sistemi** — Filtrelenebilir gerçek zamanlı sistem günlükleri

---

## 🛠️ Teknolojiler

| Teknoloji | Kullanım |
|-----------|----------|
| Python 3 | Ana dil |
| PyQt5 | Arayüz framework'ü |
| pyserial | UART/Seri haberleşme |
| HC-12 RF Modülü | Kablosuz veri aktarımı |

---

## 📡 Haberleşme Protokolü

Araç ile yer istasyonu arasında özel bir metin tabanlı binary protokol kullanılır.

**Gelen paket örnekleri:**

| ID | Sensör | Format |
|----|--------|--------|
| `01` | GPS | `01-ENLEM-BOYLAM-ALT-UYDU-HDOP-HIZ-DAK-SAN` |
| `03` | IMU | `03-ROLL-PITCH-YAW-SICAKLIK` |
| `02` | LIDAR | `02AÇIMESAFE` |
| `04` | Su Sensörü | `04SENSÖRLER` |

**Gönderilen komut örnekleri:**

| Komut | Açıklama |
|-------|----------|
| `060000000000` | Acil durdurma sinyali |
| `131` / `130` | Otonom / Manuel mod |
| `10HHH D` | Motor hız ve yön |
| `11KpKiKdLIMIT` | PID parametreleri |

---

## 🚀 Kurulum

```bash
pip install PyQt5 pyserial
python Tuna_ARAYUZ.py
```

> **Not:** Simülatör modunda test etmek için `Tuna_ARAYUZ.py` içinde `SIMULATOR_MODE = True` yapın.

Gerçek donanımda kullanım için seri port isimlerini kendi sisteminize göre ayarlayın:
```python
SERIAL_PORT_TX_NAME = "/dev/ttyACM0"  # Linux
SERIAL_PORT_RX_NAME = "/dev/ttyACM1"  # Linux
# Windows için: "COM3", "COM4" vb.
```

---

## 👤 Geliştirici

**Selman Demir** — Bilgisayar Mühendisliği, Karamanoğlu Mehmetbey Üniversitesi

- 📧 selmandmr00@gmail.com
- 🐙 [github.com/selmandemir](https://github.com/selmandemir)
