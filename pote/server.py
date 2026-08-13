"""Start, reuse, inspect, preview, and stop FastHTML servers in Jupyter or Solveit; register browser ES modules, including versioned modules for iterative development.

### Choosing a helper

```python
from pote.server import ensure_server_a, serve_app, setup_mod, add_js_msg
```

- `await ensure_server_a(...)` starts or reuses a persistent FastHTML server and returns `(srv, app, rt, p)`.
- `async with serve_app(...)` is for a scoped server that is stopped automatically, particularly in tests.
- `find_server`, `is_serving_a`, and `stop_server_a` inspect and clean up existing server state.
- `free_port(public=True)` returns first available public port.
- `p(path)` previews a route in an iframe.
- `setup_mod(..., versioned=True)` supports iterative browser ES-module work.
- `get_js`, `add_js_msg`, and `setup_mod` without `src` extract JavaScript from a `%%js`/`%%javascript` message.

The async APIs are normally preferable in Solveit and Jupyter. These helpers target FastHTML applications; the underlying `JupyUvi` can serve more general ASGI applications, but `pote.server` does not promise that compatibility.

### Persistent server

```python
srv,app,rt,p = await ensure_server_a(port=None)

@rt
def hello(): return 'hello'

p('/hello') # or

display(P(hx_get='/hello', hx_trigger='load once'))

await stop_server_a(srv.port)
```

`ensure_server_a` returns persistent notebook state as `(srv, app, rt, p)`:

- `srv` controls the uvicorn lifecycle.
- `app` is the application actually being served.
- `rt` is its FastHTML route decorator.
- `p` previews routes through the returned server.

Selection precedence is:

1. An explicit live `srv`.
2. A live `JupyUvi` already bound to the requested port.
3. A newly created server.

When an explicit or discovered server is reused, `app`, `app_kw`, and `jupyuvi_kw` are ignored. For an explicit `srv`, its own port is authoritative and the requested `port` is ignored. `mods` are still registered, and the ESM route is installed on the reused app. `port=None` selects a free port outside Solveit’s public-port allocation.

The server remains live until explicitly stopped. In notebooks, prefer `await stop_server_a(srv.port)`, which supports synchronous and asynchronous servers and clears all namespace aliases to the stopped server.

### Temporary server and testing

Use `serve_app` when a server should exist only for a block:

```python
async with serve_app(port=None) as srv:
    @srv.app.get('/hello')
    def hello(): return 'hello'

    cli = TestClient(srv.app)
    test_eq(cli.get('/hello').text, 'hello')
```

A server created by the context is owned by it: cleanup runs after normal exit, setup or body errors, and cancellation. By default, routes added to an owned app during the block are removed on exit.

A reused server is not owned by the context. It remains live afterward, and route changes made to it persist.

The context yields only the live server; use `srv.app`, `srv.port`, and other server attributes inside the block. In tests, `port=None` avoids persistent and publicly allocated ports.

`TestClient(srv.app)` tests the ASGI application directly and does not prove that uvicorn is reachable over the network. Use `await is_serving_a(srv)` when network availability is part of the contract.

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

`setup_mod` and `load_mod` import through a given or discovered server in the active Solveit browser. If no live server is found and the requested port is free, a temporary server is created for the import and stopped afterward. If the port is occupied by a non-discoverable process, setup fails rather than replacing it.

JavaScript can also come from a dialog message whose complete first line is `%%js` or `%%javascript`:

- `get_js` returns the source without the magic line.
- `setup_mod` without `src` extracts and imports the preceding JavaScript message.
- `add_js_msg` creates linked Python state containing the extracted source.

A missing registry entry is served as a valid diagnostic JavaScript module rather than an HTTP error, so an import may succeed without providing the expected exports.

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

Docs: https://civvic.github.io/pote/server.html.md"""

# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02_server.ipynb.

