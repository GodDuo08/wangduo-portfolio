"""把单文件版 HTML 内联的 base64 图片抽成独立文件并重压缩。

用法：python3 tools/extract_images.py [--quality 72] [--max-width 1400]
输入：index.html（含 data:image/webp;base64,...）
输出：images/*.webp，并把 src/data-full 改写为相对路径
"""
import argparse, base64, io, os, re, subprocess, sys, tempfile

ap = argparse.ArgumentParser()
ap.add_argument("--quality", type=int, default=72)
ap.add_argument("--max-width", type=int, default=1400)
ap.add_argument("--html", default="index.html")
ap.add_argument("--outdir", default="images")
args = ap.parse_args()

html = io.open(args.html, encoding="utf-8").read()
uris = re.findall(r"data:image/webp;base64,([A-Za-z0-9+/=]+)", html)
if not uris:
    print("没有内联图片，跳过"); sys.exit(0)
unique = list(dict.fromkeys(uris))
os.makedirs(args.outdir, exist_ok=True)

mapping, total_in, total_out = {}, 0, 0
for i, b64 in enumerate(unique, 1):
    raw = base64.b64decode(b64)
    total_in += len(raw)
    with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tf:
        tf.write(raw); tmp = tf.name
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width", "-of", "csv=p=0", tmp],
                           capture_output=True, text=True)
    w = int((probe.stdout or "0").strip() or 0)
    name = "img-%02d.webp" % i
    dest = os.path.join(args.outdir, name)
    cmd = ["cwebp", "-q", str(args.quality), "-m", "6", "-metadata", "none", "-af", tmp, "-o", dest]
    if w > args.max_width:
        cmd[1:1] = ["-resize", str(args.max_width), "0"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("cwebp failed:", name, r.stderr[-200:]); sys.exit(1)
    total_out += os.path.getsize(dest)
    mapping[b64] = "%s/%s" % (args.outdir.rstrip("/"), name)
    os.unlink(tmp)

for b64, path in mapping.items():
    html = html.replace("data:image/webp;base64," + b64, path)

io.open(args.html, "w", encoding="utf-8").write(html)
print("images: %d unique (%d refs) | %d bytes -> %d bytes (%.1f%%)"
      % (len(unique), len(uris), total_in, total_out, 100.0 * total_out / total_in))
print("html bytes: %d" % len(html.encode()))
