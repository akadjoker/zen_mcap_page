# Marks: Ctrl+M (or the tool bar button) puts a mark on the time line at the play position, with a
# note made from the topic selected in Topics and its message at that time. The marks of a file are
# kept in the plugin settings and come back when the file is opened again. The menu entry
# Plugins/Marks/Export CSV writes them next to the file.
import io
from zenmcap import command, toolbar, menu, on_open, settings, mark, time, at, file, log
from zenmcap import selected_topic, download

marks = []

def brief(msg):
    parts = []
    for k in msg:
        v = msg[k]
        if isinstance(v, float):
            v = round(v, 2)
        text = str(v)
        if len(text) <= 24 and len(parts) < 3:
            parts.append(k + "=" + text)
    return " ".join(parts)

def add_mark():
    t = time()
    topic = selected_topic()
    note = "mark"
    if topic != "":
        note = topic
        msg = at(topic)
        if msg is not None:
            note = topic + " " + brief(msg)
    mark(t, note, "info")
    marks.append([t, note])
    s = settings()
    s["marks"][file()] = marks
    log("mark at %.2f s: %s" % (t, note))

def quote(text):
    return '"' + text.replace('"', '""') + '"'

def export_csv_file():
    target = file()
    if target.endswith(".mcap"):
        target = target[0:len(target) - 5]
    target = target + "_marks.csv"
    text = "time_s,note\n"
    for m in marks:
        text = text + "%.3f,%s\n" % (m[0], quote(m[1]))
    io.write(target, text)
    download(target)
    log("marks: " + str(len(marks)) + " rows in " + target)

def opened():
    global marks
    marks = []
    s = settings()
    if file() in s["marks"]:
        for m in s["marks"][file()]:
            mark(m[0], m[1], "info")
            marks.append(m)
        s["marks"][file()] = marks

def on_load():
    s = settings()
    if "marks" not in s:
        s["marks"] = {}
    command("Mark the current time", "Ctrl+M", add_mark)
    toolbar("bookmark", "Mark the current time (Ctrl+M)", add_mark)
    menu("Plugins/Marks/Export CSV", export_csv_file)
    on_open(opened)