# %% auto #0
__all__ = ['wrap_endp', 'find_server', 'pub_ports', 'free_port', 'free_public_domain', 'is_serving', 'is_serving_a',
           'stop_server', 'stop_server_a', 'reg_mod', 'setup_loader', 'ensure_server', 'ensure_server_a',
           'setup_uvi_logging', 'serve_app', 'get_js', 'add_js_msg', 'load_mod', 'setup_mod']

# %% ../nbs/02_server.ipynb #92031bb1
import asyncio, inspect, json, keyword, logging, os, subprocess
from contextlib import asynccontextmanager
from collections.abc import Callable, AsyncIterator
from datetime import datetime
from functools import partial
from urllib.parse import quote
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

# %% ../nbs/02_server.ipynb #fd28a288
def connect_host(host): return '127.0.0.1' if host in ('0.0.0.0', '::') else host

# %% ../nbs/02_server.ipynb #f3930f80
def wrap_endp(
    response, # Existing request handler or fixed response value
) -> Callable:
    "Return callable handlers unchanged; otherwise return an async handler that returns `response` unchanged."
    if callable(response) and not isinstance(response, FT) and not hasattr(response, '__ft__'): return response
    async def endpoint(request): return response
    return endpoint

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

# %% ../nbs/02_server.ipynb #cf7b0350
def pub_ports() -> tuple[int]:
    "Public ports reserved by this Solveit instance."
    return tuple(sorted(map(int, json.loads(os.environ.get('PUBLIC_DOMAINS', '{}')))))

# %% ../nbs/02_server.ipynb #e16f4192
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

# %% ../nbs/02_server.ipynb #9e454db9
def free_public_domain():
    "Public domain for the first public port that is currently free."
    return json.loads(os.environ["PUBLIC_DOMAINS"])[str(free_port(public=True))]

# %% ../nbs/02_server.ipynb #33099713
def is_serving(srv:JupyUvi|None, timeout=1) -> bool:
    "Return whether `srv` appears started and `GET /` completes with a status below 500."
    if not (srv and srv.server and srv.server.started and not srv.server.should_exit and not is_port_free(srv.port, srv.host)): return False
    try:
        import httpx
        return httpx.get(f"http://{connect_host(srv.host)}:{srv.port}/", timeout=timeout).status_code < 500
    except Exception: return False

async def is_serving_a(srv:JupyUvi|None, timeout=1) -> bool:
    "Return whether `srv` appears started and `GET /` completes with a status below 500."
    if not (srv and srv.server and srv.server.started and not srv.server.should_exit and not is_port_free(srv.port, srv.host)): return False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as cli: return (await cli.get(f"http://{connect_host(srv.host)}:{srv.port}/")).status_code < 500
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

# %% ../nbs/02_server.ipynb #0a15ddb1
def stop_server(port:int|None=None) -> None:
    "Stop the discovered synchronous server and clear every namespace alias to it; do nothing if unmatched and raise for `JupyUviAsync`."
    srv,_ = find_server(port)
    if not srv: return
    if inspect.iscoroutinefunction(srv.stop): raise RuntimeError("JupyUviAsync requires `await stop_server_a(port)`")
    if is_serving(srv): srv.stop()
    for k,v in list(get_ipython().user_ns.items()):
        if v is srv: set_var(k, None)

async def stop_server_a(port:int|None=None) -> None:
    "Stop a discovered synchronous or asynchronous server and clear every namespace alias to it; do nothing if unmatched."
    srv,_ = find_server(port)
    if not srv: return
    if await is_serving_a(srv): await maybe_await(srv.stop())
    for k,v in list(get_ipython().user_ns.items()):
        if v is srv: set_var(k, None)

# %% ../nbs/02_server.ipynb #ae9ce702
def get_preview(app, port=8000, host=None):
    "Return a function that displays the app in an iframe."
    if host is None: host = None if port==8000 else json.loads(os.environ['PUBLIC_DOMAINS']).get(f'{port}', '127.0.0.1')
    return partial(HTMX, app=app, port=port if port in (8000, None) else 443, host=host)

