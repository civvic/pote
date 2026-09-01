"""Start, reuse, inspect, preview, and stop FastHTML servers in Jupyter or Solveit; register browser ES modules, including versioned modules for iterative development.

### Choosing a helper

```python
from pote.server import ensure_server_a, serve_app, setup_mod, add_js_msg
```

- `await ensure_server_a(...)` starts or reuses a FastHTML server and returns `(srv, app, rt, p)`; by default it selects a free non-public port.
- `async with serve_app(...)` is for a scoped server that is stopped automatically, particularly in tests.
- `find_server`, `is_serving_a`, and `stop_server_a` inspect and clean up existing server state.
- `free_port(public=True)` returns first available public port.
- `p(path)` previews a route in an iframe on a public port; it is None for private ports.
- `setup_mod(..., versioned=True)` supports iterative browser ES-module work.
- `get_js`, `add_js_msg`, and `setup_mod` without `src` extract JavaScript from a `%%js`/`%%javascript` message.

The async APIs are normally preferable in Solveit and Jupyter. These helpers target FastHTML applications; the underlying `JupyUvi` can serve more general ASGI applications, but `pote.server` does not promise that compatibility.

### Local dialog server

For the usual local dialog/notebook case, use default settings for non-public port selection:

```python
srv,app,rt,p = await ensure_server_a()

@rt
def hello(): return 'hello'

cli = TestClient(app)
test_eq(cli.get('/hello').text, 'hello')
```

Here `p` is `None`: private ports cannot be previewed in a Solveit iframe or used to setup ES modules loader. This is the normal mode for local notebook/dialog work and direct ASGI tests, rather than deploying a web application.

### Public server

```python
srv,app,rt,p = await ensure_server_a(public=True)

@rt
def hello(): return 'hello'
```

`await ensure_server_a(public=True)` argument is equivalent to `await ensure_server_a(port=free_port(public=True), host='0.0.0.0')`.

Then:

```python
p('/hello')
```

or:

```python
P(hx_get='/hello', hx_trigger='load once')
```

Stop server:

```python
await stop_server_a(srv.port)
```

`ensure_server_a()` returns the server bundle `(srv, app, rt, p)`:

- `srv` controls the uvicorn lifecycle.
- `app` is the application actually being served.
- `rt` is its FastHTML route decorator.
- `p` previews routes through the returned server.

Selection precedence is:

1. An explicit live `srv`.
2. A live `JupyUvi` already bound to the requested port.
3. A newly created server.

When an explicit or discovered server is reused, `app`, `app_kw`, and `jupyuvi_kw` are ignored. For an explicit `srv`, its own port is authoritative and the requested `port` is ignored. `mods` are still registered, and the ESM route is installed on the reused app. `port=None` selects a free port outside Solveit’s public-port allocation.

In notebooks, prefer `await stop_server_a(srv.port)`, which supports synchronous and asynchronous servers and clears all namespace aliases to the stopped server.

### CRAFT-local server
> `ensure_server_a` is designed as reusable dialog infrastructure, rather than as a web-app deployment or a special kind of server lifetime.

A CRAFT can initialize a local server once for the dialog:

```python
srv,app,rt,_ = await ensure_server_a()
```

This creates or reuses a non-public FastHTML server and returns the `(srv, app, rt, None)` bundle. Later cells can add routes through `rt` or test `app` directly without server setup.

### Temporary server and testing

Use `serve_app` when a server should exist only for a block:

```python
async with serve_app() as test_srv:
    @test_srv.app.get('/hello')
    def hello(): return 'hello'

    cli = TestClient(test_srv.app)
    test_eq(cli.get('/hello').text, 'hello')
```

`serve_app` always starts a fresh server and owns its lifetime. It stops that server after normal exit, setup or body errors, and cancellation. An explicitly requested port must be free; an occupied port raises rather than reusing its existing server.

The context temporarily scopes the notebook namespace. A new alias such as `test_srv` is removed on exit; an existing name temporarily rebound by the context is restored.

Route changes made to `test_srv.app` persist on a caller-supplied app.

The context yields the live server; use `test_srv.app`, `test_srv.port`, and its other attributes inside the block. `port=None` selects a free non-public port by default.

### Uvicorn logging

`setup_uvi_logging` routes the `uvicorn`, `uvicorn.error`, and `uvicorn.access` loggers to a callable and returns a cleanup function that restores their previous configuration.

Pass `log_config=None` when starting uvicorn; otherwise uvicorn may replace the custom logger configuration.

```python
cleanup = setup_uvi_logging(my_log)
try:
    async with serve_app(log_config=None) as srv:
        ...
finally:
    cleanup()
```

Logging configuration is process-global rather than server-owned, so the caller is responsible for cleanup.

### Browser ES modules

Register and import JavaScript in the active Solveit browser with:

```python
src = 'export const answer = 42'
nm,res = await setup_mod('editor', src, versioned=True)
```

With `versioned=True`, repeated calls register successive names such as `editor_1` and `editor_2`, and import distinct URLs such as `/esm/editor?v=1`. Use this during iterative development to bypass the browser’s ES-module cache.

The module registry belongs to the current Python kernel, not to an app or server. Registering an existing key replaces its source, and registered entries survive server shutdown. There is currently no public operation for unregistering an entry or clearing the registry.

Registered modules are executable browser code and may be served through the app’s public HTTP endpoint. Register only trusted source; module names are not an authorization boundary.

An unversioned name provides a stable URL. Replacing its registered source changes future HTTP responses, but a browser that has already imported that URL may continue using its cached module.

If given, `dname` is URL-encoded and forwarded as the `dlg_name` query parameter during the browser import. It does not affect module-registry lookup; browser-side code can use it only if it reads that parameter.

`setup_mod` and `load_mod` import through a given or discovered server in the active Solveit browser. The resolved server must listen on a Solveit public port: port `8000` uses a relative import URL, while another public port uses its assigned public domain. A private port raises `RuntimeError` before browser evaluation.

If no live server is found and the requested public port is free, a temporary server is created for the import and stopped afterward. If the port is occupied by a non-discoverable process, setup fails rather than replacing it.

JavaScript can also come from a dialog message whose first line is `%%js` or `%%javascript`:

- `get_js` returns the source without the magic line.
- `setup_mod` without `src` extracts and imports the preceding JavaScript message.
- `add_js_msg` creates linked Python state containing the extracted source.

A missing registry entry is served as a valid diagnostic JavaScript module rather than an HTTP error, so an import may succeed without providing the expected exports.

Docs: https://civvic.github.io/pote/server.html.md"""

# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02_server.ipynb.

# %% auto #0
__all__ = ['wrap_endp', 'pub_ports', 'free_port', 'free_public_domain', 'pub_domain', 'find_server', 'is_serving', 'is_serving_a',
           'stop_server', 'stop_server_a', 'reg_mod', 'setup_loader', 'ensure_server_a', 'ensure_server',
           'setup_uvi_logging', 'serve_app', 'get_js', 'add_js_msg', 'load_mod', 'setup_mod']

# %% ../nbs/02_server.ipynb #92031bb1
import asyncio, inspect, json, keyword, logging, os, subprocess, re
from contextlib import asynccontextmanager
from collections.abc import Callable, AsyncIterator
from datetime import datetime
from functools import partial
from urllib.parse import quote
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response
from starlette.routing import Route
from fastcore.basics import first
from fastcore.aio import maybe_await
from fastcore.meta import delegates
from fastcore.net import is_port_free
from fastcore.xml import FT
from fasthtml.core import FastHTML
from fasthtml.jupyter import JupyUvi, JupyUviAsync, HTMX
from fasthtml.xtend import Script, Link
from dialoghelper.core import js_eval_a, read_msg
from .basic import Kounter
from .dutil import link_msg, set_var

# %% ../nbs/02_server.ipynb #cf02fba9
kntr = Kounter()

# %% ../nbs/02_server.ipynb #ff9bbe4e
def kill_port(port):
    "Forcibly terminate local processes listening on `port`; intended only for notebook recovery"
    subprocess.run(f"lsof -ti:{port} | xargs -r kill -9", shell=True)

