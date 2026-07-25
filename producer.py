import json
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import redis

r = redis.Redis(host="localhost", port=6379, db=0)
QUEUE = "tasks"


def parse_num(s):
    try:
        return int(s)
    except ValueError:
        return float(s)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        func_name = qs.get("func", ["add"])[0]
        try:
            args = [parse_num(qs["a"][0]), parse_num(qs["b"][0])]
        except (KeyError, ValueError):
            args = [1, 2]

        # 任务指令包：用“函数名 + 参数 + 任务ID”代表一个任务
        packet = {
            "task_id": uuid.uuid4().hex,
            "func_name": func_name,
            "args": args,
        }
        r.lpush(QUEUE, json.dumps(packet, ensure_ascii=False))
        body = f"Pushed task: {json.dumps(packet, ensure_ascii=False)}\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print("Producer running at http://localhost:8000  (?a=5&b=8&func=add)", flush=True)
    HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
