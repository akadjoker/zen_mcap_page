# ADP dashboard: turns the odometry of the ego vehicle into topics (/plugin/adp/ego_path as
# foxglove.PosesInFrame, /plugin/adp/speed), draws a speed gauge as a panel type, writes a CSV
# report from the menu and answers the MCP tool adp_summary.
import math
from zenmcap import register_converter, register_panel, register_tool, menu, command, on_open
from zenmcap import series, at, time, file, log, export_csv, options

ODOMETRY = "/adp/odometry"
SCHEMA = "Adp.OdometryState"
WINDOW = 10     # samples between two points of the speed (0.1 s at 100 Hz)
PATH_EVERY = 10 # one pose of the path in ten samples
PATH_LENGTH = 60

history = []    # (t, x, y) of the last WINDOW + 1 samples
path = []       # poses of the path so far, newest last
count = 0

def reset():
    global history, path, count
    history = []
    path = []
    count = 0

def pose(x, y, yaw):
    return {"position": {"x": x, "y": y, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": math.sin(yaw / 2), "w": math.cos(yaw / 2)}}

def convert(msg, t, publish):
    global count
    x = msg["x_position"]
    y = msg["y_position"]
    yaw = msg["yaw_angle"]
    history.append([t, x, y])
    if len(history) > WINDOW + 1:
        history.pop(0)
    first = history[0]
    if t > first[0]:
        speed = math.sqrt((x - first[1]) ** 2 + (y - first[2]) ** 2) / (t - first[0])
        publish("/plugin/adp/speed", {"speed": speed, "x": x, "y": y}, "adp.Speed")
    if count % PATH_EVERY == 0:
        path.append(pose(x, y, yaw))
        if len(path) > PATH_LENGTH:
            path.pop(0)
        publish("/plugin/adp/ego_path",
                {"timestamp": {"seconds": int(t), "nanos": int((t - int(t)) * 1e9)},
                 "frame_id": "world", "poses": path},
                "foxglove.PosesInFrame")
    count += 1

# ---- the gauge panel --------------------------------------------------------------------------

def gauge(c, x, y, w, h, v, vmax):
    cx = x + w / 2
    cy = y + h * 0.55
    r = min(w, h) * 0.38
    start = math.pi * 0.75
    sweep = math.pi * 1.5
    frac = min(v / vmax, 1.0)
    segments = 54
    for i in range(segments):
        a0 = start + sweep * i / segments
        a1 = start + sweep * (i + 1) / segments
        colour = "#3a3f47"
        if (i + 0.5) / segments <= frac:
            colour = "#4ec9b0"
            if (i + 0.5) / segments > 0.8:
                colour = "#e5a04b"
        c.line(cx + r * math.cos(a0), cy + r * math.sin(a0),
               cx + r * math.cos(a1), cy + r * math.sin(a1), colour, 9)
    ticks = int(vmax / 5)
    for k in range(ticks + 1):
        a = start + sweep * k / ticks
        c.line(cx + (r - 14) * math.cos(a), cy + (r - 14) * math.sin(a),
               cx + (r - 24) * math.cos(a), cy + (r - 24) * math.sin(a), "#9aa3ad", 2)
        label = str(k * 5)
        c.text(cx + (r - 40) * math.cos(a) - 5 * len(label), cy + (r - 40) * math.sin(a) - 7,
               label, "#9aa3ad", 13)
    a = start + sweep * frac
    c.line(cx, cy, cx + (r - 28) * math.cos(a), cy + (r - 28) * math.sin(a), "#f2f2f2", 3)
    c.circle(cx, cy, 6, "#f2f2f2", True)
    c.text(cx - 52, cy + r * 0.55, "%.1f m/s" % v, "#f2f2f2", 26)

def draw(c, w, h):
    o = options()
    c.text(12, 10, o["title"], "#c8ccd2", 15)
    sample = at("/plugin/adp/speed")
    speed = 0.0
    side = min(w, h * 1.3) + 12
    if sample is None:
        c.text(side, 84, "waiting for /plugin/adp/speed (needs " + ODOMETRY + ")", "#e5a04b", 14)
    else:
        speed = sample["speed"]
        c.text(side, 84, "x = %.1f m" % sample["x"], "#9aa3ad", 14)
        c.text(side, 108, "y = %.1f m" % sample["y"], "#9aa3ad", 14)
    gauge(c, 0, 20, min(w, h * 1.3), h - 20, speed, o["max_speed"])
    c.text(side, 60, "t = %.2f s" % time(), "#9aa3ad", 14)

# ---- summary: the MCP tool and the report -------------------------------------------------------

def summarize(topic):
    times, xs = series(topic + ".x_position")
    t2, ys = series(topic + ".y_position")
    n = xs.len()
    result = {"topic": topic, "samples": n, "distance_m": 0.0, "max_speed_mps": 0.0,
              "stops": 0, "duration_s": 0.0}
    if n < 2:
        return result
    distance = 0.0
    for i in range(1, n):
        distance += math.sqrt((xs[i] - xs[i - 1]) ** 2 + (ys[i] - ys[i - 1]) ** 2)
    top = 0.0
    stops = 0
    moving = False
    for i in range(WINDOW, n):
        dt = times[i] - times[i - WINDOW]
        if dt <= 0:
            continue
        v = math.sqrt((xs[i] - xs[i - WINDOW]) ** 2 + (ys[i] - ys[i - WINDOW]) ** 2) / dt
        if v > top:
            top = v
        if v > 1.0:
            moving = True
        elif v < 0.2 and moving:
            stops += 1
            moving = False
    result["distance_m"] = round(distance, 2)
    result["max_speed_mps"] = round(top, 2)
    result["stops"] = stops
    result["duration_s"] = round(times[n - 1] - times[0], 2)
    return result

def adp_summary(args):
    topic = ODOMETRY
    if "topic" in args:
        topic = args["topic"]
    return summarize(topic)

def report():
    target = file()
    if target.endswith(".mcap"):
        target = target[0:len(target) - 5]
    target = target + "_adp_report.csv"
    rows = export_csv(target, [ODOMETRY + ".x_position", ODOMETRY + ".y_position",
                               "/plugin/adp/speed.speed"])
    log("ADP report: " + str(rows) + " rows in " + target)

def opened():
    reset()

def on_load():
    reset()
    register_converter(SCHEMA, convert)
    register_panel("dashboard", "ADP dashboard", draw, {"max_speed": 20, "title": "Ego speed"})
    register_tool("adp_summary",
                  "Distance driven, top speed and number of stops of the ego vehicle from the Adp odometry.",
                  '{"type":"object","properties":{"topic":{"type":"string","description":"Odometry topic, default /adp/odometry."}}}',
                  adp_summary)
    menu("Plugins/ADP/Report", report)
    command("ADP report", "Ctrl+Shift+R", report)
    on_open(opened)