# %% ../nbs/02_server.ipynb #f3930f80
def wrap_endp(
    response, # Existing request handler or fixed response value
) -> Callable:
    "Return callable handlers unchanged; otherwise return an async handler that returns `response` unchanged."
    if callable(response) and not isinstance(response, FT) and not hasattr(response, '__ft__'): return response
    async def endpoint(request): return response
    return endpoint

# %% ../nbs/02_server.ipynb #3ff9a50d
def pub_ports() -> tuple[int]:
    "Public ports reserved by this Solveit instance."
    return tuple(sorted(map(int, json.loads(os.environ.get('PUBLIC_DOMAINS', '{}')))))

# %% ../nbs/02_server.ipynb #bc24b67e
def free_port(
    start:int=6550, # First port to consider
    skip=(), # Ports to exclude even when available
    public:bool=False, # Restrict search to this instance's public ports?
    host:str='127.0.0.1', # Host interface used to test availability
) -> int:
    "Return the first available port; raise `RuntimeError` when none are available."
    skip, ports = set(skip), pub_ports() if public else range(start, 65536)
    if (port := first(p for p in ports if p not in skip and is_port_free(p, host))) is None: raise RuntimeError("No free port")
    return port

# %% ../nbs/02_server.ipynb #58ef6107
def free_public_domain():
    "Public domain for the first public port that is currently free."
    return json.loads(os.environ["PUBLIC_DOMAINS"])[str(free_port(public=True))]

def pub_domain(port):
    "Public domain for `port`."
    return json.loads(os.environ['PUBLIC_DOMAINS'])[str(port)]

# %% ../nbs/02_server.ipynb #43063d48
def find_server(
    port:int|None=None, # Port to match; `None` matches any port
    all_ports:bool=False, # Return every started binding across all ports; aliases may repeat the same server
) -> tuple[JupyUvi,str]|tuple[None,None]|list[tuple[JupyUvi,str]]:
    "Find namespace-bound `JupyUvi` objects whose flags indicate they are started; no HTTP health check. First-match order follows the IPython namespace."
    import IPython
    if all_ports: port = None
    ns = IPython.get_ipython().user_ns
    res = [(v,k) for k,v in ns.items() if isinstance(v, JupyUvi) and (port is None or v.port == port) and v.server and v.server.started and not v.server.should_exit]
    return res if all_ports else res[0] if res else (None,None)

# %% ../nbs/02_server.ipynb #57534b13
def _conn_host(host): return '127.0.0.1' if host in ('0.0.0.0', '::') else host

def is_serving(srv:JupyUvi|None, timeout=1) -> bool:
    "Return whether `srv` appears started and `GET /` completes with a status below 500."
    if not (srv and srv.server and srv.server.started and not srv.server.should_exit and not is_port_free(srv.port, srv.host)): return False
    try:
        import httpx
        return httpx.get(f"http://{_conn_host(srv.host)}:{srv.port}/", timeout=timeout).status_code < 500
    except Exception: return False

async def is_serving_a(srv:JupyUvi|None, timeout=1) -> bool:
    "Return whether `srv` appears started and `GET /` completes with a status below 500."
    if not (srv and srv.server and srv.server.started and not srv.server.should_exit and not is_port_free(srv.port, srv.host)): return False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as cli: return (await cli.get(f"http://{_conn_host(srv.host)}:{srv.port}/")).status_code < 500
    except Exception: return False

# %% ../nbs/02_server.ipynb #e9ba1960
daisyui_hdrs = (
    Link(href='https://cdn.jsdelivr.net/npm/daisyui@5', rel='stylesheet', type='text/css'),
    Script(src='https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4'),
    Link(href='https://cdn.jsdelivr.net/npm/daisyui@5/themes.css', rel='stylesheet', type='text/css'),
)
threejs_hdrs = (
    Script('{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.165.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.165.0/examples/jsm/"}}', type='importmap'),
)

