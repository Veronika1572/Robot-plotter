import cv2
import numpy as np

# ---------- НАСТРОЙКИ ----------
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT    = os.path.join(BASE_DIR, "input.png")
OUTPUT   = os.path.join(BASE_DIR, "output.gcode")

PLOT_W  = 200.0      # мм, рабочая область
PLOT_H  = 200.0
MARGIN  = 10.0

FEED    = 800        # мм/мин — скорость рисования (аэрограф медленнее)
TRAVEL  = 5000       # мм/мин — холостой ход (воздух выключен)

# --- Управление воздухом (MOSFET → ESP D5 = spindle/enable пин) ---
AIR_ON       = "M3 S1000"   # полная подача (S — ШИМ если поддерживается)
AIR_ON_SOFT  = "M3 S400"    # 40% для мягкого старта
AIR_OFF      = "M5"

USE_SOFT_START = True       # раскачка давления вместо резкого старта
SOFT_START_T   = 0.10       # сек, длительность мягкого старта
AIR_BUILDUP    = 0.15       # сек, задержка после M3 — давление доходит до сопла
AIR_DECAY      = 0.08       # сек, после M5 — остаток аэрозоля/капли

# --- Параметры траектории ---
THRESHOLD = 128       # порог бинаризации
EPSILON   = 1.0       # упрощение контуров (пиксели, больше = грубее)
MIN_AREA  = 30        # мелкие контуры отбрасываем (у аэрографа пятно ~неск. мм)
# ------------------------------------------------------------------


def load_and_scale(path):
    try:
        buf = np.fromfile(path, dtype=np.uint8)
    except OSError as e:
        raise FileNotFoundError(path) from e
    if buf.size == 0:
        raise FileNotFoundError(path)
    img = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(
            f"OpenCV не смог декодировать файл: {path}\n"
            f"Проверьте, что это действительно PNG/JPG и файл не повреждён."
        )
    h, w = img.shape
    scale = min((PLOT_W - 2 * MARGIN) / w,
                (PLOT_H - 2 * MARGIN) / h)
    img = cv2.resize(img, (int(w * scale), int(h * scale)),
                     interpolation=cv2.INTER_AREA)
    return img, scale


def extract_paths(img):
    _, bw = cv2.threshold(img, THRESHOLD, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(bw, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    paths = []
    for c in contours:
        if cv2.contourArea(c) < MIN_AREA:
            continue
        approx = cv2.approxPolyDP(c, EPSILON, True)
        pts = approx.reshape(-1, 2).astype(float)
        if len(pts) >= 2:
            paths.append(pts)
    return paths


def sort_paths(paths):
    """Ближайший сосед — минимизируем холостой ход (важнее для аэрографа:
       каждый лишний проход = лишний расход краски и риск капель)."""
    if not paths:
        return paths
    remaining = list(paths)
    ordered = [remaining.pop(0)]
    while remaining:
        last = ordered[-1][-1]
        idx = min(range(len(remaining)),
                  key=lambda i: np.linalg.norm(remaining[i][0] - last))
        ordered.append(remaining.pop(idx))
    return ordered


def emit_air_on(out):
    if USE_SOFT_START:
        out.append(AIR_ON_SOFT)
        out.append(f"G4 P{SOFT_START_T}")
        out.append(AIR_ON)
    else:
        out.append(AIR_ON)
    out.append(f"G4 P{AIR_BUILDUP}")


def emit_air_off(out):
    out.append(AIR_OFF)
    out.append(f"G4 P{AIR_DECAY}")


def path_to_gcode(pts, scale, out):
    def to_mm(p):
        return p[0] * scale, PLOT_H - p[1] * scale   # Y инвертируем

    # 1. Холостой ход к началу контура (воздух выключен)
    x, y = to_mm(pts[0])
    out.append(f"G0 X{x:.2f} Y{y:.2f} F{TRAVEL}")

    # 2. Включаем воздух, ждём давление
    emit_air_on(out)

    # 3. Рисуем — непрерывное движение, чтобы краска не копилась в точку
    out.append(f"G1 F{FEED}")
    for p in pts[1:]:
        x, y = to_mm(p)
        out.append(f"G1 X{x:.2f} Y{y:.2f}")

    # 4. Выключаем воздух, ждём осаждения аэрозоля
    emit_air_off(out)


def main():
    img, scale = load_and_scale(INPUT)
    paths = sort_paths(extract_paths(img))

    gcode = [
        "G21 ; мм",
        "G90 ; абсолютные координаты",
        AIR_OFF,                 # гарантированно с закрытым клапаном
        f"G4 P0.2",
    ]
    for pts in paths:
        path_to_gcode(pts, scale, gcode)
    gcode += [AIR_OFF, "G0 X0 Y0 ; домой"]

    with open(OUTPUT, "w") as f:
        f.write("\n".join(gcode))
    print(f"Готово: {len(paths)} контуров → {OUTPUT}")


if __name__ == "__main__":
    main()