import asyncio
import json
import os

STATUS = {200: "OK", 204: "No Content", 400: "Bad Request", 404: "Not Found",
          405: "Method Not Allowed", 409: "Conflict", 503: "Service Unavailable"}
MIME = {"html": "text/html; charset=utf-8", "js": "text/javascript", "css": "text/css",
        "svg": "image/svg+xml", "json": "application/json", "ico": "image/x-icon",
        "png": "image/png", "jpg": "image/jpeg"}


class Request:
    def __init__(self, method, path, query, headers, body):
        self.method = method
        self.path = path
        self.query = query
        self.headers = headers
        self.body = body

    def json(self):
        try:
            return json.loads(self.body) if self.body else {}
        except ValueError:
            raise HttpError(400, "JSON inválido")


class HttpError(Exception):
    def __init__(self, status, message=""):
        super().__init__(message)
        self.status = status
        self.message = message


class Response:
    def __init__(self, body=b"", status=200, content_type="text/plain", headers=None):
        self.body = body.encode() if isinstance(body, str) else body
        self.status = status
        self.content_type = content_type
        self.headers = headers or {}

    def head(self, length=None):
        lines = ["HTTP/1.1 %d %s" % (self.status, STATUS.get(self.status, "")),
                 "Content-Type: " + self.content_type, "Connection: close"]
        if length is not None:
            lines.append("Content-Length: %d" % length)
        lines.extend("%s: %s" % item for item in self.headers.items())
        return ("\r\n".join(lines) + "\r\n\r\n").encode()

    async def send(self, writer):
        writer.write(self.head(len(self.body)))
        if self.body:
            writer.write(self.body)
        await writer.drain()


class Json(Response):
    def __init__(self, data, status=200):
        super().__init__(json.dumps(data), status, MIME["json"], {"Cache-Control": "no-store"})


class File(Response):
    def __init__(self, path):
        super().__init__(content_type=MIME.get(path.rsplit(".", 1)[-1], "application/octet-stream"),
                         headers={"Cache-Control": "max-age=300"})
        self.path = path

    async def send(self, writer):
        size = os.stat(self.path)[6]
        writer.write(self.head(size))
        chunk = bytearray(2048)
        with open(self.path, "rb") as f:
            while n := f.readinto(chunk):
                writer.write(memoryview(chunk)[:n])
                await writer.drain()


class Server:
    def __init__(self, static_root="/www"):
        self._routes = {}
        self._static = static_root

    def route(self, method, path):
        def register(handler):
            self._routes[(method, path)] = handler
            return handler
        return register

    def get(self, path):
        return self.route("GET", path)

    def post(self, path):
        return self.route("POST", path)

    async def start(self, port):
        return await asyncio.start_server(self._serve, "0.0.0.0", port, backlog=8)

    async def _serve(self, reader, writer):
        try:
            request = await self._read(reader)
            if request is not None:
                response = await self._dispatch(request)
                await response.send(writer)
        except Exception:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except OSError:
                pass

    async def _read(self, reader):
        line = await asyncio.wait_for_ms(reader.readline(), 5000)
        parts = line.decode().split()
        if len(parts) < 2:
            return None
        method, target = parts[0], parts[1]
        headers = {}
        while True:
            raw = await asyncio.wait_for_ms(reader.readline(), 5000)
            if raw in (b"\r\n", b"\n", b""):
                break
            name, _, value = raw.decode().partition(":")
            headers[name.strip().lower()] = value.strip()
        length = min(int(headers.get("content-length", 0)), 16_384)
        body = await reader.readexactly(length) if length else b""
        path, _, query = target.partition("?")
        params = dict(pair.split("=", 1) for pair in query.split("&") if "=" in pair)
        return Request(method, path, params, headers, body)

    async def _dispatch(self, request):
        handler = self._routes.get((request.method, request.path))
        try:
            if handler is not None:
                result = await handler(request)
                if result is None:
                    return Response(status=204)
                return result if isinstance(result, Response) else Json(result)
            if request.method == "GET":
                return self._file(request.path)
            raise HttpError(405 if any(p == request.path for _, p in self._routes) else 404)
        except HttpError as e:
            return Json({"error": e.message or STATUS.get(e.status, "")}, e.status)
        except Exception as e:
            return Json({"error": repr(e)}, 400)

    def _file(self, path):
        if path.endswith("/"):
            path += "index.html"
        if ".." in path:
            raise HttpError(404)
        full = self._static + path
        try:
            os.stat(full)
        except OSError:
            raise HttpError(404)
        return File(full)
