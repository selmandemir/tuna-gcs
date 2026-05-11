#!/usr/bin/python3
# -*- coding: utf-8 -*-
import sys
import threading
import time
import serial
import serial.tools.list_ports
import math
from datetime import datetime, timezone

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QTextEdit, QComboBox, QFrame, QLineEdit, QDoubleSpinBox, QSpinBox,
    QSlider, QGroupBox, QGridLayout, QTabWidget, QSplitter, QProgressBar, QSizePolicy,
    QStackedWidget, QGraphicsOpacityEffect, QListView, QSplashScreen
)
from PyQt5.QtCore import (Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, pyqtProperty,
                          QParallelAnimationGroup, QRect, QRectF, pyqtSignal, pyqtSlot, QPointF)
from PyQt5.QtGui import (QFont, QColor, QPainter, QPen, QBrush, QPolygon, QPalette, QPixmap,
                         QLinearGradient, QRadialGradient, QPolygonF)


# --- SİMÜLATÖR MODU ---
SIMULATOR_MODE = True
# --------------------

SERIAL_PORT_TX_NAME = "/dev/ttyACM0"
SERIAL_PORT_RX_NAME = "/dev/ttyACM1"
BAUD_RATE = 9600

# --- YENİ EKLENEN AYARLAR ---
# Gemi izi çizme özelliğini açıp kapatmak için anahtar

ENABLE_SHIP_TRAIL = False
MAX_TRAIL_POINTS = 200 # Haritada gösterilecek maksimum iz noktası sayısı
# --- YENİ EKLENEN AYARLAR SONU ---


#=========================================================================================
# BÖLÜM 1: YARDIMCI FONKSİYON VE MODERN BİLEŞENLER
#=========================================================================================

def apply_modern_combobox_style(combo_box):
    list_view = QListView(combo_box)
    list_view.setObjectName("comboBoxListView")
    list_view.setSpacing(4)
    list_view.setStyleSheet("""
        QListView#comboBoxListView {
            background-color: #1e2228;
            border: 1px solid rgba(0, 212, 255, 0.6);
            border-radius: 6px;
            outline: 0px;
            padding: 5px;
        }
        QListView#comboBoxListView::item { padding: 8px 10px; border-radius: 4px; }
        QListView#comboBoxListView::item:hover { background-color: rgba(255, 255, 255, 0.1); }
        QListView#comboBoxListView::item:selected { background-color: #00d4ff; color: #000000; }
    """)
    combo_box.setView(list_view)

class RotaryKnob(QWidget):
    valueChanged = pyqtSignal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(160, 160)
        self._min_value, self._max_value, self._value = 1, 127, 90
        self._angle = self.value_to_angle(self._value)
        self._is_dragging = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height())
        square_rect = QRect(0, 0, side, side)
        square_rect.moveCenter(self.rect().center())
        rect = square_rect.adjusted(10, 10, -10, -10)
        center = rect.center()
        radius = min(rect.width(), rect.height()) / 2
        bg_gradient = QRadialGradient(center, radius)
        bg_gradient.setColorAt(0.0, QColor(45, 52, 64))
        bg_gradient.setColorAt(1.0, QColor(27, 32, 39))
        painter.setBrush(bg_gradient)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(rect)
        painter.setPen(QPen(QColor(20, 22, 25), 3))
        painter.drawEllipse(rect)
        painter.save()
        painter.translate(center)
        for i in range(60):
            painter.rotate(6)
            pen = QPen(QColor(80, 90, 100), 1.5)
            if i % 5 == 0:
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawLine(int(radius - 2), 0, int(radius - 10), 0)
            else:
                painter.setPen(pen)
                painter.drawLine(int(radius - 2), 0, int(radius - 6), 0)
        painter.restore()
        painter.save()
        painter.translate(center)
        painter.rotate(self._angle)
        indicator_gradient = QLinearGradient(0, -radius, 0, radius)
        indicator_gradient.setColorAt(0.0, QColor(0, 212, 255))
        indicator_gradient.setColorAt(1.0, QColor(124, 58, 237))
        painter.setBrush(indicator_gradient)
        painter.setPen(QPen(Qt.white, 1))
        indicator_poly = QPolygon([
            QPoint(0, int(-radius + 5)),
            QPoint(8, int(-radius + 20)),
            QPoint(-8, int(-radius + 20))
        ])
        painter.drawPolygon(indicator_poly)
        painter.restore()
        font = QFont("Segoe UI", 30, QFont.Bold)
        painter.setFont(font)
        painter.setPen(Qt.white)
        painter.drawText(self.rect().adjusted(0,0,0,-20), Qt.AlignCenter, str(self._value))
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(150, 160, 170))
        painter.drawText(self.rect().adjusted(0,0,0,40), Qt.AlignCenter, "KANAL")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self.update_angle_from_pos(event.pos())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            self.update_angle_from_pos(event.pos())
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            event.accept()
    
    def update_angle_from_pos(self, pos):
        center = self.rect().center()
        dx = pos.x() - center.x()
        dy = pos.y() - center.y()
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad) + 90
        if angle_deg < 0:
            angle_deg += 360
        self._angle = angle_deg
        new_value = self.angle_to_value(self._angle)
        self.setValue(new_value)

    def value_to_angle(self, value):
        range_val = self._max_value - self._min_value
        if range_val == 0: return 0
        return (value - self._min_value) * 360 / range_val

    def angle_to_value(self, angle):
        range_val = self._max_value - self._min_value
        if range_val == 0: return self._min_value
        return int((angle * range_val / 360) + self._min_value)

    def setValue(self, val):
        val = max(self._min_value, min(self._max_value, val))
        if self._value != val:
            self._value = val
            self._angle = self.value_to_angle(val)
            self.valueChanged.emit(self._value)
            self.update()

class SwitchButton(QWidget):
    toggled = pyqtSignal(bool)
    def __init__(self, text_on="OTONOM", text_off="MANUEL", parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 40)
        self._is_on = False
        self.text_on = text_on
        self.text_off = text_off
        self._thumb_pos_x = 3 
        self._initial_pos_set = False 
        
        self.animation = QPropertyAnimation(self, b"thumb_pos")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_pos_set:
            self.thumb_pos = self.width()/2 + 3 if not self._is_on else 3
            self._initial_pos_set = True

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0, 0, self.width(), self.height())
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(30, 30, 30))
        painter.drawRoundedRect(rect, 20, 20)
        thumb_rect = QRectF(self._thumb_pos_x, 3, self.width()/2 - 6, self.height() - 6)
        thumb_gradient = QLinearGradient(thumb_rect.topLeft(), thumb_rect.bottomRight())
        if self._is_on:
            thumb_gradient.setColorAt(0.0, QColor(0, 212, 255))
            thumb_gradient.setColorAt(1.0, QColor(124, 58, 237))
        else:
            thumb_gradient.setColorAt(0.0, QColor(28, 163, 68))
            thumb_gradient.setColorAt(1.0, QColor(34, 197, 94))
        painter.setBrush(thumb_gradient)
        painter.drawRoundedRect(thumb_rect, 17, 17)
        font = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255) if self._is_on else QColor(120, 120, 120))
        painter.drawText(QRectF(0, 0, self.width()/2, self.height()), Qt.AlignCenter, self.text_on)
        painter.setPen(QColor(255, 255, 255) if not self._is_on else QColor(120, 120, 120))
        painter.drawText(QRectF(self.width()/2, 0, self.width()/2, self.height()), Qt.AlignCenter, self.text_off)

    def mousePressEvent(self, event):
        self._is_on = not self._is_on
        self.animation.stop()
        self.animation.setEndValue(3 if self._is_on else self.width()/2 + 3)
        self.animation.start()
        self.toggled.emit(self._is_on)
        event.accept()

    @pyqtProperty(float)
    def thumb_pos(self):
        return self._thumb_pos_x
    @thumb_pos.setter
    def thumb_pos(self, value):
        self._thumb_pos_x = value
        self.update()