# %% ../nbs/02_server.ipynb #6a6338b8
def _found_srvs(port=None):
    res = find_server(all_ports=True)
    if port is not None: res = [(srv,nm) for srv,nm in res if srv.port == port]
    srvs = {}
    for srv,nm in res:
        srvs.setdefault(id(srv), (srv, []))[1].append(nm)
    return list(srvs.values())

def stop_server(port:int|None=None) -> None:
    "Stop the discovered synchronous server on `port`, or all discovered servers when `port=None`."
    srvs = _found_srvs(port)
    if any(inspect.iscoroutinefunction(srv.stop) for srv,_ in srvs): raise RuntimeError("JupyUviAsync requires `await stop_server_a(port)`")
    for srv,nms in srvs:
        srv.stop()
        for nm in nms: set_var(nm, None)

async def stop_server_a(port:int|None=None) -> None:
    "Stop the discovered server on `port`, or all discovered servers when `port=None`."
    for srv,nms in _found_srvs(port):
        await maybe_await(srv.stop())
        for nm in nms: set_var(nm, None)

# %% ../nbs/02_server.ipynb #293afdf7
def _app_kw(app_kw, public):
    app_kw = dict(ifnone(app_kw, {}))
    if public: app_kw['middleware'] = [*app_kw.get('middleware', []), Middleware(
        CORSMiddleware,
        allow_origin_regex=r'''https://[a-f0-9]+\.solve\.it\.com''',
        allow_methods=['*'],
        allow_headers=['*'],
    )]
    return app_kw

def get_preview(app, port=8000, host=None):
    "Return a function that displays the app in an iframe."
    if host is None: host = None if port==8000 else json.loads(os.environ['PUBLIC_DOMAINS']).get(str(port), '127.0.0.1')
    return partial(HTMX, app=app, host=host, port=port if port in (8000, None) else 443)

def srv_bundle(srv):
    if hasattr(srv.app, 'route'): return srv,srv.app,srv.app.route,get_preview(srv.app, srv.port) if srv.port in pub_ports() else None
    else: return srv,srv.app,None,None

def _server_target(srv=None, port:int|None=None, host=None, reuse=True, public=False):
    own = False
    if srv is not None: return srv,port,host,own
    if port in pub_ports(): public = True
    if public: port,host = port if port in pub_ports() else free_port(public=True, host='0.0.0.0'),'0.0.0.0'
    check_host = host or ('0.0.0.0' if port in pub_ports() else '127.0.0.1')
    if port is None: port = free_port(6551, skip=pub_ports(), host=check_host)
    found,_ = find_server(port)
    if found:
        if public and found.host not in ('0.0.0.0', '::'): raise RuntimeError(f"Server on port {port} is not publicly bound")
        if not reuse: raise RuntimeError(f"Server already running on port {port}")
        return found,port,host,own
    if not is_port_free(port, check_host): raise RuntimeError(f"Port {port} in use but no JupyUvi instance found in namespace")
    return None,port,host,True

async def _ensure_server_a(srv=None, port:int|None=None, app=None, app_kw=None, reuse=True, public=False, **jupyuvi_kw):
    srv,port,host,own = _server_target(srv, port, jupyuvi_kw.get('host'), reuse, public)
    if srv:
        if not await is_serving_a(srv): raise RuntimeError(f"Server on port {srv.port} is not serving")
        return srv,own
    if host is not None: jupyuvi_kw['host'] = host
    srv = JupyUviAsync(app if app is not None else mk_app(_app_kw(app_kw, public)), port=port, **jupyuvi_kw)
    await srv.start()
    return srv,own

def _ensure_server(srv=None, port:int|None=None, app=None, app_kw=None, reuse=True, public=False, **jupyuvi_kw):
    srv,port,host,own = _server_target(srv, port, jupyuvi_kw.get('host'), reuse, public)
    if srv:
        if not is_serving(srv): raise RuntimeError(f"Server on port {srv.port} is not serving")
        return srv,own
    if host is not None: jupyuvi_kw['host'] = host
    srv = JupyUvi(app if app is not None else mk_app(_app_kw(app_kw, public)), port=port, **jupyuvi_kw)
    return srv,own

