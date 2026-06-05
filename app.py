import subprocess
import json
import re
import os
import glob as glob_mod
import urllib.request
import urllib.parse
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_file as flask_send_file

app = Flask(__name__)
OBSCURA_BIN = "./target-build/debug/obscura"
AI_BASE_URL   = os.environ.get("AI_BASE_URL", "").rstrip("/")
AI_API_KEY    = os.environ.get("AI_API_KEY", "")
AI_MODEL      = os.environ.get("AI_MODEL", "")
AI_TEMPERATURE = float(os.environ.get("AI_TEMPERATURE", "0.7"))
WORKSPACE    = "/home/runner/workspace"

# ── Shell session store (keyed by id) ──
_shells: dict[str, subprocess.Popen] = {}
_shell_outputs: dict[str, list[str]] = {}

# ══════════════════════════════════════════
#  SYSTEM PROMPT
# ══════════════════════════════════════════
SYSTEM_PROMPT = """You are Dzeck Agent, an autonomous AI agent created to help users complete complex tasks using internet access, file operations, and code execution.

You excel at the following tasks:
1. Information gathering, fact-checking, and documentation
2. Data processing, analysis, and visualization
3. Writing multi-chapter articles and in-depth research reports
4. Creating websites, applications, and tools
5. Using programming to solve various problems beyond development
6. Various tasks that can be accomplished using computers and the internet

Use the language specified by the user in their messages as the working language (Indonesian or English). All responses and tool call arguments must be in the working language. Avoid using pure lists and bullet points format in any language.

System capabilities:
- Communicate with users through message_notify_user tool
- Access a workspace with internet connection
- Use shell_exec to run commands and code in Python, Bash, Node.js, and others
- Read, write, and edit files in the workspace using file tools
- Search the web and browse any URL using search_web and browse_web
- Independently install required packages via shell_exec (pip install, npm install, etc.)

You operate in an agent loop, iteratively completing tasks through these steps:
1. Analyze the request: understand the user's need and current state
2. Select tools: choose the best next tool call based on current state
3. Wait for result: use the tool output to decide the next step
4. Iterate: patiently repeat until the task is fully complete
5. Submit results: send final answer and any created files via message_notify_user

Additional rules:
- Always use message_notify_user to acknowledge a new task immediately, then proceed
- For complex tasks, create todo.md as a checklist and update it with file_str_replace after each step
- Information priority: web search > browsed page content > internal knowledge
- Always browse original pages — search snippets alone are not sufficient sources
- Always write code to a file first using file_write, then execute with shell_exec
- Use -y and -q flags in shell commands to avoid interactive prompts
- Save long outputs to files; don't print everything to stdout
- When writing reports or articles, save each section as a draft file then compile into one final file
- Write in continuous paragraphs, not bullet lists, for prose content
- When a tool fails, adjust arguments or try an alternative approach before reporting failure"""

# ══════════════════════════════════════════
#  TOOL DEFINITIONS
# ══════════════════════════════════════════
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "message_notify_user",
            "description": "Send a progress update or note to the user during task execution. Use to report what phase you're in, share intermediate findings, or explain your approach.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Message text to show the user"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the internet via DuckDuckGo. Returns titles, URLs, and snippets. Use first when you need to find information or don't know a specific URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query, 3-5 keywords"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browse_web",
            "description": "Open and read a specific web page. Use after searching, or when you know the URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL including https://"},
                    "mode": {
                        "type": "string",
                        "enum": ["text", "markdown", "links"],
                        "description": "text=readable, markdown=structured with headers, links=all URLs on page",
                        "default": "text"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Read the content of a file. Use to inspect existing files, logs, or code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "Absolute or relative path to the file"},
                    "start_line": {"type": "integer", "description": "(Optional) Starting line, 0-based"},
                    "end_line":   {"type": "integer", "description": "(Optional) Ending line (exclusive)"}
                },
                "required": ["file"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_write",
            "description": "Create or overwrite a file with given content. Use to save code, reports, data, or notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file":    {"type": "string",  "description": "Absolute or relative path to write"},
                    "content": {"type": "string",  "description": "Text content to write"},
                    "append":  {"type": "boolean", "description": "(Optional) If true, append instead of overwrite"}
                },
                "required": ["file", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_str_replace",
            "description": "Replace a specific string in a file. Use to edit parts of existing code or text without rewriting the whole file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file":    {"type": "string", "description": "Path to the file"},
                    "old_str": {"type": "string", "description": "Exact string to find and replace"},
                    "new_str": {"type": "string", "description": "Replacement string"}
                },
                "required": ["file", "old_str", "new_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_find_in_content",
            "description": "Search for a regex pattern inside a file's content. Returns matching lines with line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file":  {"type": "string", "description": "Path to the file to search"},
                    "regex": {"type": "string", "description": "Regular expression pattern to find"}
                },
                "required": ["file", "regex"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_find_by_name",
            "description": "Find files matching a name pattern (glob) in a directory. Use to locate files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to search in"},
                    "glob": {"type": "string", "description": "Glob pattern, e.g. '*.py' or '**/*.json'"}
                },
                "required": ["path", "glob"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "shell_exec",
            "description": "Execute a shell command and return its output. Use to run Python scripts, install packages, compile code, or perform any system operation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "(Optional) Timeout in seconds, default 30"}
                },
                "required": ["command"]
            }
        }
    },
]