class ModernSensorCard(QFrame):
    def __init__(self, icon, title, color_scheme="blue", parent=None):
        super().__init__(parent)
        self.setObjectName("modernSensorCard")
        self.setMinimumHeight(180)
        self.setMaximumHeight(200)
        self.value_str = "--"
        self.status_str = "Bekleniyor..."
        self.color_scheme = color_scheme
        self.is_active = False
        self.pulse_value = 0.3
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)
        header_layout = QHBoxLayout()
        icon_container = QFrame()
        icon_container.setObjectName("iconContainer")
        icon_container.setFixedSize(50, 50)
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_label = QLabel(icon)
        self.icon_label.setObjectName("modernIcon")
        self.icon_label.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(self.icon_label)
        title_layout = QVBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("modernTitle")
        self.status_label = QLabel(self.status_str)
        self.status_label.setObjectName("modernStatus")
        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.status_label)
        title_layout.addStretch()
        header_layout.addWidget(icon_container)
        header_layout.addLayout(title_layout, 1)
        self.value_label = QLabel(self.value_str)
        self.value_label.setObjectName("modernValue")
        self.value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.value_label.setWordWrap(True)
        main_layout.addLayout(header_layout)
        main_layout.addWidget(self.value_label, 1)
        self.pulse_animation = QPropertyAnimation(self, b'pulseValue')
        self.pulse_animation.setDuration(2000)
        self.pulse_animation.setLoopCount(-1)
        self.pulse_animation.setKeyValueAt(0, 0.3)
        self.pulse_animation.setKeyValueAt(0.5, 1.0)
        self.pulse_animation.setKeyValueAt(1.0, 0.3)
        effect = QGraphicsOpacityEffect(opacity=0.0)
        self.setGraphicsEffect(effect)
        self.pos_anim = QPropertyAnimation(self, b"pos")
        self.opacity_anim = QPropertyAnimation(self.graphicsEffect(), b"opacity")

    def start_entrance_animation(self, delay=0):
        self.opacity_anim.setDuration(600)
        self.opacity_anim.setStartValue(0.0)
        self.opacity_anim.setEndValue(1.0)
        self.opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.pos_anim.setDuration(800)
        start_pos = self.pos() + QPoint(0, 50)
        end_pos = self.pos()
        self.pos_anim.setStartValue(start_pos)
        self.pos_anim.setEndValue(end_pos)
        self.pos_anim.setEasingCurve(QEasingCurve.OutBack)
        QTimer.singleShot(delay, self.opacity_anim.start)
        QTimer.singleShot(delay + 50, self.pos_anim.start)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = {"blue": (QColor(59, 130, 246), QColor(147, 197, 253)), "green": (QColor(34, 197, 94), QColor(134, 239, 172)),"orange": (QColor(249, 115, 22), QColor(253, 186, 116)), "purple": (QColor(147, 51, 234), QColor(196, 181, 253)),"red": (QColor(239, 68, 68), QColor(252, 165, 165)), "cyan": (QColor(6, 182, 212), QColor(165, 243, 252))}
        primary_color, _ = colors.get(self.color_scheme, colors["blue"])
        if self.is_active:
            glow_color = QColor(primary_color)
            glow_color.setAlphaF(0.1 * self.pulse_value)
            painter.setBrush(QBrush(glow_color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect().adjusted(-5, -5, 5, 5), 20, 20)
            highlight_gradient = QLinearGradient(0, 0, self.width(), 0)
            highlight_gradient.setColorAt(0.5, QColor(primary_color))
            highlight_gradient.setColorAt(0, QColor(primary_color).darker(150))
            highlight_gradient.setColorAt(1, QColor(primary_color).darker(150))
            painter.setBrush(QBrush(highlight_gradient))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(0, 0, self.width(), 4, 2, 2)

    def update_data(self, value, status, is_active=True):
        self.value_label.setText(str(value))
        self.status_label.setText(str(status))
        self.is_active = is_active
        if is_active and self.pulse_animation.state() != QPropertyAnimation.Running:
            self.pulse_animation.start()
        elif not is_active:
            self.pulse_animation.stop()
            self.pulse_value = 0.3
        self.update()

    @pyqtProperty(float)
    def pulseValue(self):
        return self.pulse_value
    @pulseValue.setter
    def pulseValue(self, value):
        self.pulse_value = value
        self.update()

class MapView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(250, 250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.current_pos = (37.1819, 33.2154)
        self.waypoints = []
        
        # Gemi izi için nokta listesi eklendi
        self.trail_points = []
        
        self.current_heading = 0
        self.map_width_in_meters = 50.0
        self.zoom_factor = 1.2
        self.min_zoom_meters = 5.0
        self.max_zoom_meters = 500.0
        self.zoom_in_button = QPushButton("+", self)
        self.zoom_in_button.setObjectName("zoomButton")
        self.zoom_in_button.setFixedSize(30, 30)
        self.zoom_in_button.clicked.connect(self.zoom_in)
        self.zoom_out_button = QPushButton("-", self)
        self.zoom_out_button.setObjectName("zoomButton")
        self.zoom_out_button.setFixedSize(30, 30)
        self.zoom_out_button.clicked.connect(self.zoom_out)
        self._update_button_positions()

    def zoom_in(self):
        new_width = self.map_width_in_meters / self.zoom_factor
        self.map_width_in_meters = max(self.min_zoom_meters, new_width)
        self.update()

    def zoom_out(self):
        new_width = self.map_width_in_meters * self.zoom_factor
        self.map_width_in_meters = min(self.max_zoom_meters, new_width)
        self.update()
        
    def _update_button_positions(self):
        margin = 10
        btn_size = 30
        self.zoom_in_button.move(self.width() - btn_size - margin, margin)
        self.zoom_out_button.move(self.width() - btn_size - margin, margin + btn_size + 5)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_button_positions()

    def update_position(self, lat, lon, heading=None):
        try:
            self.current_pos = (float(lat), float(lon))
            if heading is not None:
                self.current_heading = float(heading)
            
            # YENİ: Gemi izi listesine yeni konumu ekle
            if ENABLE_SHIP_TRAIL:
                self.trail_points.append(QPointF(self.current_pos[1], self.current_pos[0]))
                if len(self.trail_points) > MAX_TRAIL_POINTS:
                    self.trail_points.pop(0) # Eski noktayı sil

            self.update()
        except (ValueError, TypeError):
            pass
            
    def add_waypoint(self, lat, lon, wp_id):
        try:
             new_lat, new_lon = float(lat), float(lon)
             wp_found = False
             for i in range(len(self.waypoints)):
                 if self.waypoints[i][2] == wp_id:
                     self.waypoints[i] = (new_lat, new_lon, wp_id)
                     wp_found = True
                     break
             if not wp_found:
                 self.waypoints.append((new_lat, new_lon, wp_id))
             self.update()
        except (ValueError, TypeError):
            pass

    def remove_waypoint(self, wp_id):
        original_count = len(self.waypoints)
        self.waypoints = [wp for wp in self.waypoints if wp[2] != wp_id]
        if len(self.waypoints) < original_count:
            self.update()

    def clear_waypoints(self):
        self.waypoints = []
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        bgColor = QColor("#111113")
        painter.fillRect(self.rect(), bgColor)
        
        center_x, center_y = self.width() / 2, self.height() / 2
        
        gridColor = bgColor.lighter(130)
        pen = QPen(gridColor)
        pen.setStyle(Qt.DotLine)
        painter.setPen(pen)
        step = 40
        for x in range(int(center_x) % step, self.width(), step):
            painter.drawLine(x, 0, x, self.height())
        for y in range(int(center_y) % step, self.height(), step):
            painter.drawLine(0, y, self.width(), y)
        
        METERS_PER_DEGREE_APPROX = 111100.0
        map_width_in_degrees = self.map_width_in_meters / METERS_PER_DEGREE_APPROX
        
        if map_width_in_degrees > 0:
            scale_factor = self.width() / map_width_in_degrees
        else:
            scale_factor = 0

        # YENİ: Gemi izini çizme bölümü
        if ENABLE_SHIP_TRAIL and len(self.trail_points) > 1:
            trail_pen = QPen(QColor(0, 212, 255, 100), 2, Qt.SolidLine)
            painter.setPen(trail_pen)
            
            poly_points = QPolygonF()
            for point in self.trail_points:
                delta_lon = point.x() - self.current_pos[1]
                delta_lat = point.y() - self.current_pos[0]
                offset_x = delta_lon * scale_factor
                offset_y = -delta_lat * scale_factor
                poly_points.append(QPointF(center_x + offset_x, center_y + offset_y))
            
            painter.drawPolyline(poly_points)

        # Gemi simgesini çiz
        painter.save()
        painter.translate(center_x, center_y)
        rotation_angle = (self.current_heading - 22.0) * (180.0 / 126.0)
        painter.rotate(rotation_angle)
        shipColor = QColor("#00d4ff")
        pen = QPen(shipColor.darker(150))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QBrush(shipColor))
        size = 10
        ship_polygon = QPolygon([QPoint(0, -size), QPoint(size // 2, size // 2), QPoint(0, size // 4), QPoint(-size // 2, size // 2)])
        painter.drawPolygon(ship_polygon)
        painter.restore()

        # Hedef noktalarını (waypoint) çiz
        wpColor = QColor("#FF9933")
        pen = QPen(wpColor.darker(150))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(QBrush(wpColor))
        font = painter.font()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        textColor = QColor(Qt.white)

        for lat, lon, wp_id in self.waypoints:
             delta_lon, delta_lat = lon - self.current_pos[1], lat - self.current_pos[0]
             
             offset_x, offset_y = delta_lon * scale_factor, -delta_lat * scale_factor
             x_wp, y_wp = center_x + offset_x, center_y + offset_y
             
             x_wp, y_wp = max(10, min(x_wp, self.width() - 10)), max(10, min(y_wp, self.height() - 10))
             painter.drawEllipse(QPoint(int(x_wp), int(y_wp)), 7, 7)
             painter.setPen(textColor)
             painter.drawText(int(x_wp) + 9, int(y_wp) + 3, str(wp_id))
             pen = QPen(wpColor.darker(150))
             pen.setWidth(1)
             painter.setPen(pen)

class NotificationWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.setObjectName("notificationFrame")
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(15, 10, 15, 10)
        self.main_layout.setSpacing(10)

        self.icon_label = QLabel("")
        self.icon_label.setObjectName("notificationIcon")
        self.message_label = QLabel("Bu bir bildirimdir.")
        self.message_label.setObjectName("notificationMessage")
        self.message_label.setWordWrap(True)

        self.main_layout.addWidget(self.icon_label)
        self.main_layout.addWidget(self.message_label)
        self.adjustSize()

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(400)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_animation)

    def show_notification(self, message, level="info", timeout=3500):
        level_map = {
            "success": ("✅", "#A5D6A7"),
            "info": ("ℹ️", "#90CAF9"),
            "warning": ("⚠️", "#FFE082"),
            "error": ("🔴", "#F48FB1"),
            "send": ("📤", "#90CAF9"),
            "command": ("⚙️", "#CE93D8"),
        }
        icon, color = level_map.get(level, level_map["info"])

        self.icon_label.setText(icon)
        self.message_label.setText(message)
        self.setStyleSheet(f"""
            QFrame#notificationFrame {{
                background-color: rgba(30, 32, 38, 0.95);
                border: 1px solid {color};
                border-radius: 8px;
            }}
            QLabel {{ background-color: transparent; border: none; }}
            QLabel#notificationIcon {{ font-size: 16px; }}
            QLabel#notificationMessage {{ color: #e5e7eb; font-size: 14px; }}
        """)
        
        self.parent().position_notification()
        self.show()

        self.animation.stop()
        try: self.animation.finished.disconnect()
        except TypeError: pass
        self.animation.setStartValue(self.opacity_effect.opacity())
        self.animation.setEndValue(1.0)
        self.animation.start()

        self.hide_timer.start(timeout)

    def hide_animation(self):
        self.animation.stop()
        try: self.animation.finished.disconnect()
        except TypeError: pass
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.finished.connect(self.hide)
        self.animation.start()
        
#=========================================================================================
# BÖLÜM 3: SAYFA WIDGET'LARI
#=========================================================================================
class DashboardPage(QWidget):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.tx_channel = 90
        self.rx_channel = 80
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        top_controls_layout = QHBoxLayout()
        top_controls_layout.setSpacing(20)
        
        freq_frame = QGroupBox("HC-12 Kanal Ayarı")
        freq_layout = QHBoxLayout(freq_frame)
        self.knob = RotaryKnob()
        self.knob.setValue(self.rx_channel)
        
        self.tx_rx_switch = SwitchButton(text_on="TX", text_off="RX")
        self.tx_rx_switch.setFixedSize(120, 40)
        self.freq_set_button = QPushButton("🔧 Ayarla & Bildir")
        control_v_layout = QVBoxLayout()
        control_v_layout.addStretch()
        control_v_layout.addWidget(self.tx_rx_switch, 0, Qt.AlignCenter)
        control_v_layout.addSpacing(15)
        control_v_layout.addWidget(self.freq_set_button, 0, Qt.AlignCenter)
        control_v_layout.addStretch()
        freq_layout.addWidget(self.knob)
        freq_layout.addLayout(control_v_layout)
        top_controls_layout.addWidget(freq_frame)

        right_column_layout = QVBoxLayout()
        right_column_layout.setSpacing(20)

        mode_frame = QGroupBox("🚀 Sistem Kontrol Modu")
        mode_frame.setObjectName("modeControlFrame")
        mode_layout = QHBoxLayout(mode_frame)
        self.btn_autonomous_mode = QPushButton("🛰️ Otonom Mod")
        self.btn_manual_mode = QPushButton("🕹️ Manuel Mod")
        self.btn_autonomous_mode.setCheckable(True)
        self.btn_manual_mode.setCheckable(True)
        mode_layout.addWidget(self.btn_autonomous_mode)
        mode_layout.addWidget(self.btn_manual_mode)

        self.btn_start_sensors = QPushButton("🛰️ Sensörleri Başlat")
        mode_layout.addWidget(self.btn_start_sensors)

        right_column_layout.addWidget(mode_frame)

        self.control_frame = QGroupBox("🕹️ Motor Kontrol")
        control_layout = QVBoxLayout(self.control_frame)
        motor_row1_layout = QHBoxLayout()
        motor_row1_layout.addWidget(QLabel("Yön:"))
        self.direction_selector = QComboBox()
        apply_modern_combobox_style(self.direction_selector)
        self.direction_selector.addItems(["İleri", "Geri"])
        motor_row1_layout.addWidget(self.direction_selector, 1)
        motor_row1_layout.addWidget(QLabel("Hız:"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(0, 100)
        self.speed_slider.setValue(0)
        motor_row1_layout.addWidget(self.speed_slider, 2)
        self.speed_display = QLabel("0.00 m/s")
        self.speed_display.setMinimumWidth(70)
        motor_row1_layout.addWidget(self.speed_display)
        self.btn_motor_send = QPushButton("📤 Gönder")
        motor_row1_layout.addWidget(self.btn_motor_send)
        control_layout.addLayout(motor_row1_layout)
        self.emergency_button = QPushButton("🛑 ACİL DURDUR")
        self.emergency_button.setObjectName("emergencyButton")
        self.emergency_button.setCheckable(True) # <-- BUTONUN KİLİTLENMESİNİ SAĞLAYAN ÖNEMLİ SATIR
        control_layout.addWidget(self.emergency_button)
        right_column_layout.addWidget(self.control_frame)
        
        top_controls_layout.addLayout(right_column_layout, 1)
        main_layout.addLayout(top_controls_layout)
        
        self.freq_set_button.clicked.connect(self.on_set_frequency_clicked)
        self.tx_rx_switch.toggled.connect(self.on_hc12_switch_toggled)
        self.knob.valueChanged.connect(self.on_knob_changed)
        
        center_splitter = QSplitter(Qt.Horizontal)
        self.cards_widget = QWidget()
        cards_layout = QGridLayout(self.cards_widget)
        cards_layout.setSpacing(20)
        self.gps_card = ModernSensorCard("🛰️", "GPS Pozisyon", "blue")
        self.imu_card = ModernSensorCard("🧭", "IMU Yönelim", "green")
        self.lidar_card = ModernSensorCard("📡", "LIDAR Mesafe", "purple")
        self.water_card = ModernSensorCard("💧", "Su Sensörleri", "cyan")
        self.cards = [self.gps_card, self.imu_card, self.lidar_card, self.water_card]
        positions = [(i, j) for i in range(2) for j in range(2)]
        for pos, card in zip(positions, self.cards):
            cards_layout.addWidget(card, *pos)
        center_splitter.addWidget(self.cards_widget)
        map_frame = QFrame()
        map_frame.setObjectName("mapFrame")
        map_layout = QVBoxLayout(map_frame)
        map_layout.setContentsMargins(0,0,0,0)
        self.map_view = MapView()
        map_layout.addWidget(self.map_view)
        center_splitter.addWidget(map_frame)
        self.center_splitter = center_splitter
        main_layout.addWidget(center_splitter, 1)

    def on_hc12_switch_toggled(self, is_tx):
        self.knob.setUpdatesEnabled(False)
        self.knob.blockSignals(True)
        try:
            if is_tx:
                self.knob.setValue(self.tx_channel)
            else:
                self.knob.setValue(self.rx_channel)
        finally:
            self.knob.blockSignals(False)
            self.knob.setUpdatesEnabled(True)
            self.knob.update()

    def on_knob_changed(self, value):
        if self.tx_rx_switch._is_on:
            self.tx_channel = value
        else:
            self.rx_channel = value

    def on_set_frequency_clicked(self):
        self.main_window.set_frequency(self.tx_channel, self.rx_channel)

    def start_card_animations(self):
        for i, card in enumerate(self.cards):
            card.start_entrance_animation(i * 100)

class MissionPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        
        main_splitter = QSplitter(Qt.Horizontal)
        mission_controls_widget = QWidget()
        controls_layout = QVBoxLayout(mission_controls_widget)
        controls_layout.setContentsMargins(0,0,0,0)
        
        parkur_frame = QGroupBox("🎯 Parkur Veri Girişi")
        parkur_layout = QHBoxLayout(parkur_frame)
        parkur_layout.addWidget(QLabel("Veri Giriş Ekranı:"))
        self.parkur_selector = QComboBox()
        apply_modern_combobox_style(self.parkur_selector)
        self.parkur_selector.addItems(["1. Parkur (Nokta Takip)", "2. Parkur (Engel Kaçınma)", "3. Parkur (Angajman Renk Seçimi)"])
        parkur_layout.addWidget(self.parkur_selector, 1)
        controls_layout.addWidget(parkur_frame)

        self.mission_stack = QStackedWidget()
        controls_layout.addWidget(self.mission_stack, 1)
        
        self.btn_start_mission = QPushButton("🚀 TÜM GÖREVİ BAŞLAT")
        self.btn_start_mission.setObjectName("startButton")
        self.btn_start_mission.setMinimumHeight(40)
        controls_layout.addWidget(self.btn_start_mission)
        
        main_splitter.addWidget(mission_controls_widget)

        map_frame = QFrame()
        map_frame.setObjectName("mapFrame")
        wp_map_layout = QVBoxLayout(map_frame)
        wp_map_layout.setContentsMargins(0,0,0,0)
        self.mission_map = MapView()
        wp_map_layout.addWidget(self.mission_map)
        main_splitter.addWidget(map_frame)
        
        main_splitter.setSizes([self.width()//2, self.width()//2])
        layout.addWidget(main_splitter)

        self.waypoint_tab = QWidget()
        waypoint_layout = QVBoxLayout(self.waypoint_tab)
        waypoint_layout.setContentsMargins(0, 9, 0, 0)
        waypoint_layout.setSpacing(10)
        waypoint_layout.setAlignment(Qt.AlignTop)
        self.coord_inputs = []
        self.send_waypoint_buttons = []
        for i in range(4):
            point_group_box = QGroupBox(f"📍 Görev Noktası {i+1}")
            point_layout = QHBoxLayout(point_group_box)
            coord = QLineEdit()
            
            coord.setInputMask("00.000000 00.000000;_")
            coord.setPlaceholderText("Enlem Boylam (örn: 41.008234 28.978359)")
            
            btn = QPushButton(f"Gönder")
            btn.setFixedWidth(100)
            point_layout.addWidget(QLabel("Koordinat:"))
            point_layout.addWidget(coord, 1)
            point_layout.addWidget(btn)
            waypoint_layout.addWidget(point_group_box)
            self.coord_inputs.append(coord)
            self.send_waypoint_buttons.append(btn)
        
        self.parkur2_tab = QWidget()
        parkur2_layout = QVBoxLayout(self.parkur2_tab)
        parkur2_layout.setAlignment(Qt.AlignTop)
        parkur2_layout.setSpacing(15)
        final_target_frame = QGroupBox("Final Hedef Noktası")
        final_target_layout = QHBoxLayout(final_target_frame)
        self.final_target_coord_input = QLineEdit()
        
        self.final_target_coord_input.setInputMask("00.000000 00.000000;_")
        self.final_target_coord_input.setPlaceholderText("Enlem Boylam (örn: 37.181900 33.215400)")

        self.btn_send_final_target = QPushButton("🎯 Final Hedefi Gönder")
        final_target_layout.addWidget(QLabel("Koordinat:"))
        final_target_layout.addWidget(self.final_target_coord_input, 1)
        final_target_layout.addWidget(self.btn_send_final_target)
        parkur2_layout.addWidget(final_target_frame)
        parkur2_layout.addStretch()

        self.color_tab = QWidget()
        color_layout = QVBoxLayout(self.color_tab)
        color_layout.setSpacing(15)
        color_layout.setAlignment(Qt.AlignTop)
        color_frame = QGroupBox("🎨 Renk Seçimi")
        color_selection_layout = QHBoxLayout(color_frame)
        self.color_selector = QComboBox()
        apply_modern_combobox_style(self.color_selector)
        self.color_selector.addItems(["KIRMIZI", "YEŞİL", "MAVİ", "YOK/TANIMSIZ"])
        self.btn_send_color = QPushButton("🎨 Renk Kodu Gönder")
        color_selection_layout.addWidget(QLabel("Hedef Renk:"))
        color_selection_layout.addWidget(self.color_selector, 1)
        color_selection_layout.addWidget(self.btn_send_color)
        color_layout.addWidget(color_frame)
        color_preview_frame = QGroupBox("Renk Önizleme")
        color_preview_layout = QHBoxLayout(color_preview_frame)
        color_preview_layout.setAlignment(Qt.AlignCenter)
        self.red_box = QFrame()
        self.red_box.setFixedSize(60, 60)
        self.red_box.setObjectName("colorBox")
        self.green_box = QFrame()
        self.green_box.setFixedSize(60, 60)
        self.green_box.setObjectName("colorBox")
        self.blue_box = QFrame()
        self.blue_box.setFixedSize(60, 60)
        self.blue_box.setObjectName("colorBox")
        color_preview_layout.addWidget(self.red_box)
        color_preview_layout.addWidget(self.green_box)
        color_preview_layout.addWidget(self.blue_box)
        color_layout.addWidget(color_preview_frame)
        self.label_color_status = QLabel("Renk seçimi gönderilecek.")
        color_layout.addWidget(self.label_color_status)

        self.mission_stack.addWidget(self.waypoint_tab)
        self.mission_stack.addWidget(self.parkur2_tab)
        self.mission_stack.addWidget(self.color_tab)
        
        self.parkur_selector.currentIndexChanged.connect(self.mission_stack.setCurrentIndex)
        self.mission_stack.currentChanged.connect(self.toggle_mission_visuals)

    def toggle_mission_visuals(self, index):
        if index == 2:
             self.update_color_preview(None)
             self.label_color_status.setText("Renk seçimi gönderilecek.")

    def update_color_preview(self, selected_color_text):
        default_style = "border: 2px solid #555;"
        highlight_style = "border: 3px solid yellow;"
        self.red_box.setStyleSheet(f"background-color: #E74C3C; {highlight_style if selected_color_text == 'KIRMIZI' else default_style} border-radius: 5px;")
        self.green_box.setStyleSheet(f"background-color: #2ECC71; {highlight_style if selected_color_text == 'YEŞİL' else default_style} border-radius: 5px;")
        self.blue_box.setStyleSheet(f"background-color: #589EDC; {highlight_style if selected_color_text == 'MAVİ' else default_style} border-radius: 5px;")

class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        pid_group = QGroupBox("🔧 PID Kontrol Parametreleri")
        pid_layout = QGridLayout(pid_group)
        
        pid_layout.addWidget(QLabel("Kp:"), 0, 0)
        self.kp_input = QDoubleSpinBox()
        pid_layout.addWidget(self.kp_input, 0, 1)
        self.kp_input.setRange(0.0, 10.0)
        self.kp_input.setSingleStep(0.1)
        self.kp_input.setValue(1.5)
        self.kp_input.setDecimals(2)
        
        pid_layout.addWidget(QLabel("Ki:"), 1, 0)
        self.ki_input = QDoubleSpinBox()
        pid_layout.addWidget(self.ki_input, 1, 1)
        self.ki_input.setRange(0.0, 10.0)
        self.ki_input.setSingleStep(0.01)
        self.ki_input.setValue(0.1)
        self.ki_input.setDecimals(2)
        
        pid_layout.addWidget(QLabel("Kd:"), 2, 0)
        self.kd_input = QDoubleSpinBox()
        pid_layout.addWidget(self.kd_input, 2, 1)
        self.kd_input.setRange(0.0, 10.0)
        self.kd_input.setSingleStep(0.01)
        self.kd_input.setValue(0.05)
        self.kd_input.setDecimals(2)
        
        pid_layout.addWidget(QLabel("Integral Limiti:"), 3, 0)
        self.int_limit_input = QDoubleSpinBox()
        pid_layout.addWidget(self.int_limit_input, 3, 1)
        self.int_limit_input.setRange(0.0, 50.0)
        self.int_limit_input.setSingleStep(1.0)
        self.int_limit_input.setValue(10.0)
        self.int_limit_input.setDecimals(1)
        
        pid_layout.setRowStretch(4, 1)
        self.send_pid_btn = QPushButton("📤 PID Değerlerini Gönder")
        pid_layout.addWidget(self.send_pid_btn, 5, 0, 1, 2)
        main_layout.addWidget(pid_group)
        main_layout.addStretch()

class LogsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        
        log_frame = QGroupBox("📝 Sistem Günlükleri")
        log_layout = QVBoxLayout(log_frame)
        log_controls = QHBoxLayout()
        self.log_filter = QComboBox()
        apply_modern_combobox_style(self.log_filter)
        self.log_filter.addItems(["Tüm Loglar", "Hata", "Uyarı", "Bilgi", "Başarı", "Gelen Veri (Rx)", "Giden Komut (Tx)"])
        self.btn_clear_logs = QPushButton("🗑️ Temizle")
        log_controls.addWidget(QLabel("Filtre:"))
        log_controls.addWidget(self.log_filter, 1)
        log_controls.addWidget(self.btn_clear_logs)
        log_layout.addLayout(log_controls)
        self.status_box = QTextEdit()
        self.status_box.setReadOnly(True)
        log_layout.addWidget(self.status_box, 1)
        layout.addWidget(log_frame, 1)
        
        self.status_labels = {}
        status_frame = QGroupBox("🔍 Sistem Durumu (Genel)")
        status_layout = QGridLayout(status_frame)
        
        components = [
            ("GPS", "label_status_gps"),("IMU", "label_status_imu"), 
            ("Lidar", "label_status_lidar"),("Su Sens.", "label_status_water"), 
            ("Motor", "label_status_motor"), ("İletişim", "label_status_comm"),
            ("Yazılım", "label_status_software")
        ]
        cols = 4
        for i, (name, key) in enumerate(components):
            row, col = divmod(i, cols)
            status_label = QLabel(f"⚫ {name}")
            status_label.setStyleSheet("font-weight: bold;")
            status_layout.addWidget(status_label, row, col)
            self.status_labels[key] = status_label

        layout.addWidget(status_frame)

    def update_status_indicator(self, label_key, status, base_text):
        if label_key in self.status_labels:
            label = self.status_labels[label_key]
            icon = {"ok": "🟢", "warning": "🟡", "error": "🔴"}.get(status, "⚫")
            label.setText(f"{icon} {base_text}")

#=========================================================================================
# ANA UYGULAMA PENCERESİ
#=========================================================================================
class TunaModernGCS(QWidget):
    gps_packet_received = pyqtSignal(dict)
    lidar_packet_received = pyqtSignal(dict)
    imu_packet_received = pyqtSignal(dict)
    water_packet_received = pyqtSignal(list)
    log_message_received = pyqtSignal(str, str)
    graph_data_received = pyqtSignal(dict)
    
    ### DEĞİŞİKLİK BAŞLANGICI ###
    waypoint_completed = pyqtSignal(int, int)
    ### DEĞİŞİKLİK SONU ###
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TUNA Modern YKI - GÜNCEL PROTOKOL")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.resize(1600, 900)
        self.serial_port_tx = None
        self.serial_port_rx = None
        self.last_ms_packet_time = 0
        self.last_s_packet_time = 0
        self.last_ls_packet_time = 0
        self.last_lidar_packet_time = 0
        self.emergency_active = False

        ### YENİ EKLENEN KOD BAŞLANGICI ###
        # Acil durum sinyalini tekrarlı göndermek için bir zamanlayıcı oluşturun
        self.emergency_timer = QTimer(self)
        self.emergency_timer.setInterval(150) # Her 150 milisaniyede bir sinyal gönderir
        self.emergency_timer.timeout.connect(self.send_emergency_signal_repeatedly)
        ### YENİ EKLENEN KOD SONU ###
        
        self.all_logs = []

        self.sidebar_expanded = False
        self.SIDEBAR_COLLAPSED_WIDTH = 80
        self.SIDEBAR_EXPANDED_WIDTH = 280
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.create_sidebar()
        main_layout.addWidget(self.sidebar)
        
        self.create_content_area()
        main_layout.addWidget(self.content_area, 1)
        
        self.sidebar_animation = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self.sidebar_animation.setDuration(300)
        self.sidebar_animation.setEasingCurve(QEasingCurve.InOutCubic)

        self.notification_widget = NotificationWidget(self)
        self.notification_widget.hide()

        self.setStyleSheet(self.get_modern_styles())
        
        self.log_message_received.connect(self.handle_log_message)
        
        self.connect_signals()
        
        self.gps_packet_received.connect(self.handle_gps_packet)
        self.lidar_packet_received.connect(self.handle_lidar_packet)
        self.imu_packet_received.connect(self.handle_imu_packet)
        self.water_packet_received.connect(self.handle_water_packet)

        if SIMULATOR_MODE:
            self.simulator_thread_handle = threading.Thread(target=self.simulator_thread, daemon=True)
            self.simulator_thread_handle.start()
        else:
            self.read_thread = threading.Thread(target=self.read_from_rx_concatenated_text, daemon=True)
            self.read_thread.start()
        
        self.ui_update_timer = QTimer(self)
        self.ui_update_timer.timeout.connect(self.update_ui)
        self.ui_update_timer.start(500)
        
        self.set_initial_mode_ui(True)

    def create_sidebar(self):
        self.sidebar = QFrame()
        self.sidebar.setObjectName("modernSidebar")
        self.sidebar.setFixedWidth(self.SIDEBAR_COLLAPSED_WIDTH)
        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(0, 32, 0, 32)
        layout.setSpacing(24)
        self.sidebar_text_widgets = []
        logo_container = QFrame()
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(16, 16, 16, 16)
        self.app_title = QLabel("TUNA")
        self.app_title.setObjectName("appTitle")
        self.app_title.setAlignment(Qt.AlignCenter) 
        subtitle = QLabel("Yer Kontrol İstasyonu")
        subtitle.setObjectName("appSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        self.app_title.original_text = "TUNA"
        self.app_title.collapsed_text = "T"
        subtitle.original_text = "Yer Kontrol İstasyonu"
        self.sidebar_text_widgets.append(self.app_title)
        self.sidebar_text_widgets.append(subtitle)
        logo_layout.addWidget(self.app_title)
        logo_layout.addWidget(subtitle)
        layout.addWidget(logo_container)
        nav_container = QFrame()
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(16, 0, 16, 0)
        nav_layout.setSpacing(8)
        menu_items = [("🛰️", "Ana Kontrol", "Canlı veri ve manuel kontrol"),("🎯", "Görev Planlama", "Rota ve görev yönetimi"),("🔧", "Ayarlar", "PID ve diğer parametreler"),("📝", "Günlükler", "Sistem kayıtları ve durum")]
        self.nav_buttons = []
        for icon, title_text, desc_text in menu_items:
            btn = self.create_nav_button(icon, title_text, desc_text)
            self.nav_buttons.append(btn)
            nav_layout.addWidget(btn)
        layout.addWidget(nav_container)
        layout.addStretch()
        status_container = QFrame()
        status_container.setObjectName("statusContainer")
        status_layout = QVBoxLayout(status_container)
        status_layout.setContentsMargins(16, 16, 16, 16)
        self.label_tx_status = QLabel("TX: 🔌 Bekleniyor...")
        self.label_tx_status.setObjectName("connectionStatus")
        self.label_rx_status = QLabel("RX: 🔌 Bekleniyor...")
        self.label_rx_status.setObjectName("connectionStatus")
        self.label_tx_status.original_text = "TX: 🔌 Bekleniyor..."
        self.label_rx_status.original_text = "RX: 🔌 Bekleniyor..."
        self.sidebar_text_widgets.append(self.label_tx_status)
        self.sidebar_text_widgets.append(self.label_rx_status)
        status_layout.addWidget(self.label_tx_status)
        status_layout.addWidget(self.label_rx_status)
        layout.addWidget(status_container)
        self.toggle_sidebar_texts(False)

    def create_nav_button(self, icon, title, description):
        button = QPushButton()
        button.setObjectName("modernNavButton")
        button.setCheckable(True)
        button.setFixedHeight(70)
        button.setProperty("collapsed", True)
        btn_layout = QHBoxLayout(button)
        btn_layout.setContentsMargins(0, 12, 0, 12) 
        btn_layout.setSpacing(16)
        icon_label = QLabel(icon)
        icon_label.setObjectName("navIcon")
        icon_label.setFixedSize(32, 32)
        icon_label.setAlignment(Qt.AlignCenter)
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0,0,0,0) 
        title_label = QLabel(title)
        title_label.setObjectName("navTitle")
        desc_label = QLabel(description)
        desc_label.setObjectName("navDescription")
        title_label.original_text = title
        desc_label.original_text = description
        text_widget.original_text_widgets = [title_label, desc_label]
        self.sidebar_text_widgets.append(text_widget) 
        text_layout.addWidget(title_label)
        text_layout.addWidget(desc_label)
        btn_layout.addWidget(icon_label)
        btn_layout.addWidget(text_widget, 1) 
        button.clicked.connect(lambda: self.switch_page(self.nav_buttons.index(button), button))
        return button

    def create_content_area(self):
        self.content_area = QFrame()
        self.content_area.setObjectName("contentArea")
        layout = QVBoxLayout(self.content_area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.create_title_bar()
        layout.addWidget(self.title_bar)
        self.pages = QStackedWidget()
        self.pages.setObjectName("pageStack")
        self.dashboard_page = DashboardPage(self)
        self.mission_page = MissionPage(self)
        self.settings_page = SettingsPage(self)
        self.logs_page = LogsPage()
        self.pages.addWidget(self.dashboard_page)
        self.pages.addWidget(self.mission_page)
        self.pages.addWidget(self.settings_page)
        self.pages.addWidget(self.logs_page)
        layout.addWidget(self.pages, 1)

    def create_title_bar(self):
        self.title_bar = QFrame()
        self.title_bar.setObjectName("titleBar")
        self.title_bar.setFixedHeight(60)
        layout = QHBoxLayout(self.title_bar)
        layout.setContentsMargins(32, 16, 24, 16)
        self.page_title = QLabel("Ana Kontrol Paneli")
        self.page_title.setObjectName("pageTitle")
        layout.addWidget(self.page_title)
        layout.addStretch()
        self.label_time = QLabel("⏰ --:--:--")
        self.label_time.setObjectName("timeLabel")
        layout.addWidget(self.label_time)
        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.setContentsMargins(20, 0, 0, 0)
        minimize_btn = QPushButton()
        minimize_btn.setObjectName("minimizeBtn")
        minimize_btn.setFixedSize(16, 16)
        minimize_btn.clicked.connect(self.showMinimized)
        maximize_btn = QPushButton()
        maximize_btn.setObjectName("maximizeBtn")
        maximize_btn.setFixedSize(16, 16)
        maximize_btn.clicked.connect(self.toggle_maximize)
        close_btn = QPushButton()
        close_btn.setObjectName("closeBtn")
        close_btn.setFixedSize(16, 16)
        close_btn.clicked.connect(self.close)
        controls.addWidget(minimize_btn)
        controls.addWidget(maximize_btn)
        controls.addWidget(close_btn)
        layout.addLayout(controls)
        
    def expand_sidebar(self, event):
        if not self.sidebar_expanded:
            self.sidebar_expanded = True
            try: self.sidebar_animation.finished.disconnect()
            except TypeError: pass
            self.toggle_sidebar_texts(True)
            self.sidebar_animation.setStartValue(self.sidebar.width())
            self.sidebar_animation.setEndValue(self.SIDEBAR_EXPANDED_WIDTH)
            self.sidebar_animation.start()
        event.accept()

    def collapse_sidebar(self, event):
        if self.sidebar_expanded:
            self.sidebar_expanded = False
            try: self.sidebar_animation.finished.disconnect()
            except TypeError: pass
            self.sidebar_animation.finished.connect(self.on_sidebar_collapse_finished)
            self.sidebar_animation.setStartValue(self.sidebar.width())
            self.sidebar_animation.setEndValue(self.SIDEBAR_COLLAPSED_WIDTH)
            self.sidebar_animation.start()
        event.accept()
        
    def on_sidebar_collapse_finished(self):
        if not self.sidebar_expanded:
            self.toggle_sidebar_texts(False)

    def toggle_sidebar_texts(self, show):
        for btn in self.nav_buttons:
            btn.setProperty("collapsed", not show)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        for widget in self.sidebar_text_widgets:
            if widget == self.app_title:
                widget.setText(widget.original_text if show else widget.collapsed_text)
            elif isinstance(widget, QWidget) and hasattr(widget, 'original_text_widgets'):
                widget.setVisible(show)
            elif hasattr(widget, 'original_text'):
                if widget.original_text:
                    widget.setText(widget.original_text if show else "")
        self.update_connection_status()

    def switch_page(self, index, button):
        for btn in self.nav_buttons:
            btn.setChecked(btn == button)
        self.pages.setCurrentIndex(index)
        titles = ["Ana Kontrol Paneli", "Görev Planlama", "Sistem Ayarları", "Sistem Günlükleri"]
        self.page_title.setText(titles[index])
        
    def showEvent(self, event):
        super().showEvent(event)
        initial_width = self.dashboard_page.width()
        if initial_width > 200:
            self.dashboard_page.center_splitter.setSizes([int(initial_width * 0.6), int(initial_width * 0.4)])
        QTimer.singleShot(100, self.dashboard_page.start_card_animations)
    
    # === HABERLEŞME FONKSİYONLARI ===

    def send_data_concatenated(self, command_str, log_message_prefix=""):
        if self.serial_port_tx and self.serial_port_tx.is_open:
            try:
                full_command = command_str + '\n'
                self.serial_port_tx.write(full_command.encode('ascii'))
                self.serial_port_tx.flush()
                self.log_message(f"{log_message_prefix}: {command_str}", "send")
                return True
            except Exception as e:
                self.log_message(f"Metin gönderme hatası ({log_message_prefix}): {e}", "error")
        else:
            self.log_message(f"{log_message_prefix} GÖNDERİLEMEDİ: TX Portu kapalı.", "error")
        return False

    def _threaded_send_worker(self, command_str, log_prefix):
        """Bu fonksiyon, komut gönderme döngüsünü arkaplan thread'inde çalıştırır."""
        for i in range(33):
            if not self.serial_port_tx or not self.serial_port_tx.is_open:
                # Eğer döngü sırasında port kapanırsa, işlemi sonlandır.
                self.log_message(f"Gönderim iptal edildi (Port kapandı): {log_prefix}", "warning")
                break
            self.send_data_concatenated(command_str, f"{log_prefix} ({i+1}/33)")
            time.sleep(0.05) # Seri portu ve alıcıyı boğmamak için küçük bir bekleme

    def _send_command(self, command_str, log_prefix, feedback_message):
        """Arayüzden gelen komutları alır ve arkaplan thread'inde gönderilmek üzere başlatır."""
        self.show_feedback(feedback_message, "send")
        # Gönderme işlemini arkaplan thread'ine devret
        thread = threading.Thread(
            target=self._threaded_send_worker,
            args=(command_str, log_prefix),
            daemon=True  # Ana uygulama kapandığında thread'in de kapanmasını sağlar
        )
        thread.start()


    def read_from_rx_concatenated_text(self):
        while True:
            if not self.serial_port_rx or not self.serial_port_rx.is_open:
                time.sleep(0.5); continue
            try:
                if self.serial_port_rx.in_waiting > 0:
                    packet_str = self.serial_port_rx.readline().decode('ascii', errors='ignore').strip()
                    if packet_str:
                        self.log_message(f"Ham veri alındı: {packet_str}", "recv")
                        self.process_concatenated_text_packet(packet_str)
            except Exception as e:
                self.log_message(f"Veri işleme hatası: {e}", "error")
            time.sleep(0.02)
            
    def process_concatenated_text_packet(self, packet_str):
        if len(packet_str) < 2: return
        try:
            # GPS Paketi (ID: 01)
            if packet_str.startswith("01-"):
                parts = packet_str.split('-')
                if len(parts) == 9:
                    lat_str, lon_str = parts[1], parts[2]
                    packet_data = {
                        'lat': float(f"{lat_str[0:2]}.{lat_str[2:]}"),
                        'lon': float(f"{lon_str[0:2]}.{lon_str[2:]}"),
                        'alt': int(parts[3]), 'sat': int(parts[4]),
                        'hdop': float(parts[5]) / 10.0, 'speed': int(parts[6]),
                        'minute': int(parts[7]), 'second': int(parts[8])
                    }
                    self.gps_packet_received.emit(packet_data)
                else:
                    self.log_message(f"Paket 01 (GPS) formatı hatalı. Gelen: {packet_str}", "error")
                return

            # YENİ DETAYLI IMU FORMATI (ID: 03)
            if packet_str.startswith("03-"):
                parts = packet_str.split('-')
                if len(parts) == 5:
                     # Her bir veri parçasının beklenen uzunlukta olduğunu kontrol et
                    if all(len(p) == 4 for p in parts[1:]):
                        # Veri formatı: 1. karakter işaret (0: negatif, 1: pozitif), kalan 3 karakter değer.
                        # Roll, Pitch, Yaw: Değer doğrudan okunur. Örn: "1021" -> +21
                        # Sıcaklık: Değer 10'a bölünür. Örn: "1268" -> +26.8
                        
                        # Roll (X Angle)
                        roll_str = parts[1]
                        roll_sign = 1.0 if roll_str[0] == '1' else -1.0
                        roll = roll_sign * int(roll_str[1:])

                        # Pitch (Y Angle)
                        pitch_str = parts[2]
                        pitch_sign = 1.0 if pitch_str[0] == '1' else -1.0
                        pitch = pitch_sign * int(pitch_str[1:])

                        # Yaw (Z Angle)
                        yaw_str = parts[3]
                        yaw_sign = 1.0 if yaw_str[0] == '1' else -1.0
                        yaw = yaw_sign * int(yaw_str[1:])

                        # Temperature
                        temp_str = parts[4]
                        temp_sign = 1.0 if temp_str[0] == '1' else -1.0
                        temp = temp_sign * (float(temp_str[1:]) / 10.0)
                        
                        packet_data = {'pitch': pitch, 'roll': roll, 'yaw': yaw, 'temp': temp}
                        self.imu_packet_received.emit(packet_data)
                    else:
                        self.log_message(f"Paket 03 (IMU) formatı hatalı. Veri parçaları 4 karakter olmalı. Gelen: {packet_str}", "error")
                else:
                    self.log_message(f"Paket 03 (IMU) formatı hatalı. Parça sayısı: {len(parts)}, Beklenen: 5. Gelen: {packet_str}", "error")
                return

            # Diğer paketler için eski yöntem
            packet_id = int(packet_str[0:2])
            data = packet_str[2:]
            
            if packet_id == 2: # LIDAR
                if len(data) >= 23:
                    packet_data = {'angle': int(data[0:3]), 'distance': float(data[3:7]) / 100.0}
                    self.lidar_packet_received.emit(packet_data)
                else:
                    self.log_message(f"Paket 02 (LIDAR) uzunluğu hatalı. Gelen: {len(data)}, Beklenen: 23", "error")

            elif packet_id == 4: # Su Sensörleri
                if len(data) >= 10:
                    sensor_data = [int(val) for val in data[0:10]]
                    self.water_packet_received.emit(sensor_data)
                else:
                    self.log_message(f"Paket 04 (Su Sensör) uzunluğu hatalı. Gelen: {len(data)}, Beklenen: 10", "error")
            
            elif packet_id == 15: # Görev Durum Paketi
                if len(data) >= 4:
                    parkur_no, gorev_no = int(data[0:2]), int(data[2:4])
                    self.waypoint_completed.emit(parkur_no, gorev_no)
                else:
                    self.log_message(f"Paket 15 formatı hatalı. Gelen: {packet_str}", "error")
            
            elif packet_id == 6:
                self.log_message(f"Paket 06 (Acil Durum Yanıtı) alındı: {data}", "recv")
                
            else: 
                self.log_message(f"Bilinmeyen veya işlenmeyen paket ID'si: {packet_id:02d}", "warning")

        except (ValueError, IndexError) as e:
            self.log_message(f"Paket '{packet_str}' ayrıştırılamadı. Hata: {e}", "error")

    # =========================================================================================
    # ARAYÜZÜN DİĞER YARDIMCI FONKSİYONLARI
    # =========================================================================================
    
    def connect_signals(self):
        self.sidebar.enterEvent = self.expand_sidebar
        self.sidebar.leaveEvent = self.collapse_sidebar
        self.dashboard_page.speed_slider.valueChanged.connect(self.update_speed_display)
        self.dashboard_page.btn_motor_send.clicked.connect(self.ui_send_motor_command)
        self.dashboard_page.emergency_button.toggled.connect(self.toggle_emergency)
        
        self.dashboard_page.btn_autonomous_mode.clicked.connect(self.ui_set_autonomous_mode)
        self.dashboard_page.btn_manual_mode.clicked.connect(self.ui_set_manual_mode)
        
        self.dashboard_page.btn_start_sensors.clicked.connect(self.ui_send_start_sensors_command)
        
        for i, btn in enumerate(self.mission_page.send_waypoint_buttons):
            btn.clicked.connect(lambda _, ix=i: self.ui_send_target_via_mission_command(ix))
        self.mission_page.btn_send_final_target.clicked.connect(self.ui_send_final_target_command)
        self.mission_page.btn_send_color.clicked.connect(self.ui_send_color_via_mission_command)
        self.mission_page.btn_start_mission.clicked.connect(self.ui_send_start_mission_command)
        self.settings_page.send_pid_btn.clicked.connect(self.ui_send_pid_parameters)
        self.logs_page.btn_clear_logs.clicked.connect(self.clear_logs)
        self.logs_page.log_filter.currentTextChanged.connect(self.apply_log_filter)
        
        self.waypoint_completed.connect(self.handle_waypoint_completed)

    ### YENİ VEYA GÜNCELLENMİŞ FONKSİYONLAR BAŞLANGICI ###

    def send_emergency_signal_repeatedly(self):
        """Timer tarafından tetiklenerek acil durum komutunu tekrarlı gönderir."""
        self.send_data_concatenated("060000000000", "ACİL DURUM SİNYALİ")

    def toggle_emergency(self, checked):
        """
        Acil durum butonuna basıldığında (toggle olduğunda) çalışır.
        'checked' parametresi butonun yeni durumunu belirtir (True: aktif, False: pasif).
        """
        self.emergency_active = checked
        dp = self.dashboard_page
        
        # Butonun stil özelliğini ayarla
        dp.emergency_button.setProperty("emergencyActive", checked)
        dp.emergency_button.style().unpolish(dp.emergency_button)
        dp.emergency_button.style().polish(dp.emergency_button)

        if checked:
            # BUTON AKTİF EDİLDİ (İLK BASIŞ)
            # Gönderimi durdurmak için ne yapılması gerektiğini belirten bir metin ayarla
            dp.emergency_button.setText("🔓 DURDURMAK İÇİN TEKRAR BAS")
            
            # Diğer kontrolleri devre dışı bırak
            dp.speed_slider.setEnabled(False)
            dp.direction_selector.setEnabled(False)
            dp.btn_motor_send.setEnabled(False)
            
            self.show_feedback("Acil durum sinyali gönderimi BAŞLADI!", "error")
            
            # Tekrarlı gönderim için zamanlayıcıyı BAŞLAT
            self.emergency_timer.start()
            
        else:
            # BUTON PASİF EDİLDİ (İKİNCİ BASIŞ)
            # Öncelikle tekrarlı gönderimi DURDUR
            self.emergency_timer.stop()
            
            # Buton metnini normale döndür
            dp.emergency_button.setText("🛑 ACİL DURDUR")
            
            # Kontrolleri mevcut moda göre tekrar aktif et
            is_manual = self.dashboard_page.btn_manual_mode.isChecked()
            dp.speed_slider.setEnabled(is_manual)
            dp.direction_selector.setEnabled(is_manual)
            dp.btn_motor_send.setEnabled(is_manual)
            
            # Acil durumu iptal etme komutunu SADECE BİR KEZ gönder
            command_str = "070"
            self._send_command(command_str, "Acil Durdur İptal", "Acil durum devreden çıkarıldı.")
            self.log_message("Acil durum sinyali gönderimi DURDURULDU.", "success")

    ### YENİ VEYA GÜNCELLENMİŞ FONKSİYONLAR SONU ###

    def log_message(self, message, level="info"):
        self.log_message_received.emit(message, level)

    @pyqtSlot(str, str)
    def handle_log_message(self, message, level):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        color_map = {"error": ("🔴", "#F48FB1"), "warning": ("⚠️", "#FFE082"), "success": ("✅", "#A5D6A7"), "send": ("📤", "#90CAF9"), "recv": ("📥", "#CE93D8"), "info": ("ℹ️", "#FFFFFF")}
        
        level_to_filter_text = {
            "error": "Hata",
            "warning": "Uyarı",
            "info": "Bilgi",
            "success": "Başarı",
            "recv": "Gelen Veri (Rx)",
            "send": "Giden Komut (Tx)"
        }

        icon, color = color_map.get(level, ("ℹ️", "#FFFFFF"))
        
        if hasattr(self, 'logs_page') and self.logs_page is not None:
            formatted_message = (f"<div data-level='{level}'><span style='color:#888;'>[{timestamp}]</span> <span style='color:{color};'>{icon} {message}</span></div>")
            
            self.all_logs.append((level, formatted_message))

            current_filter_text = self.logs_page.log_filter.currentText()
            log_category_text = level_to_filter_text.get(level, "Bilgi")

            if current_filter_text == "Tüm Loglar" or current_filter_text == log_category_text:
                self.logs_page.status_box.append(formatted_message)
                self.logs_page.status_box.verticalScrollBar().setValue(self.logs_page.status_box.verticalScrollBar().maximum())

    def clear_logs(self):
        self.all_logs.clear() 
        self.logs_page.status_box.clear()
        self.log_message("Loglar temizlendi.", "info")
        self.show_feedback("Loglar temizlendi.", "info")

    def apply_log_filter(self, filter_text):
        if not hasattr(self, 'logs_page') or not hasattr(self, 'all_logs'):
            return

        self.logs_page.status_box.clear()
        
        filter_text_to_level = {
            "Hata": "error",
            "Uyarı": "warning",
            "Bilgi": "info",
            "Başarı": "success",
            "Gelen Veri (Rx)": "recv",
            "Giden Komut (Tx)": "send"
        }
        
        target_level = filter_text_to_level.get(filter_text)

        for level, formatted_message in self.all_logs:
            if filter_text == "Tüm Loglar" or level == target_level:
                self.logs_page.status_box.append(formatted_message)
        
        self.logs_page.status_box.verticalScrollBar().setValue(self.logs_page.status_box.verticalScrollBar().maximum())

    def _configure_hc12_channel(self, serial_port, channel, port_label="HC12"):
        if not serial_port or not serial_port.is_open:
            self.log_message(f"{port_label} kanalı ayarlanamıyor: Port kapalı.", "warning")
            return False
        try:
            if not 1 <= channel <= 127:
                self.log_message(f"{port_label} için geçersiz kanal: {channel}.", "error")
                return False
            cmd = f'AT+C{channel:03d}\r\n'.encode('ascii')
            serial_port.write(cmd)
            time.sleep(0.5)
            response = serial_port.read(serial_port.in_waiting).decode('ascii').strip()
            if "OK" in response:
                self.log_message(f"{port_label} kanalı başarıyla {channel} olarak ayarlandı.", "success")
                self.show_feedback(f"{port_label} kanalı {channel} yapıldı.", "success")
                return True
            else:
                self.log_message(f"{port_label} kanalı ayarlandı ancak 'OK' yanıtı alınamadı. Yanıt: {response}", "warning")
                self.show_feedback(f"{port_label} yanıtı: OK değil!", "warning")
                return True
        except Exception as e:
            self.log_message(f"Frekans ayar hatası ({port_label}): {e}", "error")
            self.show_feedback(f"{port_label} frekans hatası!", "error")
            return False

    def set_frequency(self, tx_channel, rx_channel):
        command_str = f"08{tx_channel:03d}{rx_channel:03d}"
        self._send_command(command_str, "Gemi HC-12 Kanal Ayarı", f"Kanal ayarı gönderiliyor: TX {tx_channel}, RX {rx_channel}")
        
        time.sleep(0.5)
        self.log_message(f"YKİ modülleri yeni kanallara ayarlanıyor...", "info")
        self._configure_hc12_channel(self.serial_port_tx, tx_channel, "YKİ_TX_Modül")
        if self.serial_port_tx != self.serial_port_rx:
            self._configure_hc12_channel(self.serial_port_rx, rx_channel, "YKİ_RX_Modül")

    def add_waypoint_to_maps(self, lat, lon, wp_id):
        self.dashboard_page.map_view.add_waypoint(lat, lon, wp_id)
        self.mission_page.mission_map.add_waypoint(lat, lon, wp_id)

    def ui_send_motor_command(self):
        if self.emergency_active:
            self.show_feedback("Acil durum aktif, motor komutu gönderilemez!", "warning")
            return
        speed_val = self.dashboard_page.speed_slider.value()
        direction = 1 if self.dashboard_page.direction_selector.currentText() == "İleri" else 0
        command_str = f"10{speed_val:03d}{direction:1d}"
        self._send_command(command_str, "Motor Komutu", "Motor komutu gönderiliyor...")
    
    def ui_send_pid_parameters(self):
        kp = int(self.settings_page.kp_input.value() * 100)
        ki = int(self.settings_page.ki_input.value() * 100)
        kd = int(self.settings_page.kd_input.value() * 100)
        limit = int(self.settings_page.int_limit_input.value() * 10)
        command_str = f"11{kp:04d}{ki:04d}{kd:04d}{limit:04d}"
        self._send_command(command_str, "PID Parametreleri", "PID değerleri gönderiliyor...")
            
    def ui_send_start_sensors_command(self):
        self._send_command("141", "Sensörleri Başlat Komutu", "Sensörleri başlatma komutu gönderiliyor...")

    def ui_send_target_via_mission_command(self, index):
        text = self.mission_page.coord_inputs[index].text()
        try:
            lat_str, lon_str = text.strip().split(' ')
            if not lat_str or not lon_str: raise ValueError("Boş koordinat")
            
            lat_int = int(lat_str.replace('.', ''))
            lon_int = int(lon_str.replace('.', ''))

            command_str = f"09{1:1d}{index + 1:03d}{lat_int:08d}{lon_int:08d}{0:02d}"
            self._send_command(command_str, "Görev Komutu", f"Görev Noktası {index+1} gönderiliyor...")
            
            lat_float, lon_float = float(lat_str), float(lon_str)
            self.add_waypoint_to_maps(lat_float, lon_float, index + 1)
        except Exception as e:
            self.log_message(f"Hedef {index+1} format hatası: '{text}'. Hata: {e}", "error")
            self.show_feedback(f"Hedef {index+1} formatı geçersiz.", "warning")

    def ui_send_final_target_command(self):
        text = self.mission_page.final_target_coord_input.text()
        try:
            lat_str, lon_str = text.strip().split(' ')
            if not lat_str or not lon_str: raise ValueError("Boş koordinat")
            
            lat_int = int(lat_str.replace('.', ''))
            lon_int = int(lon_str.replace('.', ''))
            
            command_str = f"09{2:1d}{1:03d}{lat_int:08d}{lon_int:08d}{0:02d}"
            self._send_command(command_str, "Görev Komutu", "Final hedefi gönderiliyor...")

            lat_float, lon_float = float(lat_str), float(lon_str)
            self.add_waypoint_to_maps(lat_float, lon_float, "F")
        except Exception as e:
            self.log_message(f"Final Hedef format hatası: '{text}'. Hata: {e}", "error")
            self.show_feedback("Final hedef formatı geçersiz.", "warning")

    def ui_send_color_via_mission_command(self):
        color_map = {"KIRMIZI": 1, "YEŞİL": 2, "MAVİ": 3, "YOK/TANIMSIZ": 0}
        color_text = self.mission_page.color_selector.currentText()
        renk_kodu = color_map.get(color_text, 0)
        
        command_str = f"09{3:1d}{0:03d}{0:08d}{0:08d}{renk_kodu:02d}"
        self._send_command(command_str, "Görev Komutu", f"Renk kodu ({color_text}) gönderiliyor...")
        self.mission_page.update_color_preview(color_text if renk_kodu != 0 else None)

    def ui_send_start_mission_command(self):
        self._send_command("121", "Tüm Görevi Başlat Komutu", "Tüm görevi başlatma komutu gönderiliyor...")

    def set_initial_mode_ui(self, is_autonomous):
        dp = self.dashboard_page
        mp = self.mission_page
        
        dp.btn_autonomous_mode.setChecked(is_autonomous)
        dp.btn_manual_mode.setChecked(not is_autonomous)

        dp.speed_slider.setEnabled(not is_autonomous)
        dp.direction_selector.setEnabled(not is_autonomous)
        dp.btn_motor_send.setEnabled(not is_autonomous)
        mp.btn_start_mission.setEnabled(is_autonomous)
        
        if not is_autonomous and not self.emergency_active:
            dp.speed_slider.setValue(0)

    def ui_set_autonomous_mode(self):
        self.set_initial_mode_ui(True)
        command_str = "131"
        self._send_command(command_str, "Kontrol Modu", "Otonom moda geçildi.")
        
    def ui_set_manual_mode(self):
        self.set_initial_mode_ui(False)
        command_str = "130"
        self._send_command(command_str, "Kontrol Modu", "Manuel moda geçildi.")

    @pyqtSlot(int, int)
    def handle_waypoint_completed(self, parkur_no, gorev_no):
        wp_id_to_remove = None
        log_message = ""

        if parkur_no == 1:
            wp_id_to_remove = gorev_no
            log_message = f"Parkur 1, Görev Noktası {gorev_no} tamamlandı."
        elif parkur_no == 2 and gorev_no == 1:
            wp_id_to_remove = 'F'
            log_message = "Parkur 2, Final Hedefine ulaşıldı."
        elif parkur_no == 3 and gorev_no == 1:
            log_message = "Parkur 3, Angajman sağlandı."
        
        if log_message:
            self.log_message(log_message, "success")
            self.show_feedback(log_message, "success")

        if wp_id_to_remove is not None:
            self.dashboard_page.map_view.remove_waypoint(wp_id_to_remove)
            self.mission_page.mission_map.remove_waypoint(wp_id_to_remove)

    @pyqtSlot(dict)
    def handle_gps_packet(self, data):
        lat, lon = data['lat'], data['lon']
        time_text = f"{data['minute']:02d}:{data['second']:02d}"
        gps_value_text = f"{lat:.6f}° N | {lon:.6f}° E\nHız: {data['speed']} cm/s | Saat: {time_text}"
        gps_status_text = f"{data['sat']} Uydu | HDOP: {data['hdop']:.1f} | İrtifa: {data['alt']} m"
        
        self.dashboard_page.gps_card.update_data(gps_value_text, gps_status_text, True)
        self.dashboard_page.map_view.update_position(lat, lon)
        self.mission_page.mission_map.update_position(lat, lon)
        self.last_ms_packet_time = time.time()

    @pyqtSlot(dict)
    def handle_lidar_packet(self, data):
        self.dashboard_page.lidar_card.update_data(f"{data['distance']:.2f} m", f"Açı: {data['angle']}°", True)
        self.last_lidar_packet_time = time.time()

    @pyqtSlot(dict)
    def handle_imu_packet(self, data):
        pitch, roll, yaw, temp = data['pitch'], data['roll'], data['yaw'], data['temp']
        # Açıları tam sayı, sıcaklığı tek ondalık olarak göster
        imu_value_text = f"Pitch: {pitch:.0f}° | Roll: {roll:.0f}°\nYaw: {yaw:.0f}°"
        imu_status_text = f"Sıcaklık: {temp:.1f}°C"
        
        self.dashboard_page.imu_card.update_data(imu_value_text, imu_status_text, True)
        current_pos = self.dashboard_page.map_view.current_pos
        # Haritadaki yön bilgisi için ondalıklı yaw değeri daha hassas olabilir, bu yüzden orijinal değeri kullanıyoruz.
        self.dashboard_page.map_view.update_position(current_pos[0], current_pos[1], yaw)
        self.mission_page.mission_map.update_position(current_pos[0], current_pos[1], yaw)
        self.last_s_packet_time = time.time()
        
    @pyqtSlot(list)
    def handle_water_packet(self, data):
        self.dashboard_page.water_card.update_data(' '.join(map(str, data)), "10 Sensör Aktif", True)
        self.last_ls_packet_time = time.time()

    def simulator_thread(self):
        pass

    def update_speed_display(self):
        speed_mps = (self.dashboard_page.speed_slider.value() / 100.0) * 5.0
        self.dashboard_page.speed_display.setText(f"{speed_mps:.2f} m/s")

    def check_comm_status(self):
        t = time.time()
        ms_ok = (t - self.last_ms_packet_time) <= 3.0
        s_ok = (t - self.last_s_packet_time) <= 3.0
        ls_ok = (t - self.last_ls_packet_time) <= 7.0
        lidar_ok = (t - self.last_lidar_packet_time) <= 3.0
        
        if self.dashboard_page.gps_card.is_active and not ms_ok: self.dashboard_page.gps_card.update_data("--", "Sinyal Yok", False)
        if self.dashboard_page.imu_card.is_active and not s_ok: self.dashboard_page.imu_card.update_data("--", "Sinyal Yok", False)
        if self.dashboard_page.water_card.is_active and not ls_ok: self.dashboard_page.water_card.update_data("--", "Sinyal Yok", False)
        if self.dashboard_page.lidar_card.is_active and not lidar_ok: self.dashboard_page.lidar_card.update_data("--", "Sinyal Yok", False)
        
        self.logs_page.update_status_indicator("label_status_gps", "ok" if ms_ok else "error", "GPS")
        self.logs_page.update_status_indicator("label_status_lidar", "ok" if lidar_ok else "error", "Lidar")
        self.logs_page.update_status_indicator("label_status_imu", "ok" if s_ok else "error", "IMU")
        self.logs_page.update_status_indicator("label_status_water", "ok" if ls_ok else "error", "Su Sens.")
        self.logs_page.update_status_indicator("label_status_comm", "ok" if ms_ok or s_ok else "error", "İletişim")

    def update_ui(self):
        self.label_time.setText(f"⏰ {datetime.now(timezone.utc).astimezone().strftime('%H:%M:%S')}")
        if not SIMULATOR_MODE:
            self.check_comm_status()
            self.update_connection_status()

    def update_connection_status(self):
        if SIMULATOR_MODE:
            # Simülatör modu için durum ayarları
            tx_text_expanded, rx_text_expanded = "TX: 🔵 Simülatör", "RX: 🔵 Simülatör"
            tx_text_collapsed, rx_text_collapsed = "TX 🔵", "RX 🔵"
            style = "color: #3b82f6; font-weight: bold;"
            self.label_tx_status.setStyleSheet(style)
            self.label_rx_status.setStyleSheet(style)
        else:
            # Gerçek donanım modu
            try:
                available_ports = [p.device for p in serial.tools.list_ports.comports()]
                if SERIAL_PORT_TX_NAME in available_ports:
                    if not (self.serial_port_tx and self.serial_port_tx.is_open):
                        self.serial_port_tx = serial.Serial(SERIAL_PORT_TX_NAME, BAUD_RATE, timeout=0.5, write_timeout=0.5)
                else:
                    if self.serial_port_tx and self.serial_port_tx.is_open:
                        self.serial_port_tx.close()
                    self.serial_port_tx = None

                if SERIAL_PORT_TX_NAME == SERIAL_PORT_RX_NAME:
                    self.serial_port_rx = self.serial_port_tx
                else:
                    if SERIAL_PORT_RX_NAME in available_ports:
                        if not (self.serial_port_rx and self.serial_port_rx.is_open):
                            self.serial_port_rx = serial.Serial(SERIAL_PORT_RX_NAME, BAUD_RATE, timeout=0.1)
                    else:
                        if self.serial_port_rx and self.serial_port_rx.is_open:
                            self.serial_port_rx.close()
                        self.serial_port_rx = None
            except Exception as e: 
                self.log_message(f"Seri port durum güncelleme hatası: {e}", "error")
                if self.serial_port_tx: self.serial_port_tx.close()
                if self.serial_port_rx: self.serial_port_rx.close()
                self.serial_port_tx, self.serial_port_rx = None, None

            tx_ok = self.serial_port_tx and self.serial_port_tx.is_open
            rx_ok = self.serial_port_rx and self.serial_port_rx.is_open
            
            tx_text_expanded = "TX: 🟢 Aktif" if tx_ok else "TX: 🔴 Kopuk!"
            tx_text_collapsed = "TX 🟢" if tx_ok else "TX 🔴"
            self.label_tx_status.setStyleSheet("color: #10b981; font-weight: bold;" if tx_ok else "color: #ef4444; font-weight: bold;")
            rx_text_expanded = "RX: 🟢 Aktif" if rx_ok else "RX: 🔴 Kopuk!"
            rx_text_collapsed = "RX 🟢" if rx_ok else "RX 🔴"
            self.label_rx_status.setStyleSheet("color: #10b981; font-weight: bold;" if rx_ok else "color: #ef4444; font-weight: bold;")

        if self.sidebar_expanded:
            self.label_tx_status.setText(tx_text_expanded)
            self.label_rx_status.setText(rx_text_expanded)
        else:
            self.label_tx_status.setText(tx_text_collapsed)
            self.label_rx_status.setText(rx_text_collapsed)
            
        self.label_tx_status.original_text = tx_text_expanded
        self.label_rx_status.original_text = rx_text_expanded

    def closeEvent(self, event):
        if self.ui_update_timer: self.ui_update_timer.stop()
        if self.serial_port_tx and self.serial_port_tx.is_open: self.serial_port_tx.close()
        if self.serial_port_rx and self.serial_port_rx.is_open and self.serial_port_rx != self.serial_port_tx: self.serial_port_rx.close()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_notification()

    def position_notification(self):
        if not hasattr(self, 'notification_widget'): return
        self.notification_widget.adjustSize()
        margin = 20
        x = self.width() - self.notification_widget.width() - margin
        y = self.height() - self.notification_widget.height() - margin
        self.notification_widget.move(x, y)

    def show_feedback(self, message, level="info"):
        if hasattr(self, 'notification_widget'):
            self.notification_widget.show_notification(message, level)
            
    def toggle_maximize(self): self.showMaximized() if not self.isMaximized() else self.showNormal()
    def mousePressEvent(self, event): self.drag_pos = event.globalPos()
    def mouseMoveEvent(self, event): self.move(self.pos() + event.globalPos() - self.drag_pos); self.drag_pos = event.globalPos()

    def get_modern_styles(self):
        return """
        QWidget { font-family: 'Segoe UI', 'Arial', sans-serif; color: #e5e7eb; background-color: transparent; }
        TunaModernGCS { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0a0a0b, stop:0.5 #111113, stop:1 #0f0f10); border-radius: 12px; }
        QFrame#modernSidebar { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(17, 17, 19, 0.95), stop:1 rgba(26, 26, 29, 0.8)); border-top-left-radius: 12px; border-bottom-left-radius: 12px; border-right: 1px solid rgba(255, 255, 255, 0.1); }
        QLabel#appTitle { font-size: 32px; font-weight: bold; color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00d4ff, stop:1 #7c3aed); }
        QLabel#appSubtitle { font-size: 12px; color: #a1a1aa; text-transform: uppercase; letter-spacing: 1px; }
        QPushButton#modernNavButton { background: transparent; border: 1px solid transparent; border-radius: 12px; padding: 12px 0; }
        QPushButton#modernNavButton:hover { background: rgba(255, 255, 255, 0.05); }
        QPushButton#modernNavButton:checked { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 212, 255, 0.15), stop:1 rgba(124, 58, 237, 0.15)); border: 1px solid rgba(0, 212, 255, 0.4); }
        QPushButton#modernNavButton[collapsed="false"] { text-align: left; }
        QPushButton#modernNavButton[collapsed="true"] { text-align: center; }
        QLabel#navIcon { font-size: 18px; }
        QLabel#navTitle { font-size: 14px; font-weight: 600; color: #ffffff; }
        QLabel#navDescription { font-size: 11px; color: #71717a; }
        QFrame#statusContainer { background: rgba(0, 0, 0, 0.2); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.1); }
        QLabel#connectionStatus, QLabel#dataStatus { font-size: 12px; font-weight: bold;}
        QFrame#contentArea { background: transparent; }
        QFrame#titleBar { background: rgba(26, 26, 29, 0.6); border-bottom: 1px solid rgba(255, 255, 255, 0.1); }
        QLabel#pageTitle { font-size: 24px; font-weight: 600; color: #ffffff; }
        QLabel#timeLabel { font-size: 18px; font-weight: 600; color: #00d4ff; }
        QPushButton#minimizeBtn { background-color: #ffbd2e; border: none; border-radius: 8px; }
        QPushButton#maximizeBtn { background-color: #28ca42; border: none; border-radius: 8px; }
        QPushButton#closeBtn { background-color: #ff5f57; border: none; border-radius: 8px; }
        QFrame#modernSensorCard { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.06), stop:1 rgba(255, 255, 255, 0.02)); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 16px; }
        QFrame#iconContainer { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(0, 212, 255, 0.2), stop:1 rgba(124, 58, 237, 0.2)); border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.1); }
        QLabel#modernIcon { font-size: 20px; color: #ffffff; }
        QLabel#modernTitle { font-size: 16px; font-weight: 600; color: #ffffff; }
        QLabel#modernStatus { font-size: 12px; color: #a1a1aa; }
        QLabel#modernValue { font-size: 18px; font-weight: 700; color: #e5e7eb; }
        QGroupBox { font-weight: bold; border: 1px solid rgba(255, 255, 255, 0.1); background-color: rgba(255, 255, 255, 0.04); border-radius: 12px; margin-top: 12px; padding: 12px; }
        QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 2px 12px; left: 10px; color: #E0E0E0; background-color: rgba(255, 255, 255, 0.08); border-radius: 6px; }
        QGroupBox#modeControlFrame { border: 1px solid rgba(124, 58, 237, 0.7); background-color: rgba(124, 58, 237, 0.08); }
        QGroupBox#modeControlFrame::title { color: #c4b5fd; font-size: 14px; background-color: rgba(124, 58, 237, 0.2); }
        QGroupBox QPushButton { font-weight: bold; color: #ffffff; background-color: rgba(0, 212, 255, 0.15); border: 1px solid rgba(0, 212, 255, 0.3); border-radius: 5px; padding: 8px; }
        QGroupBox QPushButton:hover { background-color: rgba(0, 212, 255, 0.3); border-color: rgba(0, 212, 255, 0.6); }
        QGroupBox QPushButton:pressed { background-color: rgba(0, 212, 255, 0.1); }
        QPushButton#emergencyButton { background-color: #C62828; font-weight: bold; color: white;}
        QPushButton#startButton { background-color: #2E7D32; color: white; }
        QPushButton#startButton:hover { background-color: #388E3C; }
        QPushButton#startButton:disabled { background-color: #555; border-color: #666; color: #999; }
        QPushButton#emergencyButton:hover { background-color: #D32F2F; }
        QPushButton#emergencyButton[emergencyActive="true"] { background-color: #D32F2F; border: 2px solid yellow; }
        QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox { background-color: #2D323B; color: #F0F0F0; padding: 8px; border: 1px solid #4A505A; border-radius: 5px; }
        QComboBox:hover, QLineEdit:hover, QDoubleSpinBox:hover, QSpinBox:hover { border: 1px solid #00d4ff; }
        QComboBox:focus, QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus { border: 1px solid #7c3aed; background-color: #313640; }
        QComboBox:disabled, QLineEdit:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled, QSlider:disabled { background-color: #444; color: #888; border: 1px solid #555; }
        QDoubleSpinBox::up-button, QSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 18px; border-left: 1px solid #4A505A; }
        QDoubleSpinBox::down-button, QSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 18px; border-left: 1px solid #4A505A; }
        QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover { background-color: rgba(0, 212, 255, 0.2); }
        QComboBox::drop-down { border: 0px; }
        QSlider::groove:horizontal { height: 6px; background: rgba(0,0,0,0.2); border-radius: 3px; }
        QSlider::handle:horizontal { background: #E0E0E0; width: 14px; margin: -4px 0; border-radius: 7px; }
        QSlider::handle:horizontal:disabled { background: #777; }
        QTextEdit { background-color: #111113; border: 1px solid rgba(255, 255, 255, 0.1); color: #C5C5C5; border-radius: 8px; font-family: 'Monospace'; }
        QSplitter::handle { background-color: rgba(255, 255, 255, 0.1); }
        QSplitter::handle:horizontal { width: 3px; }
        QFrame#mapFrame { border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; }
        QPushButton#zoomButton { font-weight: bold; font-size: 16px; color: white; background-color: rgba(0, 0, 0, 0.4); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 15px; }
        QPushButton#zoomButton:hover { background-color: rgba(0, 0, 0, 0.6); }
        QPushButton#zoomButton:pressed { background-color: rgba(0, 212, 255, 0.2); }
        """

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    pixmap = QPixmap(600, 350)
    pixmap.fill(QColor("#0f0f10"))
    painter = QPainter(pixmap)
    font = QFont("Segoe UI", 80, QFont.Bold)
    painter.setFont(font)
    gradient = QLinearGradient(0, 0, pixmap.width(), pixmap.height())
    gradient.setColorAt(0.0, QColor(0, 212, 255))
    gradient.setColorAt(1.0, QColor(124, 58, 237))
    painter.setPen(QPen(gradient, 0))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "TUNA")
    font.setPointSize(14)
    font.setBold(False)
    painter.setFont(font)
    painter.setPen(QColor("#a1a1aa"))
    painter.drawText(pixmap.rect().adjusted(0,0,0,-40), Qt.AlignHCenter | Qt.AlignBottom, "Yer Kontrol İstasyonu Yükleniyor...")
    painter.end()

    splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
    splash.show()

    app.processEvents()
    gui = TunaModernGCS()
    
    QTimer.singleShot(1500, lambda: (splash.close(), gui.show()))
    
    sys.exit(app.exec_())