# %% ../nbs/02_server.ipynb #d34f1855
_mod_nm_re = re.compile(r'[A-Za-z_][A-Za-z0-9_-]*\Z')
def _check_mod_nm(nm):
    if not isinstance(nm, str) or not _mod_nm_re.fullmatch(nm): raise ValueError(f"Invalid ES module name: {nm!r}")
    return nm

__mods__ = {}
def reg_mod(
    nm:str, # Kernel-global registry key
    src:str, # JavaScript module source served for this key
    v:int|None=None, # Version suffix; when given, the module is served under `<nm>_<v>`
) -> None:
    "Register or replace JavaScript source; entries persist in this kernel across app and server lifetimes."
    __mods__[_check_mod_nm(nm)+(f"_{v}" if v>0 else '')] = src
def _get_mod(
    nm:str, # Base module name from the request route
    v:int=0, # Requested version; resolves `<nm>_<v>` before the base name
    debugger:bool=False, # Prefix existing module source with `debugger;`
):
    "Return registered JavaScript as an HTTP response, or a diagnostic module when missing."
    src = __mods__.get(f'{nm}_{v}', __mods__.get(nm))
    if src is None: src,debugger = f'console.log("[{nm}] ES module version `{v}` not found");',False
    return Response(('debugger;\n' if debugger else '')+src, media_type='text/javascript')

# %% ../nbs/02_server.ipynb #07301fb2
def _bool_q(o): return str(o).lower() in ('1','true','yes','on')

async def esm_endpoint(req):
    pp = req.path_params
    try: nm = _check_mod_nm(pp['nm'])
    except ValueError as e: return Response(str(e), status_code=400)
    res = _get_mod(nm, int(req.query_params.get('v', 0)), _bool_q(req.query_params.get('debugger', False)))
    res.headers['Access-Control-Allow-Origin'] = '*'
    return res

# %% ../nbs/02_server.ipynb #93a7b679
esm_routes = (Route('/esm/{nm}', esm_endpoint), )

# %% ../nbs/02_server.ipynb #210adfc1
def add_esm_routes(app):
    paths = {r.path for r in app.routes}
    for r in esm_routes:
        if r.path not in paths: app.routes.append(r)
    return app

# %% ../nbs/02_server.ipynb #9f76a759
def setup_loader(
    app:FastHTML|None=None, # App receiving the ESM routes once; omit to register source without modifying an app
    mods:dict[str,str]|None=None, # Module names and sources added to the kernel-global registry
) -> None:
    "Idempotently install `/esm/{nm}` on `app` and register or replace kernel-global module sources."
    if app is not None: add_esm_routes(app)
    for nm,mod in (mods or {}).items(): reg_mod(nm,mod)

# %% ../nbs/02_server.ipynb #9c15e03a
def mk_app(app_kw=None):
    "Create default FastHTML app"
    if app_kw is None: app_kw = dict(hdrs=daisyui_hdrs)
    return add_esm_routes(FastHTML(**(app_kw or {})))

# %% ../nbs/02_server.ipynb #4738712d
async def ensure_server_a(
    srv:JupyUvi|None=None, # Explicit live server; its app and port win over all creation options
    port:int|None=None, # Port used for discovery or creation; ignored when `srv` is explicit; `None` chooses a free non-public port
    app:FastHTML|None=None, # FastHTML app used only to create a server; ignored when reusing one
    mods:dict[str,str]|None=None, # Sources registered and ESM route installed after server selection, including reuse
    app_kw:dict|None=None, # Keywords for creating the default FastHTML app only; ignored when reusing one
    host:str='127.0.0.1', # loopback by default
    public=False, # set True to enforce a public port if `srv` is not given
    **jupyuvi_kw, # Additional `JupyUviAsync` options used only when creating a server; ignored when reusing one
) -> tuple[JupyUvi,FastHTML,Callable|None,Callable|None]:
    "Return persistent `(srv, app, rt, p)` state, selecting explicit `srv`, matching `port`, then a new server; reuse ignores creation options but still installs `mods`."
    srv,_ = await _ensure_server_a(srv=srv, port=port, app=app, app_kw=app_kw, reuse=True, public=public, host=host, **jupyuvi_kw)
    setup_loader(srv.app, mods)
    return (*srv_bundle(srv),)