def srv_bundle(srv):
    if hasattr(srv.app, 'route'): return srv,srv.app,srv.app.route,get_preview(srv.app, srv.port)
    else: return srv,srv.app,None,None

def _server_target(srv=None, port:int|None=None, reuse=True, host='127.0.0.1'):
    own = False
    if srv: return srv,port,own
    if port is None: port = free_port(6551, skip=pub_ports(), host=host)
    found,_ = find_server(port)
    if found:
        if not reuse: raise RuntimeError(f"Server already running on port {port}")
        return found,port,own
    if not is_port_free(port): raise RuntimeError(f"Port {port} in use but no JupyUvi instance found in namespace")
    return None,port,True

def _ensure_server(srv=None, port:int|None=None, app=None, app_kw=None, reuse=True, **jupyuvi_kw):
    srv,port,own = _server_target(srv, port, reuse, jupyuvi_kw.get('host', '127.0.0.1'))
    if srv:
        if not is_serving(srv): raise RuntimeError(f"Server on port {srv.port} is not serving")
        return srv, own
    srv = JupyUvi(app if app is not None else mk_app(app_kw), port=port, **jupyuvi_kw)
    return srv, own

async def _ensure_server_a(srv=None, port:int|None=None, app=None, app_kw=None, reuse=True, **jupyuvi_kw):
    srv,port,own = _server_target(srv, port, reuse, jupyuvi_kw.get('host', '127.0.0.1'))
    if srv:
        if not await is_serving_a(srv): raise RuntimeError(f"Server on port {srv.port} is not serving")
        return srv, own
    srv = JupyUviAsync(app if app is not None else mk_app(app_kw), port=port, **jupyuvi_kw)
    await srv.start()
    return srv, own

# %% ../nbs/02_server.ipynb #d34f1855
__mods__ = {}
def reg_mod(
    nm:str, # Kernel-global registry key; versioned entries use `<nm>_<version>`
    src:str, # JavaScript module source served for this key
) -> None:
    "Register or replace JavaScript source; entries persist in this kernel across app and server lifetimes."
    __mods__[nm] = src
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
    return _get_mod(pp['nm'], int(req.query_params.get('v', 0)), _bool_q(req.query_params.get('debugger', False)))

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
def ensure_server(
    srv:JupyUvi|None=None, # Explicit live server; its app and port win over all creation options
    port:int|None=8000, # Port used for discovery or creation; ignored when `srv` is explicit; `None` chooses a free non-public port
    app:FastHTML|None=None, # FastHTML app used only to create a server; ignored when reusing one
    mods:dict[str,str]|None=None, # Sources registered and ESM route installed after server selection, including reuse
    app_kw:dict|None=None, # Keywords for creating the default FastHTML app only; ignored when reusing one
    host:str='127.0.0.1', # loopback by default
    **jupyuvi_kw, # Additional `JupyUvi` options used only when creating a server; ignored when reusing one
) -> tuple[JupyUvi,FastHTML,Callable|None,Callable|None]: # asdf
    "Return persistent `(srv, app, rt, p)` state, selecting explicit `srv`, matching `port`, then a new server; reuse ignores creation options but still installs `mods`."
    srv,_ = _ensure_server(srv=srv, port=port, app=app, app_kw=app_kw, reuse=True, host=host, **jupyuvi_kw)
    setup_loader(srv.app, mods)
    return (*srv_bundle(srv),)

