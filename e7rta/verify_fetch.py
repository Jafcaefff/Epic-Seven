"""用本地假 CDN 验证 fetch_images 的下载→PNG校验→写盘→重跑跳过 整条链路。"""
import os, json, threading, time, http.server, socketserver
import fetch_images as F

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "img", "heroes")

# 造一个最小合法 PNG（1x1 红色），CRC 用 zlib 现算，保证格式正确
import struct, zlib
PNG = None
def _chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
_ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)          # 1x1, 8bit, truecolor
_raw  = b"\x00" + b"\xff\x00\x00"                              # scanline filter=0 + RGB 红
_idat = zlib.compress(_raw)
PNG = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", _ihdr)
       + _chunk(b"IDAT", _idat) + _chunk(b"IEND", b""))
assert PNG[:8] == F.PNG_MAGIC, "PNG magic 不对"

PORT = 8791
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # /face/cXXXX_s.png -> 真 PNG；故意让一个 code 返回 HTML 伪装 404
        if "c9999" in self.path:
            body = b"<html><body>404 Not Found</body></html>"
            self.send_response(404)
            self.send_header("Content-Type", "text/html")
        else:
            body = PNG
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

srv = socketserver.ThreadingTCPServer(("127.0.0.1", PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
time.sleep(0.4)

F.IMG_BASE = f"http://127.0.0.1:{PORT}/face/"
F.OUT = OUT
os.makedirs(OUT, exist_ok=True)
F.fetch_one.suffix = "_s"

# 清理待测文件
for c in ("c7777", "c7778", "c9999"):
    p = os.path.join(OUT, c + ".png")
    if os.path.exists(p):
        os.remove(p)

print("=== 1) 正常下载 ===")
print(F.fetch_one(("c7777", "测试英雄A")))
p = os.path.join(OUT, "c7777.png")
assert os.path.isfile(p), "文件未生成"
assert open(p, "rb").read() == PNG, "内容不一致"
print("  PASS: 下载并写入成功，大小", os.path.getsize(p))

print("\n=== 2) 重跑应 skip（断点续传）===")
r = F.fetch_one(("c7777", "测试英雄A"))
print(r)
assert r[2] == "skip", f"期望 skip，实际 {r[2]}"
print("  PASS: 已存在的正确图片被跳过")

print("\n=== 3) 伪造内容(HTML冒充404)必须判为 fail，不能写盘 ===")
p2 = os.path.join(OUT, "c9999.png")
# 让 URL 返回 HTML 但 HTTP 404 -> break
r = F.fetch_one(("c9999", "假英雄"))
print(r)
assert r[2] == "fail", f"期望 fail，实际 {r[2]}"
assert not os.path.exists(p2), "不该生成文件却生成了"
print("  PASS: 伪造/缺失图片被正确拒绝且不落盘")

srv.shutdown()
print("\n链路验证全部通过：下载 → PNG magic 校验 → 写盘 → 重跑跳过 → 脏数据拒绝")