def ensure_server(
    srv:JupyUvi|None=None, # Explicit live server; its app and port win over all creation options
    port:int|None=None, # Port used for discovery or creation; ignored when `srv` is explicit; `None` chooses a free non-public port
    app:FastHTML|None=None, # FastHTML app used only to create a server; ignored when reusing one
    mods:dict[str,str]|None=None, # Sources registered and ESM route installed after server selection, including reuse
    app_kw:dict|None=None, # Keywords for creating the default FastHTML app only; ignored when reusing one
    host:str='127.0.0.1', # loopback by default
    public=False, # set True to enforce a public port if `srv` is not given
    **jupyuvi_kw, # Additional `JupyUvi` options used only when creating a server; ignored when reusing one
) -> tuple[JupyUvi,FastHTML,Callable|None,Callable|None]:
    "Return persistent `(srv, app, rt, p)` state, selecting explicit `srv`, matching `port`, then a new server; reuse ignores creation options but still installs `mods`."
    srv,_ = _ensure_server(srv=srv, port=port, app=app, app_kw=app_kw, reuse=True, public=public, host=host, **jupyuvi_kw)
    setup_loader(srv.app, mods)
    return (*srv_bundle(srv),)

# %% ../nbs/02_server.ipynb #3e47ca82
def log(msg, *args, **kwargs): print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)

# %% ../nbs/02_server.ipynb #f95cf689
class LoggerHandler(logging.Handler):
    def __init__(self, log): self.log = log; super().__init__()
    def emit(self, record):
        try: self.log(f"{(record.levelname+':'):<10}{self.format(record)}")
        except Exception: self.handleError(record)

# %% ../nbs/02_server.ipynb #deed061f
def setup_uvi_logging(
    _log:Callable[[str],object]|None=None, # Callable receiving formatted log lines; defaults to this module's `log`
    level:int=logging.INFO, # Level assigned to the uvicorn, uvicorn.error, and uvicorn.access loggers
) -> Callable[[],None]:
    "Route uvicorn logs to `_log`; return caller-owned cleanup and use `log_config=None` to preserve the setup."
    _log = log if _log is None else _log
    _lh = LoggerHandler(_log)
    names = ('uvicorn', 'uvicorn.error', 'uvicorn.access')
    prev = {}
    for name in names:
        lg = logging.getLogger(name)
        prev[name] = lg.handlers[:],lg.propagate,lg.level,lg.disabled
        lg.handlers,lg.propagate,lg.disabled = [_lh],False,False
        lg.setLevel(level)
    def cleanup():
        for name,(handlers,propagate,level,disabled) in prev.items():
            lg = logging.getLogger(name)
            lg.handlers,lg.propagate,lg.disabled = handlers,propagate,disabled
            lg.setLevel(level)
    return cleanup

