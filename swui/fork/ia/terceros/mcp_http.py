# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 Alfred Mickautsch (ghbalf/freecad-ai, mcp/transport.py)
# SPDX-FileCopyrightText: 2026 wally88ar-coder (adaptado para FreeWorks)
# Origen: ghbalf/freecad-ai commit 08d637d, freecad_ai/mcp/transport.py. Cambios nuestros marcados "FreeWorks:".
"""Transports for MCP communication.

HTTPServerTransport — serves MCP over HTTP: Streamable HTTP and HTTP+SSE.

FreeWorks: solo el lado servidor por HTTP (sin los transportes de cliente ni STDIO del
original) y la clave (token) es obligatoria: sin clave no arranca.
"""

import hmac
import json
import logging
import socket  # FreeWorks: puerto exclusivo en Windows
import threading
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Any, Callable

from . import mcp_protocol as protocol  # FreeWorks: nombre del archivo copiado

logger = logging.getLogger(__name__)


def validate_modern_headers(headers, msg):
    """Return a JSON-RPC error when the mirrored headers disagree with the
    body, or None when they agree.

    2026-07-28 mirrors selected body fields into headers so an intermediary
    can route, authorize or rate-limit without parsing the body. That only
    holds if the two always say the same thing: a request whose header names
    one tool and whose body names another is how a policy layer in front of
    this server gets walked past. So a mismatch is a MUST-reject, not a
    preference for one source over the other.

    Reads each mirrored header with ``.get_all()`` where available (guarded,
    since a caller may pass a plain mapping) rather than ``.get()`` alone.
    ``.get()`` on an ``email.message.Message`` silently returns only the
    FIRST occurrence of a repeated header, so a smuggled second copy would
    validate or not purely on which one comes first — and intermediaries
    disagree on that (nginx keeps the first, Envoy joins duplicates with a
    comma, some WAFs keep the last). A duplicate is therefore rejected
    outright rather than resolved by picking one: there is no rule for
    "use the first" that every intermediary in front of us also follows,
    so any such rule would just relocate the bypass.

    Module level, not a method of the nested RequestHandler: that class is
    built inside HTTPServerTransport._make_server() and cannot be reached
    without binding a socket.
    """
    msg_id = msg.get("id")

    def mismatch(text):
        return protocol.make_error(msg_id, protocol.HEADER_MISMATCH, text)

    get_all = getattr(headers, "get_all", None)
    if get_all is not None:
        for name in (protocol.HEADER_PROTOCOL_VERSION, protocol.HEADER_METHOD,
                     protocol.HEADER_NAME):
            if len(get_all(name) or ()) > 1:
                return mismatch("Header %s appears more than once." % name)

    version = protocol.request_protocol_version(msg)
    header_version = headers.get(protocol.HEADER_PROTOCOL_VERSION)
    if header_version is None:
        return mismatch("Missing required MCP-Protocol-Version header.")
    if header_version != version:
        return mismatch(
            "Header mismatch: MCP-Protocol-Version %r does not match the %r "
            "in params._meta." % (header_version, version))

    method = msg.get("method", "")
    header_method = headers.get(protocol.HEADER_METHOD)
    if header_method is None:
        return mismatch("Missing required Mcp-Method header.")
    if header_method != method:
        return mismatch(
            "Header mismatch: Mcp-Method %r does not match the body's method "
            "%r." % (header_method, method))

    if method == "tools/call":
        raw_name = headers.get(protocol.HEADER_NAME)
        if raw_name is None:
            return mismatch("Missing required Mcp-Name header on tools/call.")
        wanted = (msg.get("params") or {}).get("name")
        decoded_name = protocol.decode_header_value(raw_name)
        if decoded_name is None or decoded_name != wanted:
            return mismatch(
                "Header mismatch: Mcp-Name %r does not name the tool the body "
                "calls (%r)." % (raw_name, wanted))

    return None


# 2026-07-28 maps these onto HTTP so an intermediary can act on them without
# parsing the body. Legacy answers 200-with-error for everything, so this map
# is applied only to a modern response.
MODERN_ERROR_STATUS = {
    protocol.METHOD_NOT_FOUND: 404,
    protocol.HEADER_MISMATCH: 400,
    protocol.MISSING_REQUIRED_CLIENT_CAPABILITY: 400,
    protocol.UNSUPPORTED_PROTOCOL_VERSION: 400,
}


def _status_for(response, modern):
    """The HTTP status a JSON-RPC response travels under."""
    if not modern or "error" not in response:
        return 200
    return MODERN_ERROR_STATUS.get(response["error"].get("code"), 200)



