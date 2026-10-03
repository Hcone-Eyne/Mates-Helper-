# Tool registry and router for FoxAgent
# Wires Schedule_Bot, Finance_bot, and web tools into a single dispatch layer.

import re
import html
import ipaddress
import socket
import urllib.request
import urllib.parse
import urllib.error
from collections import OrderedDict

import pandas as pd

# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

TOOLS = OrderedDict()       # name -> {"description": ..., "params": [...], "fn": callable}


def _register(name, description, params, fn):
    """Register a tool that FoxAgent can call.

    *name*        – identifier the model will emit (e.g. "finance_calculate")
    *description* – one-line explanation shown to the model
    *params*      – list of {"name": ..., "type": ..., "desc": ...} dicts
    *fn*          – callable(**kwargs) -> str
    """
    TOOLS[name] = {
        "description": description,
        "params": params,
        "fn": fn,
    }


def dispatch(tool_name, **kwargs):
    """Run a registered tool and return its string result."""
    tool = TOOLS.get(tool_name)
    if tool is None:
        return f"[Fox]: Unknown tool '{tool_name}'."
    try:
        return tool["fn"](**kwargs)
    except Exception as e:
        return f"[Fox]: Tool '{tool_name}' error: {e}"


def tool_prompt_block():
    """Return the tool list block to embed in the system prompt."""
    if not TOOLS:
        return ""
    lines = [
        "You have access to these tools. To use one, write EXACTLY this format on its own line:",
        "",
        '  >>TOOL: tool_name(param="value")<<',
        "",
        "IMPORTANT: There MUST be a space between the tool name and the opening parenthesis.",
        "Available tools:",
    ]
    for name, info in TOOLS.items():
        param_str = ", ".join(f'{p["name"]}="..."' for p in info["params"]) if info["params"] else ""
        if param_str:
            lines.append(f'  >>TOOL: {name}({param_str})<<  -- {info["description"]}')
        else:
            lines.append(f'  >>TOOL: {name}()<<  -- {info["description"]}')
    lines.append("")
    lines.append("You MUST wait for the tool result before claiming any action was performed.")
    lines.append("Never fabricate tool results. If a tool fails, say so honestly.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper: safely read schedule CSV (shared by schedule tools)
# ---------------------------------------------------------------------------

def _load_schedule():
    from Path_mapper import SCHEDULE_CSV
    return pd.read_csv(SCHEDULE_CSV)


# ---------------------------------------------------------------------------
# Schedule Tools
# ---------------------------------------------------------------------------

def _schedule_view():
    df = _load_schedule()
    return df.to_string(index=False) if not df.empty else "[Fox]: Schedule is empty."


def _schedule_ask(query=""):
    from bot import query_handler
    data = _load_schedule()
    result = query_handler(query, data)
    if isinstance(result, pd.DataFrame):
        return result.to_string(index=False) if not result.empty else "[Fox]: Nothing found."
    return str(result)


_register(
    name="schedule_view",
    description="View the full class schedule.",
    params=[],
    fn=_schedule_view,
)

_register(
    name="schedule_ask",
    description="Ask about the schedule (e.g. day name, 'today', 'books').",
    params=[{"name": "query", "type": "str", "desc": "Natural language query about the schedule"}],
    fn=_schedule_ask,
)


# ---------------------------------------------------------------------------
# Finance Tools
# ---------------------------------------------------------------------------

def _finance_calculate(expression=""):
    from Finance_bot.operations_finder import operation_finder
    from Memory.memory_storer import memory_catcher
    result = operation_finder(expression)
    if result is None:
        return "[Fox]: Invalid expression. Use digits and operators + - * /."
    memory_catcher(expression, result)
    return f"[Fox]: Result -> {result}"


def _finance_history():
    from Memory.memory_storer import memory_dataframe
    df = memory_dataframe()
    return df.to_string(index=False) if not df.empty else "[Fox]: No calculation history."


def _finance_clear_history():
    from Memory.memory_storer import memory_eraser
    memory_eraser()
    return "[Fox]: Memory erased."


def _expense_summary(path=""):
    from Finance_bot.Expense_analyzer import load_statement, build_summary
    try:
        df = load_statement(path)
    except Exception as e:
        return f"[Fox]: {e}"
    summary = build_summary(df)
    if summary is None:
        return "[Fox]: No transactions found."
    lines = [f"Expense summary for {summary['month']}:"]
    for category, amount in summary["by_category"].items():
        sign = "+" if amount >= 0 else "-"
        lines.append(f"  {category}: {sign}{abs(amount):.0f}")
    lines.append(f"  Total spend: {summary['total_spend']:.0f}")
    if summary["prev_spend"] not in (None, 0, 0.0):
        diff = summary["total_spend"] - summary["prev_spend"]
        pct = (diff / summary["prev_spend"]) * 100
        direction = "extra" if diff >= 0 else "less"
        lines.append(f"  That's {pct:+.0f}% {direction} than last month.")
    return "\n".join(lines)


_register(
    name="finance_calculate",
    description="Evaluate a math expression (supports +, -, *, / and negatives).",
    params=[{"name": "expression", "type": "str", "desc": "Math expression like '12+3*2'"}],
    fn=_finance_calculate,
)

_register(
    name="finance_history",
    description="View history of past financial calculations.",
    params=[],
    fn=_finance_history,
)

_register(
    name="finance_clear_history",
    description="Clear the stored calculation history.",
    params=[],
    fn=_finance_clear_history,
)

_register(
    name="expense_summary",
    description="Analyze a bank/GPay statement (CSV or PDF) and return spending breakdown.",
    params=[{"name": "path", "type": "str", "desc": "File path to the statement (.csv or .pdf)"}],
    fn=_expense_summary,
)


# ---------------------------------------------------------------------------
# Web Tools  (no external pip dependencies — uses stdlib only)
# ---------------------------------------------------------------------------

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _web_search(query="", max_results=5):
    """Search the web via DuckDuckGo HTML and return top results."""
    params = urllib.parse.urlencode({"q": query, "t": "h_", "ia": "web"})
    url = f"https://html.duckduckgo.com/html/?{params}"

    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"[Fox]: Web search failed: {e}"

    # Parse result blocks from DuckDuckGo HTML
    results = []
    for m in re.finditer(
        r'<a[^>]+class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        raw, re.DOTALL,
    ):
        href, title, snippet = m.groups()
        title = html.unescape(re.sub(r"<.*?>", "", title)).strip()
        snippet = html.unescape(re.sub(r"<.*?>", "", snippet)).strip()
        # DuckDuckGo wraps URLs in a redirect; extract the real URL
        uddg = re.search(r"uddg=([^&]+)", href)
        real_url = urllib.parse.unquote(uddg.group(1)) if uddg else href
        results.append({"title": title, "url": real_url, "snippet": snippet})
        if len(results) >= max_results:
            break

    if not results:
        return f"[Fox]: No results found for '{query}'."

    lines = [f"Search results for '{query}':\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   {r['url']}")
        lines.append(f"   {r['snippet']}\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Web fetch safety (SSRF guard for the LLM-controlled web_browse tool)
# ---------------------------------------------------------------------------

_WEB_BROWSE_TIMEOUT = 15
_WEB_BROWSE_MAX_CHARS = 4000


def _ip_is_blocked(address) -> bool:
    """Return True for loopback, private, link-local, multicast, or
    unspecified addresses (including IPv4-mapped IPv6 forms)."""
    candidates = [address]
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        candidates.append(address.ipv4_mapped)
    return any(
        candidate.is_loopback
        or candidate.is_private
        or candidate.is_link_local
        or candidate.is_multicast
        or candidate.is_unspecified
        for candidate in candidates
    )


def _validate_url_for_fetch(url) -> str | None:
    """Safety gate for web_browse.

    Returns None when the URL is allowed, otherwise a `[Fox]` error string.
    Every hostname is resolved and every resolved address is checked - a
    blocked literal and a hostile DNS answer are refused alike.
    """
    if not isinstance(url, str) or not url.strip():
        return "[Fox]: No URL was provided."
    try:
        parsed = urllib.parse.urlsplit(url.strip())
    except ValueError as exc:
        return f"[Fox]: URL is not allowed ({exc})."
    if parsed.scheme.lower() not in ("http", "https"):
        return "[Fox]: URL is not allowed. Only http:// and https:// addresses can be fetched."
    if parsed.username or parsed.password:
        return "[Fox]: URL is not allowed. Credentials must not be embedded in the URL."
    try:
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        return f"[Fox]: URL is not allowed ({exc})."
    if not host:
        return "[Fox]: URL is not allowed. The address has no host."
    host = host.strip().rstrip(".")
    if not host:
        return "[Fox]: URL is not allowed. The address has no host."
    lowered = host.lower()
    if lowered == "localhost" or lowered.endswith(".localhost"):
        return "[Fox]: URL is not allowed (localhost is blocked)."
    try:
        literal = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        literal = None
    if literal is not None:
        if _ip_is_blocked(literal):
            return "[Fox]: URL is not allowed (blocked IP address)."
        return None
    default_port = 443 if parsed.scheme.lower() == "https" else 80
    try:
        infos = socket.getaddrinfo(host, port or default_port, type=socket.SOCK_STREAM)
    except OSError:
        return f"[Fox]: URL is not allowed. Could not resolve '{host}'."
    if not infos:
        return f"[Fox]: URL is not allowed. Could not resolve '{host}'."
    for info in infos:
        try:
            resolved = ipaddress.ip_address(info[4][0].split("%", 1)[0])
        except ValueError:
            return f"[Fox]: URL is not allowed. Could not verify '{host}'."
        if _ip_is_blocked(resolved):
            return "[Fox]: URL is not allowed because it resolves to a blocked address."
    return None


class _BlockedURLError(ValueError):
    """Raised when a redirect target fails URL safety validation."""


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow HTTP redirects only to URLs that pass fetch validation."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urljoin(req.get_full_url(), newurl)
        error = _validate_url_for_fetch(target)
        if error is not None:
            raise _BlockedURLError(error)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _web_browse(url=""):
    """Fetch a URL and return its visible text content (first 4000 chars)."""
    blocked = _validate_url_for_fetch(url)
    if blocked is not None:
        return blocked
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        opener = urllib.request.build_opener(_SafeRedirectHandler())
        with opener.open(req, timeout=_WEB_BROWSE_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except _BlockedURLError as exc:
        return str(exc)
    except Exception as e:
        return f"[Fox]: Could not fetch '{url}': {e}"

    # Strip HTML tags to get visible text
    text = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return f"[Fox]: Page at '{url}' returned empty content."

    return text[:_WEB_BROWSE_MAX_CHARS] + ("..." if len(text) > _WEB_BROWSE_MAX_CHARS else "")


_register(
    name="web_search",
    description="Search the web for information on any topic.",
    params=[{"name": "query", "type": "str", "desc": "Search query"}],
    fn=_web_search,
)

_register(
    name="web_browse",
    description="Fetch and read the content of a specific URL.",
    params=[{"name": "url", "type": "str", "desc": "URL to load and read"}],
    fn=_web_browse,
)

# Fox Club member tool

_fox_club_runtime = None


def _get_fox_club_runtime():
    global _fox_club_runtime

    from agent.fox.runtime.runtime import build_runtime
    from File_Manager.organizer import VAULT_ROOT, ensure_vault
    from brain.orchestrator import get_think

    if _fox_club_runtime is None:
        ensure_vault()
        _fox_club_runtime = build_runtime(target_dir=VAULT_ROOT, think=get_think())
    return _fox_club_runtime


def _fox_club_task(request=""):
    request = request.strip()
    if not request:
        return "[Fox]: Give me a file task, e.g. 'organise my files by type' or 'list what's in the vault'. "

    runtime = _get_fox_club_runtime()
    result = runtime.handle(request)
    selina = result.selina_result
    gwen = result.gwen_result

    lines = [f"[Fox Club] Action: {selina.action or 'none determined'}"]
    if selina.success:
        lines.append(f"Result: {selina.result}")
    else:
        lines.append(f"Result: {selina.result}")
    lines.append(f"Reviewed by Gwen: {'approved' if gwen.approved else 'flagged for review'}")
    if gwen.critique:
        lines.append(f"Gwen's note: {gwen.critique}")
    return "\n".join(lines)


_register(
    name="fox_club_task",
    description=(
        "Run a file task (list, sort, or organise files) through the Julie->Annie->"
        "Selina->Gwen review pipeline. Scoped to the app's Vault folder."
    ),
    params=[{"name": "request", "type": "str", "desc": "What to do, e.g. 'organise files by type'"}],
    fn=_fox_club_task,
)