# %% ../nbs/02_server.ipynb #50b6c46a
@asynccontextmanager
async def serve_app(
    app:FastHTML|None=None, # FastHTML app to serve; if omitted, create one with `app_kw`
    port:int|None=None, # Port to serve on; `None` chooses a free non-public port
    srv:JupyUvi|None=None, # Explicit live server; reused and never owned by this context
    reuse:bool=True, # Reuse a live server discovered on `port`; otherwise raise if one exists
    after_start:Callable[[JupyUvi],object]|None=None, # Sync or async callback after setup; failure triggers owned-server cleanup
    before_stop:Callable[[JupyUvi],object]|None=None, # Sync or async callback during cleanup, before owned-server shutdown
    restore_routes:bool=True, # Restore the initial route list only for a server created by this context
    timeout:float=5, # Seconds to wait for an owned server's port to become free
    mods:dict[str,str]|None=None, # Sources registered in the kernel-global ESM registry
    app_kw:dict|None=None, # Keywords used only when creating the default FastHTML app
    public=False, # Set True to enforce a public port if `srv` is not given
    **jupyuvi_kw, # Additional `JupyUviAsync` options used only when creating a server
) -> AsyncIterator[JupyUvi]:
    "Yield a live server in a temporary notebook namespace scope; stop and optionally restore routes only when this context created it."
    from unittest.mock import patch as mock_patch
    ns = get_ipython().user_ns
    with mock_patch.dict(ns, {}):
        srv,own = await _ensure_server_a(srv=srv, port=port, app=app, app_kw=app_kw, reuse=reuse, public=public, **jupyuvi_kw)
        routes = list(srv.app.routes) if own and restore_routes and hasattr(srv.app, 'routes') else None
        primary = None
        try:
            setup_loader(srv.app, mods)
            if after_start: await maybe_await(after_start(srv))
            yield srv
        except BaseException as e:
            primary = e
            raise
        finally:
            errs = []
            try:
                if own and before_stop: await maybe_await(before_stop(srv))
            except BaseException as e: errs.append(e)
            try:
                if routes is not None: srv.app.routes[:] = routes
            except BaseException as e: errs.append(e)
            try:
                if own:
                    srv.server.should_exit = True
                    deadline = (loop := asyncio.get_running_loop()).time() + timeout
                    while not is_port_free(srv.port, srv.host):
                        if loop.time() > deadline: raise TimeoutError(f"Port {srv.host}:{srv.port} still in use after {timeout}s")
                        await asyncio.sleep(0.1)
            except BaseException as e: errs.append(e)
            if errs:
                if primary is None:
                    if len(errs) == 1: raise errs[0]
                    raise BaseExceptionGroup("serve_app cleanup failures", errs)
                for e in errs: primary.add_note(f"serve_app cleanup failed: {type(e).__name__}: {e}")

# %% ../nbs/02_server.ipynb #2f03e0c6
@asynccontextmanager
async def serve_app(
    app:FastHTML|None=None, # App to serve; omit to create a default app
    port:int|None=None, # Exact port to bind; omit to select a free private/public port
    after_start:Callable[[JupyUvi],object]|None=None, # Sync or async callback after server startup
    before_stop:Callable[[JupyUvi],object]|None=None, # Sync or async callback before server shutdown
    mods:dict[str,str]|None=None, # JavaScript module sources registered for the app
    app_kw:dict|None=None, # Keywords used only when creating the default app
    public:bool=False, # Select a public port and public server binding
    **jupyuvi_kw, # Additional options passed when creating `JupyUviAsync`
) -> AsyncIterator[JupyUvi]:
    "Yield a newly created server in a temporary notebook namespace scope, then stop it."
    if port is None:
        host = '0.0.0.0' if public else '127.0.0.1'
        port = free_port(public=True, host=host) if public else free_port(6551, skip=pub_ports(), host=host)
    public = public or port in pub_ports()
    host = '0.0.0.0' if public else '127.0.0.1'
    if not is_port_free(port, host): raise RuntimeError(f"Port {port} is already in use")
    with mock_patch.dict(get_ipython().user_ns, {}):
        srv,app,_,_ = await ensure_server_a(
            app=app, port=port, mods=mods, app_kw=app_kw, public=public, **jupyuvi_kw
        )
        try:
            if after_start: await maybe_await(after_start(srv))
            yield srv
        finally:
            try:
                if before_stop: await maybe_await(before_stop(srv))
            finally: await srv.stop()

# %% ../nbs/02_server.ipynb #905790cf
async def get_js(
    id:str|None=None, # JavaScript message id; defaults to the preceding message
    dname:str='', # Optional dialog name containing the message
) -> str|None:
    "Strip the leading `%%js` or `%%javascript` line from a dialog message and return its remaining source."
    fl,_,src = (await read_msg(n=0 if id else -1, id=id, dname=dname)).content.partition('\n')
    if fl.lower() not in ('%%javascript', '%%js'): return None
    return src