async def ensure_server_a(
    srv:JupyUvi|None=None, # Explicit live server; its app and port win over all creation options
    port:int|None=8000, # Port used for discovery or creation; ignored when `srv` is explicit; `None` chooses a free non-public port
    app:FastHTML|None=None, # FastHTML app used only to create a server; ignored when reusing one
    mods:dict[str,str]|None=None, # Sources registered and ESM route installed after server selection, including reuse
    app_kw:dict|None=None, # Keywords for creating the default FastHTML app only; ignored when reusing one
    host:str='127.0.0.1', # loopback by default
    **jupyuvi_kw, # Additional `JupyUviAsync` options used only when creating a server; ignored when reusing one
) -> tuple[JupyUvi,FastHTML,Callable|None,Callable|None]: # asdf
    "Return persistent `(srv, app, rt, p)` state, selecting explicit `srv`, matching `port`, then a new server; reuse ignores creation options but still installs `mods`."
    srv,_ = await _ensure_server_a(srv=srv, port=port, app=app, app_kw=app_kw, reuse=True, host=host, **jupyuvi_kw)
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

# %% ../nbs/02_server.ipynb #085b35d6
@asynccontextmanager
async def serve_app(
    app:FastHTML|None=None, # FastHTML app to serve; if omitted, create one with `app_kw`
    port:int|None=8000, # Port to serve on; `None` chooses a free non-public port
    srv:JupyUvi|None=None, # Explicit live server; reused and never owned by this context
    reuse:bool=True, # Reuse a live server discovered on `port`; otherwise raise if one exists
    after_start:Callable[[JupyUvi],object]|None=None, # Sync or async callback after setup; failure triggers owned-server cleanup
    before_stop:Callable[[JupyUvi],object]|None=None, # Sync or async callback during cleanup, before owned-server shutdown
    restore_routes:bool=True, # Restore the initial route list only for a server created by this context
    timeout:float=5, # Seconds to wait for an owned server's port to become free
    mods:dict[str,str]|None=None, # Sources registered in the kernel-global ESM registry
    app_kw:dict|None=None, # Keywords used only when creating the default FastHTML app
    **jupyuvi_kw, # Additional `JupyUviAsync` options used only when creating a server
) -> AsyncIterator[JupyUvi]:
    "Async context manager yielding a live server; stop and optionally restore routes only when this context created it."
    srv,own = await _ensure_server_a(srv=srv, port=port, app=app, app_kw=app_kw, reuse=reuse, **jupyuvi_kw)
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

# %% ../nbs/02_server.ipynb #acbc1689
@delegates(serve_app)
async def load_mod(
    nm:str, # Route-safe module name previously registered with `reg_mod`
    v:int|None=None, # Numeric version selecting registered `<nm>_<v>` before falling back to `<nm>`,
    dname:str='', # Dialog owning the module; will be appended as query param if present
    **kwargs
) -> object:
    "Ensure the server, import `/esm/<nm>` in the active Solveit browser, then release any temporary server; browser and registry state persist."
    # url = f"{ifnone(url, f'/esm/{nm}')}{'?v='+str(v) if v is not None else ''}"
    q = filter(None, (f"v={v}" if v is not None else '', f"dlg_name={quote(dname.lstrip('/'), safe='')}" if dname else ''))
    url = f'/esm/{nm}' + ('?' if q else '') + '&'.join(q)
    async with serve_app(**kwargs) as _: return await js_eval_a(f"return await import({json.dumps(url)})")

# %% ../nbs/02_server.ipynb #8a4f6aea
@delegates(serve_app)
async def setup_mod(
    nm:str, # Stable base ESM name
    src:str|None=None, # JavaScript source; defaults to the preceding JS message
    versioned:bool=False, # Use a kernel-local counter for `<nm>_<version>` and `?v=<version>` to bypass browser cache
    dname:str='', # Dialog owning the module; will be appended as query param if present
    **kwargs
) -> tuple[str,object]:
    "Register stable or versioned JavaScript, import it through ensured server, and return `(registered_name, browser_result)`."
    if src is None: src = await get_js()
    if src is None: raise ValueError(f"Message #{(await read_msg()).id} does not contain Javascript source")
    nmv = f"{nm}{'_'+str(v) if (v := str(kntr(nm)) if versioned else None) else ''}"
    reg_mod(nmv, src)
    return nmv, await load_mod(nm, v, dname=dname, **kwargs)