_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

# A wildcard bind address is not a name any client's Host header ever
# carries, so it cannot seed the default Host allowlist (see __init__).
_WILDCARD_BIND_HOSTS = frozenset({"0.0.0.0", "::"})

# Cap the Streamable HTTP request body. A negative Content-Length would make
# rfile.read() block to EOF and pin a worker thread until the socket timeout,
# answering nothing; an oversized one would buffer the whole body in memory.
MAX_REQUEST_BODY = 10 * 1024 * 1024


class HTTPServerTransport:
    """Server-side transport: serves MCP over HTTP on one listener.

    Endpoints:
        POST /mcp       — Streamable HTTP; the JSON-RPC reply comes back
                          inline as application/json
        GET  /mcp       — 405; this server offers no server-to-client stream
        GET  /sse       — legacy HTTP+SSE event stream (client subscribes here)
        POST /messages  — legacy HTTP+SSE requests (responses arrive via SSE)

    Both transports run side by side so a client connects with whichever it
    speaks. HTTP+SSE was deprecated in 2026-07-28 with a minimum twelve-month
    removal window (#65); the spec's own guidance for servers is to host both
    during it.

    Designed for a single connected client at a time (typical for a
    desktop-app MCP server like FreeCAD).

    Because ``POST /messages`` executes arbitrary tools (including run_macro),
    every request is gated: the ``Host`` header must be loopback (a
    DNS-rebinding guard) and any cross-origin ``Origin`` is rejected. Native
    MCP clients send no ``Origin``; a malicious web page's ``fetch()`` always
    does, so this blocks browser drive-by tool invocation without breaking the
    documented local client. ``allowed_hosts``/``allowed_origins`` widen the
    policy for advanced (e.g. deliberately LAN-exposed) deployments.

    Neither check is access control: any local process can send a loopback
    ``Host`` and no ``Origin``, so anything already running on the machine can
    call every tool. ``auth_token``, when set, closes that gap by also
    requiring ``Authorization: Bearer <token>`` on every request (#59).
    Unset (the default) leaves the server exactly as before: no token is
    required, matching every currently documented start-up recipe.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 3000,
                 allowed_hosts=None, allowed_origins=(), auth_token=None):
        self._host = host
        self._port = port
        self._handler: Callable[[dict], dict | None] | None = None
        self._sse_wfile: Any = None
        self._sse_lock = threading.Lock()
        self._httpd = None
        self._serving = False
        self._lifecycle_lock = threading.Lock()
        # FreeWorks: la clave es obligatoria (en el original es opcional). Sin ella cualquier
        # programa de la PC podría mandarle código a FreeCAD.
        if not auth_token:
            raise ValueError("El puente IA necesita una clave (auth_token).")
        self._auth_token = auth_token
        if allowed_hosts is None:
            if host.lower() in _WILDCARD_BIND_HOSTS:
                raise OSError(
                    "MCP_HOST=%s binds every interface, but no real client's "
                    "Host header ever names a wildcard address, so every LAN "
                    "client would get a 403. Set MCP_HOST to the concrete "
                    "interface address clients will dial (e.g. your LAN IP), "
                    "or pass allowed_hosts explicitly to opt into a wider "
                    "policy." % host)
            allowed_hosts = _LOOPBACK_HOSTS | {host.lower()}
        self._allowed_hosts = frozenset(h.lower() for h in allowed_hosts)
        self._allowed_origins = frozenset(allowed_origins)

    @staticmethod
    def _hostname_of(host_header) -> str:
        """Extract the bare hostname (no port) from a Host header value."""
        if not host_header:
            return ""
        value = host_header.strip()
        if value.startswith("["):  # IPv6 literal, e.g. [::1]:3000
            return value[1:].split("]", 1)[0].lower()
        return value.split(":", 1)[0].lower()

    def _request_allowed(self, host_header, origin_header,
                          authorization_header=None) -> bool:
        """Authorize a request by Host (DNS-rebinding), Origin (CSRF), and,
        when configured, a bearer token (access control, #59)."""
        return self._classify_request(
            host_header, origin_header, authorization_header) == "ok"

    def _classify_request(self, host_header, origin_header,
                           authorization_header=None) -> str:
        """Like ``_request_allowed``, but distinguishes *why* a request is
        denied so the HTTP handler can answer 403 vs 401.

        "denied": Host/Origin rejected the request (DNS-rebinding/CSRF),
        meaning this caller is not allowed here at all, regardless of
        credentials. "unauthorized": a bearer token is configured and the
        one presented is missing or wrong, meaning the caller may retry
        with a credential. "ok": request may proceed.
        """
        if self._hostname_of(host_header) not in self._allowed_hosts:
            return "denied"
        if origin_header is not None and origin_header not in self._allowed_origins:
            return "denied"
        if self._auth_token is not None and not self._token_matches(authorization_header):
            return "unauthorized"
        return "ok"

    def _token_matches(self, authorization_header) -> bool:
        """Constant-time compare of the presented bearer token.

        ``hmac.compare_digest`` raises ``TypeError`` when either ``str``
        argument contains a non-ASCII character. HTTP headers are decoded
        latin-1 by ``http.client.parse_headers``, so any byte >= 0x80 in
        ``Authorization`` produces exactly that: an unauthenticated caller
        could otherwise crash the handler thread on every request, with no
        response sent at all.
        """
        try:
            return hmac.compare_digest(
                self._bearer_token_of(authorization_header),
                self._auth_token)
        except TypeError:
            return False

    @staticmethod
    def _bearer_token_of(authorization_header) -> str:
        """Extract the token from an ``Authorization: Bearer <token>`` header.

        Returns ``""`` for a missing header or any other scheme, which
        ``hmac.compare_digest`` then compares against the real token in
        constant time: a plain ``==`` would leak the token's length and
        prefix through response timing.
        """
        if not authorization_header:
            return ""
        scheme, _, value = authorization_header.partition(" ")
        if scheme.lower() != "bearer":
            return ""
        return value.strip()

    def bind(self):
        """Create and bind the listening socket. Raises OSError if unavailable.

        Split out of ``run`` so a caller on the GUI thread learns about a bind
        failure (EADDRINUSE, EACCES) synchronously. When the bind happened
        inside the serve thread the traceback went to the console and nothing
        else: FreeCAD carried on as if the server had started.

        Idempotent — binding an already-bound transport is a no-op.
        """
        with self._lifecycle_lock:
            if self._httpd is None:
                self._httpd = self._make_server()

    def serve(self, handler: Callable[[dict], dict | None] | None = None):
        """Serve until stop(). Requires a prior bind()."""
        with self._lifecycle_lock:
            if handler is not None:
                self._handler = handler
            httpd = self._httpd
            if httpd is None:
                raise RuntimeError("bind() must be called before serve()")
            self._serving = True
        logger.info(
            "MCP server listening on http://%s:%d/mcp (legacy HTTP+SSE also "
            "served at http://%s:%d/sse)",
            self._host, self._port, self._host, self._port)
        try:
            httpd.serve_forever()
        finally:
            with self._lifecycle_lock:
                self._serving = False

    def stop(self):
        """Shut down and release the socket. Safe when never bound.

        ``shutdown()`` is only safe once ``serve_forever()`` is running: it
        waits on an event that only serve_forever's exit path sets, so calling
        it on a bound-but-never-served socket blocks forever. Bound but never
        served therefore goes straight to ``server_close()``.

        The two values are captured under the lock and then released before
        any blocking call: holding the lock across ``shutdown()`` would
        deadlock against ``serve()``'s ``finally`` clause, which needs the
        same lock to clear ``_serving``.

        Shutting the listening socket down does not touch an already-attached
        SSE client: its ``process_request_thread`` sits in the keepalive loop
        and keeps writing, so the client never learns the server went away and
        its later POSTs are answered 202 by a transport that drops the reply.
        Closing ``_sse_wfile`` here makes the next keepalive write fail, which
        ends that thread and gives the client a clean EOF. Everything else
        already treats a None ``_sse_wfile`` as "no client attached", which is
        exactly the state left behind. Done outside ``_lifecycle_lock`` for
        the same deadlock reason as above.
        """
        with self._lifecycle_lock:
            httpd, self._httpd = self._httpd, None
            serving = self._serving

        with self._sse_lock:
            wfile, self._sse_wfile = self._sse_wfile, None
        if wfile is not None:
            try:
                wfile.close()
            except Exception:
                pass

        if httpd is None:
            return
        if serving:
            httpd.shutdown()
        httpd.server_close()

    def run(self, handler: Callable[[dict], dict | None]):
        """Start the HTTP server (blocking). Unchanged: bind, then serve."""
        self._handler = handler
        self.bind()
        self.serve()

    def _make_server(self):
        """Build the threaded HTTP server (split out for testability)."""
        transport = self

        class RequestHandler(BaseHTTPRequestHandler):
            # Without a timeout the connection socket blocks forever, and
            # ``_write_locked`` holds ``_sse_lock`` across its write: a client
            # that stops reading would pin that lock and freeze ``stop()`` —
            # which runs on the Qt main thread — hanging all of FreeCAD (#63).
            # ``StreamRequestHandler.setup()`` applies this via settimeout().
            # Generous enough that a merely slow client is not dropped; a
            # timed-out write surfaces as ``socket.timeout``, which is
            # ``TimeoutError`` and so already handled as a dropped client.
            timeout = 30

            def log_message(self, fmt, *args):
                logger.debug(fmt, *args)

            def _base_path(self):
                return self.path.split("?")[0].rstrip("/")

            def _authorized(self):
                status = transport._classify_request(
                    self.headers.get("Host"), self.headers.get("Origin"),
                    self.headers.get("Authorization"))
                if status == "ok":
                    return True
                if status == "unauthorized":
                    # Missing/wrong bearer token: distinct from a Host/Origin
                    # rejection so a client can tell "present a credential"
                    # from "you are not allowed here at all" (#59 review).
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", "Bearer")
                    self.end_headers()
                    return False
                self.send_error(403)
                return False

            def do_GET(self):
                if not self._authorized():
                    return
                path = self._base_path()
                if path == "/sse":
                    self._handle_sse()
                elif path == "/mcp":
                    # The spec allows a server that offers no server-to-client
                    # stream to refuse GET outright, and we originate no
                    # server-initiated messages.
                    self._send_method_not_allowed()
                else:
                    self.send_error(404)

            def do_DELETE(self):
                # _authorized() is invoked per-verb by hand — BaseHTTPRequest-
                # Handler has no dispatch layer to hook — so a new verb that
                # forgets this call silently bypasses the Host/Origin guard.
                if not self._authorized():
                    return
                if self._base_path() == "/mcp":
                    # DELETE terminates a session. We issue none.
                    self._send_method_not_allowed()
                else:
                    self.send_error(404)

            def _send_method_not_allowed(self):
                self.send_response(405)
                self.send_header("Allow", "POST")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_POST(self):
                if not self._authorized():
                    return
                path = self._base_path()
                if path == "/messages":
                    self._handle_messages()
                elif path == "/mcp":
                    self._handle_streamable()
                else:
                    self.send_error(404)

            def _handle_sse(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                session_id = uuid.uuid4().hex
                with transport._sse_lock:
                    transport._sse_wfile = self.wfile

                try:
                    endpoint_data = f"/messages?sessionId={session_id}"
                    endpoint_event = (
                        f"event: endpoint\ndata: {endpoint_data}\n\n".encode()
                    )
                    if not transport._write_locked(endpoint_event):
                        return
                    while transport._write_locked(b": keepalive\n\n"):
                        time.sleep(15)
                finally:
                    with transport._sse_lock:
                        if transport._sse_wfile is self.wfile:
                            transport._sse_wfile = None

            def _handle_messages(self):
                # Same guard as _handle_streamable, for the same reason (#69):
                # this endpoint is unauthenticated (#59), so a malformed
                # header or body must answer with a JSON-RPC error rather
                # than escape as a traceback in the user's FreeCAD console.
                # ValueError covers a non-integer Content-Length and
                # json.JSONDecodeError (a ValueError subclass, so the
                # pre-existing parse-error behaviour is unchanged); a body
                # that isn't valid UTF-8 raises UnicodeDecodeError. The range
                # check matters most: rfile.read(-1) would block to EOF and
                # pin a worker thread until the socket timeout, answering
                # nothing at all.
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    if length < 0 or length > MAX_REQUEST_BODY:
                        raise ValueError(
                            "Content-Length %d out of range" % length)
                    body = self.rfile.read(length).decode("utf-8")
                    msg = json.loads(body)
                except (ValueError, UnicodeDecodeError):
                    err = protocol.make_error(
                        None, protocol.PARSE_ERROR, "Parse error"
                    )
                    self._send_json(400, err)
                    return

                # A modern-shaped message is served modern here too (both
                # endpoints share MCPServer._handle), but without the header
                # validation /mcp applies. Deliberate: mirrored headers exist
                # so an intermediary can route without parsing the body, and
                # this deprecated localhost SSE pair (#65) has none. Not worth
                # extending a transport on a removal clock.
                try:
                    response = transport._handler(msg) if transport._handler else None
                except Exception as e:
                    msg_id = msg.get("id")
                    response = protocol.make_error(
                        msg_id, protocol.INTERNAL_ERROR, str(e)
                    ) if msg_id is not None else None

                self.send_response(202)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"accepted":true}')
                self.wfile.flush()

                if response is not None:
                    transport._send_sse(response)

            def _handle_streamable(self):
                """Serve one Streamable HTTP POST.

                Unlike ``/messages``, the reply travels back in this very
                response — there is no side channel and no client to have
                dropped, so none of the SSE bookkeeping applies.

                The request/notification split is decided by ``id``, not by
                whether the handler produced something: a request that gets no
                response is a server bug, and answering it with a bare 202
                would surface as an unparseable empty body on the client.
                """
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    if length < 0 or length > MAX_REQUEST_BODY:
                        raise ValueError(
                            "Content-Length %d out of range" % length)
                    body = self.rfile.read(length).decode("utf-8")
                    msg = json.loads(body)
                except (ValueError, UnicodeDecodeError):
                    # ValueError covers a non-integer Content-Length and
                    # json.JSONDecodeError (a ValueError subclass); a body
                    # that isn't valid UTF-8 raises UnicodeDecodeError. This
                    # endpoint is unauthenticated (#59), so any of the three
                    # must answer with a JSON-RPC error, never an uncaught
                    # exception reaching http.server's generic handler.
                    self._send_json(400, protocol.make_error(
                        None, protocol.PARSE_ERROR, "Parse error"))
                    return

                if not isinstance(msg, dict):
                    self._send_json(400, protocol.make_error(
                        None, protocol.INVALID_REQUEST,
                        "Expected a single JSON-RPC object. Batched requests "
                        "are not supported."))
                    return

                # Era is decided by the body, so the body must be read first.
                # This is why the version check no longer runs before it —
                # which also retires the old caveat about answering without
                # draining, safe only while protocol_version stayed HTTP/1.0.
                modern = protocol.is_modern_request(msg)
                if modern:
                    err = validate_modern_headers(self.headers, msg)
                    if err is not None:
                        self._send_json(400, err)
                        return
                else:
                    # Absent means "assume 2025-03-26" (spec SHOULD), which is
                    # what we speak. A body with no _meta naming a modern
                    # revision in the header is a broken client: the list it
                    # can act on is the legacy one.
                    version = self.headers.get("MCP-Protocol-Version")
                    if (version is not None
                            and version not in protocol.LEGACY_VERSIONS):
                        self._send_json(400, protocol.unsupported_version_error(
                            msg.get("id"), version, protocol.LEGACY_VERSIONS))
                        return

                msg_id = msg.get("id")
                try:
                    response = transport._handler(msg) if transport._handler else None
                except Exception as e:
                    response = protocol.make_error(
                        msg_id, protocol.INTERNAL_ERROR, str(e))

                if msg_id is None:
                    self.send_response(202)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return

                if response is None:
                    response = protocol.make_error(
                        msg_id, protocol.INTERNAL_ERROR,
                        "Server produced no response for method %r"
                        % msg.get("method"))

                self._send_json(_status_for(response, modern), response)

            def _send_json(self, code: int, msg: dict):
                data = json.dumps(msg, separators=(",", ":")).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_OPTIONS(self):
                if not self._authorized():
                    return
                # No permissive CORS: a cross-origin preflight gets no
                # Access-Control-Allow-Origin, so the browser blocks the
                # follow-up request (do_POST also rejects it server-side).
                self.send_response(204)
                self.end_headers()

        class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
            daemon_threads = True
            # FreeWorks: en Windows SO_REUSEADDR deja que OTRO programa escuche en el mismo puerto
            # y reciba los pedidos (con la clave): puerto exclusivo (visto el 01/11 con un FreeCAD
            # que quedó colgado escuchando en el mismo puerto que el nuevo).
            allow_reuse_address = not hasattr(socket, "SO_EXCLUSIVEADDRUSE")

            def server_bind(self):
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                super().server_bind()

        return ThreadedHTTPServer((self._host, self._port), RequestHandler)

    def _send_sse(self, msg: dict):
        """Send a JSON-RPC message to the connected SSE client."""
        data = json.dumps(msg, separators=(",", ":"))
        payload = f"event: message\ndata: {data}\n\n".encode()
        self._write_locked(payload)

    def _write_locked(self, payload: bytes) -> bool:
        """Write raw bytes to the SSE client, serialized by ``_sse_lock``.

        The lock is held across the write *and* flush (not just the pointer
        read), so the keepalive loop and tool responses — which run on
        separate ThreadingMixIn request threads — cannot interleave bytes and
        corrupt the event stream. Returns False if there is no connected
        client or the connection has dropped (the client is then cleared).
        """
        with self._sse_lock:
            wfile = self._sse_wfile
            if wfile is None:
                return False
            try:
                wfile.write(payload)
                wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError, OSError):
                self._sse_wfile = None
                return False