# %% ../nbs/02_server.ipynb #71238f94
def _py_assign(nm:str, src:str):
    "Return a Python assignment that round-trips `src`; reject invalid variable names."
    if not nm.isidentifier() or keyword.iskeyword(nm): raise ValueError(f"Invalid Python identifier: {nm!r}")
    return f'{nm} = {src!r}'

# %% ../nbs/02_server.ipynb #dbc9dcd5
@delegates(link_msg, but='content,msg_type')
async def add_js_msg(
    nm:str, # Valid Python identifier assigned to safely serialized source; invalid names raise `ValueError`
    id:str=None, # JavaScript source message; defaults to the preceding message and does not change the linkage anchor
    dname:str='', # Dialog to get info for; the linked code message is created in the current dialog
    **kwargs, # Delegated `link_msg` placement, execution, and display options; output is always a code message
) -> str:
    "Extract JavaScript from a dialog message and create or update a linked Python code message containing a safely serialized assignment."
    if (src := await get_js(id, dname)) is not None:
        return await link_msg(_py_assign(nm, src), msg_type='code', **kwargs)
    raise ValueError(f"Message #{id or (await read_msg()).id} does not contain Javascript source")

# %% ../nbs/02_server.ipynb #673eba95
async def load_mod(
    nm:str, # Route-safe module name previously registered with `reg_mod`
    v:int|None=None, # Numeric version selecting registered `<nm>_<v>` before falling back to `<nm>`
    dname:str='', # Dialog owning the module; will be appended as query param if present
) -> object:
    "Import `/esm/<nm>` in the active Solveit browser; return URL and module result. Need at least one public port free."
    _check_mod_nm(nm)
    async with serve_app(public=True) as srv:
        q = (*filter(None, (f"v={v}" if v is not None else '', f"dlg_name={quote(dname.lstrip('/'), safe='')}" if dname else '')),)  
        base = '' if srv.port == 8000 else f"https://{pub_domain(srv.port)}"
        url = f'{base}/esm/{nm}' + ('?' if q else '') + '&'.join(q)
        return url, await js_eval_a(f"return await import({json.dumps(url)})")

# %% ../nbs/02_server.ipynb #648e4add
async def load_mod(
    nm:str, # Route-safe module name previously registered with `reg_mod`
    v:int|None=None, # Numeric version selecting registered `<nm>_<v>` before falling back to `<nm>`
    dname:str='', # Dialog owning the module; will be appended as query param if present
) -> object:
    "Import a registered ES module in the active Solveit browser and return the url and its exports (as JSON)."
    _check_mod_nm(nm)
    async with serve_app(public=True) as srv:
        q = (*filter(None, (f"v={v}" if v is not None else '', f"dlg_name={quote(dname.lstrip('/'), safe='')}" if dname else '')),)
        base = '' if srv.port == 8000 else f"https://{pub_domain(srv.port)}"
        url = f'{base}/esm/{nm}' + ('?' if q else '') + '&'.join(q)
        res = await js_eval_a(f'''try {{ return await import({json.dumps(url)}) }} catch (e) {{ return {{__load_mod_error__: `${{e.name}}: ${{e.message}}`}} }}''')
    if err := res['result'].get('__load_mod_error__'): raise RuntimeError(err)
    return url, res

# %% ../nbs/02_server.ipynb #8a4f6aea
@delegates(serve_app)
async def setup_mod(
    nm:str, # Stable base ESM name
    src:str|None=None, # JavaScript source; defaults to the preceding JS message
    versioned:bool=False, # Use a kernel-local counter for `<nm>_<version>` and `?v=<version>` to bypass browser cache
    dname:str='', # Dialog owning the module; will be appended as query param if present
    **kwargs
) -> tuple[str,object]:
    "Register stable or versioned JavaScript, import it, and return `(registered_name, browser_result)`."
    _check_mod_nm(nm)
    if src is None: src = await get_js()
    if src is None: raise ValueError(f"Message #{(await read_msg()).id} does not contain Javascript source")
    v = kntr(nm) if versioned else None
    nmv = f'{nm}_{v}' if v is not None else nm
    reg_mod(nmv, src)
    return nmv, await load_mod(nm, v, dname=dname, **kwargs)