# ══════════════════════════════════════════
#  TOOL IMPLEMENTATIONS
# ══════════════════════════════════════════

def run_obscura(args: list[str], timeout: int = 45) -> dict:
    try:
        result = subprocess.run(
            [OBSCURA_BIN] + args, capture_output=True, text=True, timeout=timeout,
        )
        return {"success": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "Request timed out."}
    except FileNotFoundError:
        return {"success": False, "stdout": "", "stderr": "Binary not found. Run: CARGO_TARGET_DIR=target-build cargo build"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e)}


def _strip_think(text: str) -> str:
    """Hapus blok <think>...</think> yang disisipkan model (misal Qwen3 thinking mode)."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def normalize_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        return re.sub(r"<[^>]+>", "", match.group(1)).strip()
    return ""


def do_search(query: str) -> str:
    encoded = urllib.parse.quote(query)
    url = f"https://lite.duckduckgo.com/lite/?q={encoded}"
    result = run_obscura(["fetch", url, "--dump", "markdown", "--wait", "4"])
    if result["success"]:
        c = result["stdout"].strip()
        return (c[:6000] + "\n...[truncated]") if len(c) > 6000 else c
    return f"Search failed: {result['stderr']}"


def do_browse(url: str, mode: str = "text") -> str:
    url = normalize_url(url)
    result = run_obscura(["fetch", url, "--dump", mode, "--wait", "5"])
    if result["success"]:
        c = result["stdout"].strip()
        limit = 8000 if mode == "markdown" else 5000
        return (c[:limit] + "\n...[truncated]") if len(c) > limit else c
    return f"Error fetching {url}: {result['stderr']}"


def do_file_read(path: str, start_line: int = None, end_line: int = None) -> str:
    try:
        p = path if os.path.isabs(path) else os.path.join(WORKSPACE, path)
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        if start_line is not None or end_line is not None:
            lines = lines[start_line:end_line]
        content = "".join(lines)
        return (content[:8000] + "\n...[truncated]") if len(content) > 8000 else content
    except Exception as e:
        return f"Error reading file: {e}"


def do_file_write(path: str, content: str, append: bool = False) -> str:
    try:
        p = path if os.path.isabs(path) else os.path.join(WORKSPACE, path)
        os.makedirs(os.path.dirname(p) if os.path.dirname(p) else WORKSPACE, exist_ok=True)
        mode = "a" if append else "w"
        with open(p, mode, encoding="utf-8") as f:
            f.write(content)
        action = "Appended to" if append else "Written"
        return f"{action}: {p} ({len(content)} chars)"
    except Exception as e:
        return f"Error writing file: {e}"


def do_file_str_replace(path: str, old_str: str, new_str: str) -> str:
    try:
        p = path if os.path.isabs(path) else os.path.join(WORKSPACE, path)
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
        if old_str not in content:
            return f"String not found in {p}"
        with open(p, "w", encoding="utf-8") as f:
            f.write(content.replace(old_str, new_str, 1))
        return f"Replaced successfully in {p}"
    except Exception as e:
        return f"Error: {e}"


def do_file_find_in_content(path: str, regex: str) -> str:
    try:
        p = path if os.path.isabs(path) else os.path.join(WORKSPACE, path)
        results = []
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                if re.search(regex, line):
                    results.append(f"Line {i}: {line.rstrip()}")
        return "\n".join(results[:100]) if results else "No matches found."
    except Exception as e:
        return f"Error: {e}"


def do_file_find_by_name(path: str, pattern: str) -> str:
    try:
        p = path if os.path.isabs(path) else os.path.join(WORKSPACE, path)
        matches = glob_mod.glob(os.path.join(p, "**", pattern), recursive=True)
        matches = [m for m in matches if ".git" not in m and "target" not in m]
        return "\n".join(matches[:50]) if matches else "No files found."
    except Exception as e:
        return f"Error: {e}"


def do_shell_exec(command: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=WORKSPACE,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        out = ""
        if result.stdout.strip(): out += result.stdout
        if result.stderr.strip(): out += ("\nSTDERR:\n" if result.stdout.strip() else "") + result.stderr
        out = out.strip() or "(no output)"
        return (out[:6000] + "\n...[truncated]") if len(out) > 6000 else out
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s."
    except Exception as e:
        return f"Error: {e}"


# ══════════════════════════════════════════
#  AI REQUEST
# ══════════════════════════════════════════
def ai_request(messages: list, tools: list = None) -> dict:
    payload = {"model": AI_MODEL, "messages": messages, "temperature": AI_TEMPERATURE}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{AI_BASE_URL}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {AI_API_KEY}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read())


# ══════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/fetch", methods=["POST"])
def api_fetch():
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    mode = data.get("mode", "text")
    selector = data.get("selector", "").strip()
    stealth = data.get("stealth", False)
    user_agent = data.get("user_agent", "").strip()
    eval_js = data.get("eval_js", "").strip()
    wait = str(data.get("wait", 5))

    if not url:
        return jsonify({"success": False, "error": "URL tidak boleh kosong."})
    url = normalize_url(url)
    args = ["fetch", url, "--dump", mode, "--wait", wait]
    if selector:   args += ["--selector", selector]
    if stealth:    args += ["--stealth"]
    if user_agent: args += ["--user-agent", user_agent]
    if eval_js:    args += ["--eval", eval_js]

    result = run_obscura(args)
    if not result["success"]:
        return jsonify({"success": False, "error": result["stderr"] or "Gagal mengambil halaman."})
    content = result["stdout"]
    title = ""
    if mode == "html":
        title = extract_title(content)
    elif mode in ("links", "assets"):
        lines = [l.strip() for l in content.strip().splitlines() if l.strip()]
        return jsonify({"success": True, "title": f"{len(lines)} item ditemukan", "content": content, "mode": mode, "count": len(lines)})
    return jsonify({"success": True, "title": title, "content": content, "mode": mode})


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    data = request.get_json() or {}
    urls_raw = data.get("urls", "").strip()
    concurrency = str(data.get("concurrency", 5))
    eval_js = data.get("eval_js", "").strip()

    if not urls_raw:
        return jsonify({"success": False, "error": "URL tidak boleh kosong."})
    urls = [normalize_url(u.strip()) for u in urls_raw.splitlines() if u.strip()][:10]
    args = ["scrape", "--concurrency", concurrency, "--format", "json"]
    if eval_js: args += ["--eval", eval_js]
    args += urls

    result = run_obscura(args, timeout=90)
    stdout = result["stdout"].strip()

    if not stdout and not result["success"]:
        return jsonify({"success": False, "error": result["stderr"] or "Scraping gagal."})

    # Binary outputs a single JSON object: {"results": [...], ...}
    # Attempt to parse it directly; fall back to NDJSON for older builds.
    raw_results = []
    try:
        parsed = json.loads(stdout)
        if isinstance(parsed, dict) and "results" in parsed:
            raw_results = parsed["results"]
        elif isinstance(parsed, list):
            raw_results = parsed
    except Exception:
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw_results.append(json.loads(line))
            except Exception:
                pass

    if not raw_results:
        return jsonify({"success": False, "error": "Tidak ada hasil. " + (result["stderr"] or "")})

    # Normalise each item to {url, result, error} that the UI expects
    results = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        url_val   = item.get("url", "")
        err_val   = item.get("error") or None
        # Prefer content > text > title as the displayable result
        content   = item.get("content") or item.get("text") or item.get("title") or ""
        results.append({"url": url_val, "result": content, "error": err_val})

    return jsonify({"success": True, "results": results})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    if not AI_BASE_URL or not AI_API_KEY or not AI_MODEL:
        missing = [k for k, v in [("AI_BASE_URL", AI_BASE_URL), ("AI_API_KEY", AI_API_KEY), ("AI_MODEL", AI_MODEL)] if not v]
        return jsonify({"success": False, "error": f"AI belum dikonfigurasi: {', '.join(missing)} belum diset."})

    data = request.get_json() or {}
    history = data.get("history", [])
    user_msg = data.get("message", "").strip()
    if not user_msg:
        return jsonify({"success": False, "error": "Pesan tidak boleh kosong."})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": user_msg}]

    def generate():
        steps = []
        current_messages = messages[:]

        try:
            for _ in range(30):
                resp = ai_request(current_messages, TOOLS)
                choice = resp["choices"][0]
                msg = choice["message"]
                current_messages.append(msg)

                if choice["finish_reason"] == "tool_calls":
                    for tc in msg.get("tool_calls", []):
                        fn = tc["function"]
                        try:
                            args = json.loads(fn["arguments"])
                        except Exception:
                            args = {}

                        name = fn["name"]

                        # ── message_notify_user ──
                        if name == "message_notify_user":
                            text = _strip_think(args.get("text", ""))
                            step = {"icon": "notify", "text": text}
                            steps.append(step)
                            yield f"data: {json.dumps({'type': 'step', **step})}\n\n"
                            content = "OK"

                        # ── search_web ──
                        elif name == "search_web":
                            query = args.get("query", "")
                            step = {"icon": "search", "text": f"Mencari: {query}"}
                            steps.append(step)
                            yield f"data: {json.dumps({'type': 'step', **step})}\n\n"
                            content = do_search(query)

                        # ── browse_web ──
                        elif name == "browse_web":
                            url = args.get("url", "")
                            mode = args.get("mode", "text")
                            step = {"icon": "browse", "text": f"Membuka: {url}"}
                            steps.append(step)
                            yield f"data: {json.dumps({'type': 'step', **step})}\n\n"
                            content = do_browse(url, mode)

                        # ── file_read ──
                        elif name == "file_read":
                            path = args.get("file", "")
                            step = {"icon": "file", "text": f"Membaca file: {path}"}
                            steps.append(step)
                            yield f"data: {json.dumps({'type': 'step', **step})}\n\n"
                            content = do_file_read(path, args.get("start_line"), args.get("end_line"))

                        # ── file_write ──
                        elif name == "file_write":
                            path = args.get("file", "")
                            step = {"icon": "file", "text": f"Menulis file: {path}"}
                            steps.append(step)
                            yield f"data: {json.dumps({'type': 'step', **step})}\n\n"
                            content = do_file_write(path, args.get("content", ""), args.get("append", False))
                            # Emit download event so the UI shows a download chip
                            abs_path = path if os.path.isabs(path) else os.path.join(WORKSPACE, path)
                            if "Error" not in content and os.path.exists(abs_path):
                                fname = os.path.basename(abs_path)
                                yield f"data: {json.dumps({'type': 'file_created', 'path': abs_path, 'name': fname})}\n\n"

                        # ── file_str_replace ──
                        elif name == "file_str_replace":
                            path = args.get("file", "")
                            step = {"icon": "file", "text": f"Mengedit file: {path}"}
                            steps.append(step)
                            yield f"data: {json.dumps({'type': 'step', **step})}\n\n"
                            content = do_file_str_replace(path, args.get("old_str", ""), args.get("new_str", ""))

                        # ── file_find_in_content ──
                        elif name == "file_find_in_content":
                            path = args.get("file", "")
                            step = {"icon": "file", "text": f"Mencari dalam: {path}"}
                            steps.append(step)
                            yield f"data: {json.dumps({'type': 'step', **step})}\n\n"
                            content = do_file_find_in_content(path, args.get("regex", ""))

                        # ── file_find_by_name ──
                        elif name == "file_find_by_name":
                            step = {"icon": "file", "text": f"Mencari file: {args.get('glob', '')}"}
                            steps.append(step)
                            yield f"data: {json.dumps({'type': 'step', **step})}\n\n"
                            content = do_file_find_by_name(args.get("path", WORKSPACE), args.get("glob", "*"))

                        # ── shell_exec ──
                        elif name == "shell_exec":
                            cmd = args.get("command", "")
                            timeout = args.get("timeout", 30)
                            step = {"icon": "shell", "text": f"$ {cmd}"}
                            steps.append(step)
                            yield f"data: {json.dumps({'type': 'step', **step})}\n\n"
                            content = do_shell_exec(cmd, timeout)

                        else:
                            content = f"Tool '{name}' tidak dikenal."

                        current_messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": content,
                        })
                    continue

                reply = _strip_think(msg.get("content", ""))
                yield f"data: {json.dumps({'type': 'done', 'reply': reply, 'steps': steps, 'messages': current_messages[1:]})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'error', 'error': 'Agen mencapai batas iterasi.'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/download")
def api_download():
    path = request.args.get("path", "").strip()
    if not path:
        return jsonify({"error": "Path tidak boleh kosong."}), 400
    abs_path = path if os.path.isabs(path) else os.path.join(WORKSPACE, path)
    abs_path = os.path.realpath(abs_path)
    # Security: hanya boleh download dari dalam WORKSPACE
    if not abs_path.startswith(os.path.realpath(WORKSPACE)):
        return jsonify({"error": "Akses ditolak."}), 403
    if not os.path.isfile(abs_path):
        return jsonify({"error": "File tidak ditemukan."}), 404
    return flask_send_file(abs_path, as_attachment=True, download_name=os.path.basename(abs_path))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
