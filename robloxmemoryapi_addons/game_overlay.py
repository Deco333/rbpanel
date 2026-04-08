"""
game_overlay.py — Transparent Win32 overlay module for ESP / prediction data.

Creates a borderless, click-through, topmost window that draws GDI primitives
over the Roblox game window at up to 240 FPS.  Uses double-buffered rendering
with per-frame BitBlt and colour-key transparency (black = transparent).

Typical usage
-------------
>>> overlay = GameOverlay(target_fps=240)
>>> overlay.create()
>>> overlay.start()
>>> overlay.update([
...     {"type": "circle", "x": 500, "y": 300, "r": 5,
...      "color": (0, 200, 255), "filled": True},
...     {"type": "text", "x": 500, "y": 288,
...      "text": "Player1 [50m]", "color": (255, 255, 255), "font_size": 12},
... ])
>>> # ... later ...
>>> overlay.stop()
>>> overlay.destroy()
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import logging
import threading
import time
from typing import List, Optional, Tuple, Dict, Any

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Win32 constants
# ---------------------------------------------------------------------------
# Window styles
WS_POPUP       = 0x80000000
WS_VISIBLE     = 0x10000000

# Extended window styles
WS_EX_LAYERED      = 0x00080000
WS_EX_TOPMOST      = 0x00000008
WS_EX_TRANSPARENT  = 0x00000020
WS_EX_TOOLWINDOW   = 0x00000080
WS_EX_NOACTIVATE   = 0x08000000

# Layered-window attributes
LWA_COLORKEY = 0x00000001
LWA_ALPHA    = 0x00000002

# Window messages
WM_DESTROY = 0x0002
WM_PAINT   = 0x000F

# Stock objects
NULL_BRUSH = 5
BLACK_PEN  = 7

# GDI raster ops
SRCCOPY = 0x00CC0020
BLACKONWHITE = 1

# GDI background mode
TRANSPARENT = 1
OPAQUE      = 2

# Pen styles
PS_SOLID      = 0
PS_DASH       = 1
PS_DOT        = 2
PS_DASHDOT    = 3
PS_DASHDOTDOT = 4

# Font weight
FW_NORMAL  = 400
FW_BOLD    = 700
FW_LIGHT   = 300

# ---------------------------------------------------------------------------
# Win32 API bindings (lazy-loaded via windll)
# ---------------------------------------------------------------------------
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# ---------------------------------------------------------------------------
# Win32 structures
# ---------------------------------------------------------------------------

# Python 3.12+ removed several types from ctypes.wintypes — define fallbacks
_WINTYPES_COMPAT = {
    "HCURSOR": ctypes.c_void_p,
    "LRESULT": ctypes.c_long,
    "HBRUSH":  ctypes.c_void_p,
    "HICON":   ctypes.c_void_p,
    "HMENU":   ctypes.c_void_p,
    "HGDIOBJ": ctypes.c_void_p,
    "HINSTANCE": ctypes.c_void_p,
    "HMODULE": ctypes.c_void_p,
    "ATOM":    ctypes.c_ushort,
}
for _name, _ctype in _WINTYPES_COMPAT.items():
    if not hasattr(wintypes, _name):
        setattr(wintypes, _name, _ctype)

class WNDCLASSEXW(ctypes.Structure):
    """WNDCLASSEXW — used to register the overlay window class."""
    _fields_ = [
        ("cbSize",        wintypes.UINT),
        ("style",         wintypes.UINT),
        ("lpfnWndProc",   ctypes.c_void_p),
        ("cbClsExtra",    ctypes.c_int),
        ("cbWndExtra",    ctypes.c_int),
        ("hInstance",     wintypes.HINSTANCE),
        ("hIcon",         wintypes.HICON),
        ("hCursor",       wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm",       wintypes.HICON),
    ]


class BLENDFUNCTION(ctypes.Structure):
    """BLENDFUNCTION for UpdateLayeredWindow (unused but kept for reference)."""
    _fields_ = [
        ("BlendOp",             ctypes.c_ubyte),
        ("BlendFlags",          ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat",         ctypes.c_ubyte),
    ]


class MSG(ctypes.Structure):
    """MSG structure for the message pump."""
    _fields_ = [
        ("hwnd",   wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam",  wintypes.WPARAM),
        ("lParam",  wintypes.LPARAM),
        ("time",    wintypes.DWORD),
        ("pt",      wintypes.POINT),
    ]


class RECT(ctypes.Structure):
    """RECT — rectangle defined by left, top, right, bottom."""
    _fields_ = [
        ("left",   ctypes.c_long),
        ("top",    ctypes.c_long),
        ("right",  ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class POINT(ctypes.Structure):
    """POINT — 2-D coordinate."""
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]

# ---------------------------------------------------------------------------
# WNDPROC callback type
# ---------------------------------------------------------------------------
WNDPROC_TYPE = ctypes.WINFUNCTYPE(
    wintypes.LRESULT,  # return
    wintypes.HWND,     # hwnd
    wintypes.UINT,     # uMsg
    wintypes.WPARAM,   # wParam
    wintypes.LPARAM,   # lParam
)


# ---------------------------------------------------------------------------
# Helper: RGB macro → COLORREF (BGR layout)
# ---------------------------------------------------------------------------
def _rgb(r: int, g: int, b: int) -> int:
    """Convert (R, G, B) 0-255 → Win32 COLORREF (DWORD, BGR byte order)."""
    return (b << 16) | (g << 8) | r


def _color_tuple_to_colorref(color: Tuple[int, int, int]) -> int:
    """Convert an (R, G, B) tuple to a Win32 COLORREF."""
    r, g, b = color[0] & 0xFF, color[1] & 0xFF, color[2] & 0xFF
    return _rgb(r, g, b)


# ---------------------------------------------------------------------------
# Overlay window class name (must be unique per process)
# ---------------------------------------------------------------------------
_OVERLAY_CLASS_NAME = "GameOverlayClass_v1"
_OVERLAY_WINDOW_TITLE = "GameOverlay"


# ===========================================================================
# GameOverlay
# ===========================================================================
class GameOverlay:
    """Transparent, click-through, topmost Win32 overlay for drawing ESP data.

    The overlay uses colour-key transparency: every black pixel is fully
    transparent, all other colours are visible.  Drawing is done with GDI on
    a memory DC (double-buffered) and BitBlt'd to the window DC each frame.

    Parameters
    ----------
    target_fps : int
        Desired render frame rate (default 240).
    show_fps : bool
        If True, render an FPS counter in the top-left corner.
    track_roblox : bool
        If True, automatically find and follow the Roblox window.
    """

    def __init__(self, target_fps: int = 240, show_fps: bool = False,
                 track_roblox: bool = True) -> None:
        self._target_fps: int = max(1, min(1000, target_fps))
        self._show_fps: bool = show_fps
        self._track_roblox: bool = track_roblox

        # Window handles
        self._hwnd: int = 0
        self._roblox_hwnd: int = 0
        self._h_instance: int = kernel32.GetModuleHandleW(None)

        # Double-buffering
        self._hdc_mem: int = 0
        self._hbitmap: int = 0
        self._hbitmap_old: int = 0

        # GDI object caches
        self._brush_cache: Dict[int, int] = {}       # colorref → HBRUSH
        self._pen_cache: Dict[Tuple[int, int], int] = {}  # (colorref, width) → HPEN
        self._dash_pen_cache: Dict[Tuple[int, int], int] = {}
        self._font_cache: Dict[int, int] = {}        # font_size → HFONT
        self._hdc_window: int = 0

        # Thread control
        self._render_thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._created: bool = False

        # Data (protected by lock)
        self._lock = threading.Lock()
        self._draw_items: List[Dict[str, Any]] = []

        # FPS measurement
        self._frame_count: int = 0
        self._fps: float = 0.0
        self._fps_timer: float = time.perf_counter()

        # Roblox tracking timer
        self._roblox_track_interval: float = 0.5  # seconds
        self._last_track_time: float = 0.0

        # Window size cache
        self._width: int = 0
        self._height: int = 0

        # WNDPROC (must hold a reference to prevent GC)
        self._wndproc: Optional[WNDPROC_TYPE] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self) -> bool:
        """Register the window class and create the overlay window.

        Returns True on success, False otherwise.
        """
        if self._created:
            log.warning("Overlay already created.")
            return True

        try:
            self._register_class()
            self._hwnd = self._create_window()
            if not self._hwnd:
                log.error("Failed to create overlay window.")
                return False

            self._setup_transparency()
            self._hdc_window = user32.GetDC(self._hwnd)
            if not self._hdc_window:
                log.error("Failed to get window DC.")
                user32.DestroyWindow(self._hwnd)
                self._hwnd = 0
                return False

            self._init_double_buffer()
            self._cache_initial_gdi_objects()

            if self._track_roblox:
                self._find_roblox_window()

            self._created = True
            log.info("Overlay window created successfully (hwnd=0x%X).", self._hwnd)
            return True

        except Exception as exc:
            log.error("Error creating overlay: %s", exc, exc_info=True)
            self._created = False
            return False

    def destroy(self) -> None:
        """Clean up all Win32 resources (GDI objects, window, class)."""
        self.stop()

        # Release double-buffer objects
        self._cleanup_double_buffer()

        # Release window DC
        if self._hdc_window:
            user32.ReleaseDC(self._hwnd, self._hdc_window)
            self._hdc_window = 0

        # Destroy window
        if self._hwnd:
            user32.DestroyWindow(self._hwnd)
            log.info("Overlay window destroyed (hwnd=0x%X).", self._hwnd)
            self._hwnd = 0

        # Unregister class
        user32.UnregisterClassW(_OVERLAY_CLASS_NAME, self._h_instance)

        # Clean GDI caches
        self._cleanup_gdi_cache()

        self._created = False

    def start(self) -> None:
        """Start the render thread."""
        if self._running:
            log.warning("Render thread already running.")
            return
        if not self._created:
            log.error("Cannot start — overlay not created. Call create() first.")
            return

        self._running = True
        self._render_thread = threading.Thread(
            target=self._render_loop,
            name="OverlayRender",
            daemon=True,
        )
        self._render_thread.start()
        log.info("Render thread started (target %d FPS).", self._target_fps)

    def stop(self) -> None:
        """Signal the render thread to stop and wait for it to join."""
        if not self._running:
            return

        self._running = False
        if self._render_thread is not None:
            self._render_thread.join(timeout=2.0)
            if self._render_thread.is_alive():
                log.warning("Render thread did not stop within 2 seconds.")
            self._render_thread = None
        log.info("Render thread stopped.")

    def update(self, items: List[Dict[str, Any]]) -> None:
        """Thread-safe update of the draw-item list.

        Parameters
        ----------
        items : list[dict]
            A list of draw-command dictionaries.  Each dict must contain a
            ``"type"`` key with one of: circle, line, dashed_line, text,
            crosshair, box, arrow.
        """
        with self._lock:
            self._draw_items = list(items)

    def set_fps(self, fps: int) -> None:
        """Change the target frame rate at runtime.

        Parameters
        ----------
        fps : int
            New target FPS (clamped to 1-1000).
        """
        self._target_fps = max(1, min(1000, fps))
        log.debug("Target FPS changed to %d.", self._target_fps)

    def set_roblox_hwnd(self, hwnd: int) -> None:
        """Manually set the Roblox window handle.

        Parameters
        ----------
        hwnd : int
            Win32 HWND of the Roblox window.
        """
        self._roblox_hwnd = hwnd
        log.info("Roblox HWND manually set to 0x%X.", hwnd)

    def is_running(self) -> bool:
        """Return True if the render thread is currently active."""
        return self._running

    # ------------------------------------------------------------------
    # Static: World-to-Screen
    # ------------------------------------------------------------------

    @staticmethod
    def w2s(world_x: float, world_y: float, world_z: float,
            view_matrix: List[float], screen_w: int,
            screen_h: int) -> Optional[Tuple[float, float]]:
        """Convert a 3-D world position to 2-D screen coordinates.

        Performs a standard perspective divide against a 4×4 view-projection
        matrix in **row-major** order.

        Parameters
        ----------
        world_x, world_y, world_z : float
            World-space position (in studs).
        view_matrix : list[float]
            16 floats representing a 4×4 row-major matrix.
        screen_w, screen_h : int
            Viewport dimensions in pixels.

        Returns
        -------
        tuple[float, float] | None
            ``(screen_x, screen_y)`` or ``None`` if the point is behind
            the camera (clip_w < 0.1).
        """
        wx, wy, wz = world_x, world_y, world_z
        m = view_matrix

        clip_x = wx * m[0] + wy * m[4] + wz * m[8]  + m[12]
        clip_y = wx * m[1] + wy * m[5] + wz * m[9]  + m[13]
        clip_w = wx * m[3] + wy * m[7] + wz * m[11] + m[15]

        if clip_w < 0.1:
            return None

        ndc_x = clip_x / clip_w
        ndc_y = clip_y / clip_w

        screen_x = (screen_w * 0.5) * (1.0 + ndc_x)
        screen_y = (screen_h * 0.5) * (1.0 - ndc_y)
        return (screen_x, screen_y)

    # ------------------------------------------------------------------
    # Internal: Window class registration
    # ------------------------------------------------------------------

    def _register_class(self) -> None:
        """Register the WNDCLASSEXW for the overlay window."""
        self._wndproc = WNDPROC_TYPE(self._static_wndproc)

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = 0  # CS_HREDRAW | CS_VREDRAW not needed — we redraw manually
        wc.lpfnWndProc = ctypes.cast(self._wndproc, ctypes.c_void_p)
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = self._h_instance
        wc.hIcon = 0
        wc.hCursor = 0
        wc.hbrBackground = gdi32.GetStockObject(NULL_BRUSH)
        wc.lpszClassName = _OVERLAY_CLASS_NAME
        wc.hIconSm = 0

        if not user32.RegisterClassExW(ctypes.byref(wc)):
            err = ctypes.get_last_error()
            if err != 1410:  # ERROR_CLASS_ALREADY_EXISTS
                raise ctypes.WinError(err)

    def _static_wndproc(self, hwnd: int, msg: int, wparam: int,
                        lparam: int) -> int:
        """Minimal window procedure — defers everything to DefWindowProcW."""
        if msg == WM_DESTROY:
            self._running = False
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # ------------------------------------------------------------------
    # Internal: Window creation
    # ------------------------------------------------------------------

    def _create_window(self) -> int:
        """Create the overlay window and return its HWND (0 on failure)."""
        # Default size if Roblox not found
        rect = RECT()
        if self._roblox_hwnd:
            user32.GetWindowRect(self._roblox_hwnd, ctypes.byref(rect))
        else:
            # Use primary monitor work area
            user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)

        w = max(rect.right - rect.left, 100)
        h = max(rect.bottom - rect.top, 100)
        self._width = w
        self._height = h

        ex_style = (WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TRANSPARENT
                    | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        style = WS_POPUP | WS_VISIBLE

        hwnd = user32.CreateWindowExW(
            ex_style,
            _OVERLAY_CLASS_NAME,
            _OVERLAY_WINDOW_TITLE,
            style,
            rect.left, rect.top,
            w, h,
            0, 0, self._h_instance, 0,
        )
        return hwnd or 0

    def _setup_transparency(self) -> None:
        """Configure colour-key transparency: black (0,0,0) is transparent."""
        user32.SetLayeredWindowAttributes(
            self._hwnd,
            0,    # crKey — COLORREF black
            0,    # bAlpha (unused with LWA_COLORKEY alone)
            LWA_COLORKEY,
        )

    # ------------------------------------------------------------------
    # Internal: Double buffering
    # ------------------------------------------------------------------

    def _init_double_buffer(self) -> None:
        """Create a memory DC + compatible bitmap for double-buffered drawing."""
        hdc = self._hdc_window
        self._hdc_mem = gdi32.CreateCompatibleDC(hdc)
        self._hbitmap = gdi32.CreateCompatibleBitmap(hdc, self._width, self._height)
        if self._hbitmap:
            self._hbitmap_old = gdi32.SelectObject(self._hdc_mem, self._hbitmap)
        log.debug("Double buffer initialised (%dx%d).", self._width, self._height)

    def _resize_double_buffer(self, new_w: int, new_h: int) -> None:
        """Recreate the back-buffer at the new dimensions."""
        if new_w == self._width and new_h == self._height:
            return

        self._cleanup_double_buffer()
        self._width = new_w
        self._height = new_h
        self._init_double_buffer()
        log.debug("Double buffer resized to %dx%d.", new_w, new_h)

    def _cleanup_double_buffer(self) -> None:
        """Release the memory DC and bitmap."""
        if self._hdc_mem and self._hbitmap_old:
            gdi32.SelectObject(self._hdc_mem, self._hbitmap_old)
            self._hbitmap_old = 0
        if self._hbitmap:
            gdi32.DeleteObject(self._hbitmap)
            self._hbitmap = 0
        if self._hdc_mem:
            gdi32.DeleteDC(self._hdc_mem)
            self._hdc_mem = 0

    # ------------------------------------------------------------------
    # Internal: GDI object caching
    # ------------------------------------------------------------------

    def _cache_initial_gdi_objects(self) -> None:
        """Pre-create commonly used GDI objects."""
        # Default fonts
        for size in (10, 11, 12, 13, 14, 16, 18, 20, 24):
            self._get_font(size)

        # Default pens
        for width in (1, 2, 3):
            for r, g, b in [(255, 255, 255), (255, 50, 50),
                             (0, 200, 255), (0, 255, 0),
                             (255, 255, 0), (0, 255, 100),
                             (255, 165, 0), (255, 0, 255)]:
                self._get_pen(r, g, b, width)

        log.debug("Initial GDI objects cached.")

    def _get_brush(self, r: int, g: int, b: int) -> int:
        """Return a cached solid brush for the given colour."""
        cref = _rgb(r, g, b)
        if cref not in self._brush_cache:
            self._brush_cache[cref] = gdi32.CreateSolidBrush(cref)
        return self._brush_cache[cref]

    def _get_pen(self, r: int, g: int, b: int, width: int) -> int:
        """Return a cached solid pen."""
        cref = _rgb(r, g, b)
        key = (cref, width)
        if key not in self._pen_cache:
            self._pen_cache[key] = gdi32.CreatePen(PS_SOLID, width, cref)
        return self._pen_cache[key]

    def _get_dash_pen(self, r: int, g: int, b: int, width: int) -> int:
        """Return a cached dashed pen."""
        cref = _rgb(r, g, b)
        key = (cref, width)
        if key not in self._dash_pen_cache:
            self._dash_pen_cache[key] = gdi32.CreatePen(PS_DASH, width, cref)
        return self._dash_pen_cache[key]

    def _get_font(self, font_size: int) -> int:
        """Return a cached font (Consolas, bold).

        ``font_size`` is the desired height in *points*; GDI CreateFontW
        expects the height in *pixels* (negative value = character height).
        We use a fixed mapping: pixels ≈ -font_size.
        """
        if font_size not in self._font_cache:
            height = -font_size
            hfont = gdi32.CreateFontW(
                height,   # nHeight
                0,        # nWidth
                0,        # nEscapement
                0,        # nOrientation
                FW_BOLD,  # fnWeight
                0,        # fdwItalic
                0,        # fdwUnderline
                0,        # fdwStrikeOut
                0,        # fdwCharSet (ANSI)
                0,        # fdwOutputPrecision
                0,        # fdwClipPrecision
                0,        # fdwQuality
                0,        # fdwPitchAndFamily
                "Consolas",
            )
            self._font_cache[font_size] = hfont
        return self._font_cache[font_size]

    def _cleanup_gdi_cache(self) -> None:
        """Delete all cached GDI objects."""
        for hobj in self._brush_cache.values():
            gdi32.DeleteObject(hobj)
        self._brush_cache.clear()

        for hobj in self._pen_cache.values():
            gdi32.DeleteObject(hobj)
        self._pen_cache.clear()

        for hobj in self._dash_pen_cache.values():
            gdi32.DeleteObject(hobj)
        self._dash_pen_cache.clear()

        for hobj in self._font_cache.values():
            gdi32.DeleteObject(hobj)
        self._font_cache.clear()

    # ------------------------------------------------------------------
    # Internal: Roblox window tracking
    # ------------------------------------------------------------------

    def _find_roblox_window(self) -> None:
        """Attempt to locate the Roblox game window by class name or title."""
        # Try by UWP class name first
        hwnd = user32.FindWindowW("Windows10CoreWindow", None)
        if hwnd:
            # Verify it's Roblox by checking the title
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.lower()
                if "roblox" in title:
                    self._roblox_hwnd = hwnd
                    log.info("Found Roblox (UWP): hwnd=0x%X title='%s'", hwnd, buf.value)
                    return

        # Enumerate windows looking for "Roblox" in the title
        self._roblox_hwnd = self._enum_find_roblox()
        if self._roblox_hwnd:
            log.info("Found Roblox (enum): hwnd=0x%X", self._roblox_hwnd)
        else:
            log.warning("Roblox window not found. Overlay will use screen center.")

    def _enum_find_roblox(self) -> int:
        """Use EnumWindows to find a visible window with 'Roblox' in the title."""
        found = [0]

        @WNDPROC_TYPE
        def _enum_callback(hwnd: int, _lparam: int) -> int:
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    if "roblox" in buf.value.lower():
                        found[0] = hwnd
                        return 0  # stop
            return 1  # continue

        # WNDPROC_TYPE casts the callback, but EnumWindows expects a different
        # signature.  Use ctypes directly instead.
        enum_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )
        callback = enum_type(_enum_callback.func)

        # ctypes.byref for the LPARAM is fine (it's not used)
        user32.EnumWindows(callback, 0)
        return found[0]

    def _track_roblox_window(self) -> None:
        """Check Roblox window position/size and reposition overlay."""
        if not self._roblox_hwnd:
            if self._track_roblox:
                self._find_roblox_window()
            return

        # Check if Roblox is still alive
        if not user32.IsWindow(self._roblox_hwnd):
            log.warning("Roblox window closed. Stopping overlay.")
            self._roblox_hwnd = 0
            self._running = False
            return

        rect = RECT()
        user32.GetWindowRect(self._roblox_hwnd, ctypes.byref(rect))

        new_w = max(rect.right - rect.left, 100)
        new_h = max(rect.bottom - rect.top, 100)

        # Reposition overlay
        user32.SetWindowPos(
            self._hwnd, -1,  # HWND_TOPMOST
            rect.left, rect.top, new_w, new_h,
            0x0010 | 0x0004,  # SWP_NOACTIVATE | SWP_NOZORDER
        )

        if new_w != self._width or new_h != self._height:
            self._resize_double_buffer(new_w, new_h)

    # ------------------------------------------------------------------
    # Internal: Render loop
    # ------------------------------------------------------------------

    def _render_loop(self) -> None:
        """Main render loop running on a dedicated thread."""
        frame_time = 1.0 / self._target_fps
        self._last_track_time = time.perf_counter()

        while self._running:
            t_start = time.perf_counter()

            # Track Roblox window periodically
            now = time.perf_counter()
            if now - self._last_track_time >= self._roblox_track_interval:
                self._last_track_time = now
                try:
                    self._track_roblox_window()
                except Exception:
                    pass  # don't let tracking errors kill the loop

            # Render one frame
            try:
                self._render_frame()
            except Exception as exc:
                log.debug("Render frame error: %s", exc)

            # FPS measurement
            self._frame_count += 1
            elapsed_fps = now - self._fps_timer
            if elapsed_fps >= 1.0:
                self._fps = self._frame_count / elapsed_fps
                self._frame_count = 0
                self._fps_timer = now

            # Frame timing — sleep the remainder; skip if we overslept
            t_end = time.perf_counter()
            dt = t_end - t_start
            sleep_time = frame_time - dt
            if sleep_time > 0.001:
                time.sleep(sleep_time)
            # If sleep_time <= 0, frame took too long → just continue (no lag accumulation)

    def _render_frame(self) -> None:
        """Clear the back-buffer, draw all items, and BitBlt to screen."""
        hdc_mem = self._hdc_mem
        if not hdc_mem or not self._hdc_window:
            return

        # 1. Clear entire buffer to black (transparent via colour-key)
        rect = RECT(0, 0, self._width, self._height)
        black_brush = self._get_brush(0, 0, 0)
        gdi32.FillRect(hdc_mem, ctypes.byref(rect), black_brush)

        # 2. Snapshot draw items under lock (fast copy)
        with self._lock:
            items = list(self._draw_items)

        # 3. Draw each item
        for item in items:
            try:
                self._draw_item(hdc_mem, item)
            except Exception as exc:
                log.debug("Draw error for item %s: %s", item.get("type"), exc)

        # 4. Draw FPS counter
        if self._show_fps:
            self._draw_fps(hdc_mem)

        # 5. Flip: BitBlt from memory DC → window DC
        gdi32.BitBlt(
            self._hdc_window, 0, 0, self._width, self._height,
            hdc_mem, 0, 0, SRCCOPY,
        )

    # ------------------------------------------------------------------
    # Internal: Drawing primitives
    # ------------------------------------------------------------------

    def _draw_item(self, hdc: int, item: Dict[str, Any]) -> None:
        """Dispatch a single draw-command dict to the appropriate primitive."""
        draw_type = item.get("type", "")
        if draw_type == "circle":
            self._draw_circle(hdc, item)
        elif draw_type == "line":
            self._draw_line(hdc, item)
        elif draw_type == "dashed_line":
            self._draw_dashed_line(hdc, item)
        elif draw_type == "text":
            self._draw_text(hdc, item)
        elif draw_type == "crosshair":
            self._draw_crosshair(hdc, item)
        elif draw_type == "box":
            self._draw_box(hdc, item)
        elif draw_type == "arrow":
            self._draw_arrow(hdc, item)
        # else: silently ignore unknown types

    def _draw_circle(self, hdc: int, item: Dict[str, Any]) -> None:
        """Draw a filled or outline circle."""
        x = int(item.get("x", 0))
        y = int(item.get("y", 0))
        r = max(int(item.get("r", 1)), 1)
        color = item.get("color", (255, 255, 255))
        filled = item.get("filled", True)

        cr, cg, cb = color[0] & 0xFF, color[1] & 0xFF, color[2] & 0xFF

        if filled:
            brush = self._get_brush(cr, cg, cb)
            old_brush = gdi32.SelectObject(hdc, brush)
            old_pen = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
            gdi32.Ellipse(hdc, x - r, y - r, x + r, y + r)
            gdi32.SelectObject(hdc, old_pen)
            gdi32.SelectObject(hdc, old_brush)
        else:
            pen = self._get_pen(cr, cg, cb, item.get("width", 1))
            old_pen = gdi32.SelectObject(hdc, pen)
            old_brush = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_BRUSH))
            gdi32.Ellipse(hdc, x - r, y - r, x + r, y + r)
            gdi32.SelectObject(hdc, old_brush)
            gdi32.SelectObject(hdc, old_pen)

    def _draw_line(self, hdc: int, item: Dict[str, Any]) -> None:
        """Draw a solid line."""
        x1 = int(item.get("x1", 0))
        y1 = int(item.get("y1", 0))
        x2 = int(item.get("x2", 0))
        y2 = int(item.get("y2", 0))
        color = item.get("color", (255, 255, 255))
        width = max(int(item.get("width", 1)), 1)

        cr, cg, cb = color[0] & 0xFF, color[1] & 0xFF, color[2] & 0xFF
        pen = self._get_pen(cr, cg, cb, width)
        old_pen = gdi32.SelectObject(hdc, pen)

        gdi32.MoveToEx(hdc, x1, y1, None)
        gdi32.LineTo(hdc, x2, y2)

        gdi32.SelectObject(hdc, old_pen)

    def _draw_dashed_line(self, hdc: int, item: Dict[str, Any]) -> None:
        """Draw a dashed line (for prediction trajectories)."""
        x1 = int(item.get("x1", 0))
        y1 = int(item.get("y1", 0))
        x2 = int(item.get("x2", 0))
        y2 = int(item.get("y2", 0))
        color = item.get("color", (255, 255, 255))
        width = max(int(item.get("width", 1)), 1)

        cr, cg, cb = color[0] & 0xFF, color[1] & 0xFF, color[2] & 0xFF
        pen = self._get_dash_pen(cr, cg, cb, width)
        old_pen = gdi32.SelectObject(hdc, pen)

        gdi32.MoveToEx(hdc, x1, y1, None)
        gdi32.LineTo(hdc, x2, y2)

        gdi32.SelectObject(hdc, old_pen)

    def _draw_text(self, hdc: int, item: Dict[str, Any]) -> None:
        """Draw text with a transparent background."""
        x = int(item.get("x", 0))
        y = int(item.get("y", 0))
        text = str(item.get("text", ""))
        color = item.get("color", (255, 255, 255))
        font_size = max(int(item.get("font_size", 12)), 6)

        cr, cg, cb = color[0] & 0xFF, color[1] & 0xFF, color[2] & 0xFF
        cref = _rgb(cr, cg, cb)

        old_font = gdi32.SelectObject(hdc, self._get_font(font_size))
        old_text_color = gdi32.SetTextColor(hdc, cref)
        old_bk_mode = gdi32.SetBkMode(hdc, TRANSPARENT)

        # Draw text with a thin black outline for readability
        outline_color = 0  # black
        old_color2 = gdi32.SetTextColor(hdc, outline_color)
        for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            gdi32.TextOutW(hdc, x + ox, y + oy, text, len(text))
        gdi32.SetTextColor(hdc, cref)
        gdi32.TextOutW(hdc, x, y, text, len(text))

        gdi32.SetBkMode(hdc, old_bk_mode)
        gdi32.SetTextColor(hdc, old_text_color)
        gdi32.SelectObject(hdc, old_font)

    def _draw_crosshair(self, hdc: int, item: Dict[str, Any]) -> None:
        """Draw an X crosshair mark at the given position."""
        x = int(item.get("x", 0))
        y = int(item.get("y", 0))
        r = max(int(item.get("r", 4)), 1)
        color = item.get("color", (255, 50, 50))
        width = max(int(item.get("width", 2)), 1)

        cr, cg, cb = color[0] & 0xFF, color[1] & 0xFF, color[2] & 0xFF
        pen = self._get_pen(cr, cg, cb, width)
        old_pen = gdi32.SelectObject(hdc, pen)

        # X shape: top-left to bottom-right, top-right to bottom-left
        gdi32.MoveToEx(hdc, x - r, y - r, None)
        gdi32.LineTo(hdc, x + r, y + r)

        gdi32.MoveToEx(hdc, x + r, y - r, None)
        gdi32.LineTo(hdc, x - r, y + r)

        gdi32.SelectObject(hdc, old_pen)

    def _draw_box(self, hdc: int, item: Dict[str, Any]) -> None:
        """Draw a 2-D bounding box (rectangle outline)."""
        x1 = int(item.get("x1", 0))
        y1 = int(item.get("y1", 0))
        x2 = int(item.get("x2", 0))
        y2 = int(item.get("y2", 0))
        color = item.get("color", (0, 255, 0))
        width = max(int(item.get("width", 1)), 1)
        filled = item.get("filled", False)

        cr, cg, cb = color[0] & 0xFF, color[1] & 0xFF, color[2] & 0xFF

        if filled:
            brush = self._get_brush(cr, cg, cb)
            old_brush = gdi32.SelectObject(hdc, brush)
            old_pen = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
            gdi32.Rectangle(hdc, x1, y1, x2, y2)
            gdi32.SelectObject(hdc, old_pen)
            gdi32.SelectObject(hdc, old_brush)
        else:
            pen = self._get_pen(cr, cg, cb, width)
            old_pen = gdi32.SelectObject(hdc, pen)
            old_brush = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_BRUSH))
            gdi32.Rectangle(hdc, x1, y1, x2, y2)
            gdi32.SelectObject(hdc, old_brush)
            gdi32.SelectObject(hdc, old_pen)

    def _draw_arrow(self, hdc: int, item: Dict[str, Any]) -> None:
        """Draw an arrow from (x1,y1) to (x2,y2) with an arrowhead."""
        x1 = int(item.get("x1", 0))
        y1 = int(item.get("y1", 0))
        x2 = int(item.get("x2", 0))
        y2 = int(item.get("y2", 0))
        color = item.get("color", (0, 255, 100))
        width = max(int(item.get("width", 2)), 1)

        cr, cg, cb = color[0] & 0xFF, color[1] & 0xFF, color[2] & 0xFF
        pen = self._get_pen(cr, cg, cb, width)
        old_pen = gdi32.SelectObject(hdc, pen)

        # Draw the shaft
        gdi32.MoveToEx(hdc, x1, y1, None)
        gdi32.LineTo(hdc, x2, y2)

        # Compute arrowhead
        dx = x2 - x1
        dy = y2 - y1
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1.0:
            gdi32.SelectObject(hdc, old_pen)
            return

        # Normalise direction
        ndx = dx / length
        ndy = dy / length

        # Arrowhead size proportional to length, clamped
        head_len = min(max(length * 0.25, 6), 20)
        head_half_width = head_len * 0.5

        # Perpendicular direction
        px = -ndy
        py = ndx

        # Arrowhead tip is at (x2, y2); two base points
        bx1 = x2 - ndx * head_len + px * head_half_width
        by1 = y2 - ndy * head_len + py * head_half_width
        bx2 = x2 - ndx * head_len - px * head_half_width
        by2 = y2 - ndy * head_len - py * head_half_width

        # Draw arrowhead (filled triangle)
        brush = self._get_brush(cr, cg, cb)
        old_brush = gdi32.SelectObject(hdc, brush)
        old_pen2 = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))

        pts = (POINT * 3)(
            POINT(x2, y2),
            POINT(int(bx1), int(by1)),
            POINT(int(bx2), int(by2)),
        )
        gdi32.Polygon(hdc, pts, 3)

        gdi32.SelectObject(hdc, old_pen2)
        gdi32.SelectObject(hdc, old_brush)
        gdi32.SelectObject(hdc, old_pen)

    def _draw_fps(self, hdc: int) -> None:
        """Draw the FPS counter in the top-left corner."""
        text = f"FPS: {self._fps:.0f}"
        x, y = 8, 8
        font_size = 12

        old_font = gdi32.SelectObject(hdc, self._get_font(font_size))
        old_bk_mode = gdi32.SetBkMode(hdc, TRANSPARENT)

        # Black outline for visibility
        old_color = gdi32.SetTextColor(hdc, 0)
        for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            gdi32.TextOutW(hdc, x + ox, y + oy, text, len(text))

        # Green text
        gdi32.SetTextColor(hdc, _rgb(0, 255, 0))
        gdi32.TextOutW(hdc, x, y, text, len(text))

        gdi32.SetTextColor(hdc, old_color)
        gdi32.SetBkMode(hdc, old_bk_mode)
        gdi32.SelectObject(hdc, old_font)

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "GameOverlay":
        self.create()
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
        self.destroy()


# ===========================================================================
# Convenience: quick demo / self-test
# ===========================================================================
def _demo() -> None:
    """Minimal demo that spins up the overlay for 5 seconds with sample data."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    overlay = GameOverlay(target_fps=240, show_fps=True, track_roblox=False)

    if not overlay.create():
        print("ERROR: Failed to create overlay.")
        return

    # Get window dimensions for demo positioning
    w, h = overlay._width, overlay._height

    sample_items = [
        {"type": "circle", "x": w // 2, "y": h // 2, "r": 40,
         "color": (0, 200, 255), "filled": False},
        {"type": "circle", "x": w // 2, "y": h // 2, "r": 5,
         "color": (0, 200, 255), "filled": True},
        {"type": "crosshair", "x": w // 2, "y": h // 2,
         "r": 12, "color": (255, 255, 255), "width": 2},
        {"type": "box", "x1": w // 2 - 50, "y1": h // 2 - 70,
         "x2": w // 2 + 50, "y2": h // 2 + 70,
         "color": (0, 255, 0), "width": 1},
        {"type": "text", "x": w // 2 - 40, "y": h // 2 - 85,
         "text": "Demo Player [32m]", "color": (255, 255, 255), "font_size": 12},
        {"type": "arrow", "x1": w // 2, "y1": h // 2,
         "x2": w // 2 + 80, "y2": h // 2 - 40,
         "color": (0, 255, 100), "width": 2},
        {"type": "dashed_line", "x1": w // 2, "y1": h // 2,
         "x2": w // 2 - 100, "y2": h // 2 + 60,
         "color": (255, 50, 50), "width": 1},
        {"type": "line", "x1": w // 2, "y1": h // 2 + 70,
         "x2": w // 2, "y2": h // 2 + 140,
         "color": (255, 255, 0), "width": 1},
        {"type": "circle", "x": w // 2, "y": h // 2 + 140, "r": 3,
         "color": (255, 255, 0), "filled": True},
    ]

    overlay.update(sample_items)
    overlay.start()

    print("Overlay running for 5 seconds... (close overlay window or wait)")
    time.sleep(5.0)

    overlay.stop()
    overlay.destroy()
    print("Done.")


if __name__ == "__main__":
    _demo()
