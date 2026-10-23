"""按实际渲染宽度重压图片：内联预览用小图，data-full 放大图保留原尺寸。

用法: python3 tools/optimize_images.py --widths widths.json --quality 62
"""
import argparse, io, json, os, re, subprocess

ap = argparse.ArgumentParser()
ap.add_argument("--html", default="index.html")
ap.add_argument("--srcdir", default="images")
ap.add_argument("--outdir", default="images/small")
ap.add_argument("--fulldir", default="images/full")
ap.add_argument("--widths", default="/tmp/widths.json")
ap.add_argument("--quality", type=int, default=62)
a = ap.parse_args()

html = io.open(a.html, encoding="utf-8").read()
widths = {r[0]: r[4] for r in json.load(open(a.widths))}
full_refs = set(re.findall(r'data-full="images/([^"]+)"', html))
print("data-full 引用:", sorted(full_refs))
os.makedirs(a.outdir, exist_ok=True); os.makedirs(a.fulldir, exist_ok=True)

def dim(p):
    out = subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
                          "-show_entries","stream=width,height","-of","csv=p=0",p],
                         capture_output=True, text=True).stdout.strip()
    w, h = out.split(",")[:2]
    return int(w), int(h)

tot_in = tot_out = 0
report = []
for name in sorted(os.listdir(a.srcdir)):
    if not name.endswith(".webp"): continue
    src = os.path.join(a.srcdir, name)
    W, H = dim(src); sz = os.path.getsize(src); tot_in += sz

    if name in full_refs:                      # 放大用的原图：留在 full/
        dest = os.path.join(a.fulldir, name)
        if os.path.abspath(dest) != os.path.abspath(src):
            os.replace(src, dest)
        tot_out += sz
        report.append((name, W, W, sz, sz, "full"))
        continue

    target = widths.get(name, 0) or W
    target = min(target, W)
    dest = os.path.join(a.outdir, name)
    subprocess.run(["cwebp","-q",str(a.quality),"-m","6","-metadata","none","-af",
                    "-resize",str(target),"0",src,"-o",dest], check=True, capture_output=True)
    out = os.path.getsize(dest); tot_out += out
    report.append((name, W, target, sz, out, "small"))
    os.unlink(src)

for name, W, target, i, o, kind in report:
    html = html.replace('src="%s/%s"' % (a.srcdir, name), 'src="%s/%s"' % (a.outdir, name))
for name in full_refs:
    html = html.replace('data-full="%s/%s"' % (a.srcdir, name), 'data-full="%s/%s"' % (a.fulldir, name))
io.open(a.html, "w", encoding="utf-8").write(html)

print("原 %d 张 %.2f MB -> %.2f MB (%.0f%%)" % (len(report), tot_in/1048576, tot_out/1048576, 100.0*tot_out/tot_in))
top = sorted([r for r in report if r[5]=="small"], key=lambda r: -r[4])[:5]
for n, W, t, i, o, k in top:
    print("  %-12s %4dpx -> %-4dpx  %5dKB -> %4dKB" % (n, W, t, i//1024, o//1024))
print("html bytes:", len(html.encode()))
