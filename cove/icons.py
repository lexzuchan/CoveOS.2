from math import cos, pi, sin

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap


def apps(painter):
    for y in (15, 26):
        for x in (15, 26):
            painter.drawRoundedRect(QRectF(x, y, 7, 7), 1.5, 1.5)


def files(painter):
    outline = QPainterPath(QPointF(12, 31))
    outline.lineTo(12, 17)
    outline.quadTo(12, 15, 14, 15)
    outline.lineTo(21, 15)
    outline.lineTo(24, 18)
    outline.lineTo(34, 18)
    outline.quadTo(36, 18, 36, 20)
    outline.lineTo(36, 31)
    outline.quadTo(36, 33, 34, 33)
    outline.lineTo(14, 33)
    outline.quadTo(12, 33, 12, 31)
    outline.closeSubpath()
    painter.drawPath(outline)


def browser(painter):
    painter.drawEllipse(QRectF(12, 12, 24, 24))
    needle = QPainterPath(QPointF(29.5, 18.5))
    needle.lineTo(26, 26)
    needle.lineTo(18.5, 29.5)
    needle.lineTo(22, 22)
    needle.closeSubpath()
    painter.drawPath(needle)


def windows(painter):
    rear = QPainterPath(QPointF(18, 17))
    rear.lineTo(18, 15)
    rear.quadTo(18, 13, 20, 13)
    rear.lineTo(34, 13)
    rear.quadTo(36, 13, 36, 15)
    rear.lineTo(36, 25)
    rear.quadTo(36, 27, 34, 27)
    rear.lineTo(32, 27)
    painter.drawPath(rear)
    painter.drawRoundedRect(QRectF(12, 19, 20, 15), 2, 2)
    painter.drawLine(QPointF(12, 23), QPointF(32, 23))


def appearance(painter):
    gear = QPainterPath()
    for index in range(32):
        angle = index * pi / 16
        radius = 11.5 if index % 4 in (1, 2) else 9.25
        point = QPointF(24 + radius * cos(angle), 24 + radius * sin(angle))
        if index == 0:
            gear.moveTo(point)
        else:
            gear.lineTo(point)
    gear.closeSubpath()
    painter.drawPath(gear)
    painter.drawEllipse(QRectF(20, 20, 8, 8))


ARTWORK = {
    "Apps": apps,
    "Files": files,
    "Browser": browser,
    "Windows": windows,
    "Appearance": appearance,
}


def dock_icon(name, size, scale):
    pixels = round(size * scale)
    pixmap = QPixmap(pixels, pixels)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 48, size / 48)

    glass = QLinearGradient(0, 0, 0, 48)
    glass.setColorAt(0, QColor(55, 85, 144, 174))
    glass.setColorAt(1, QColor(18, 35, 73, 204))
    painter.setBrush(glass)
    painter.setPen(QPen(QColor(171, 199, 248, 107), 0.85))
    painter.drawRoundedRect(QRectF(1, 1, 46, 46), 11, 11)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor("#ffffff"), 1.55, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    ARTWORK[name](painter)
    painter.end()
    return QIcon(pixmap)
