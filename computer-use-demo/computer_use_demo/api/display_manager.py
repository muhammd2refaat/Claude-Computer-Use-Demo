"""Dynamic virtual display and VNC allocation for concurrent sessions.

Each session gets its own Xvfb display and x11vnc instance, enabling
truly parallel computer use sessions without any hardcoded limits.
"""

import asyncio
import logging
import os
import signal
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Starting points for dynamic allocation
_BASE_DISPLAY_NUM = 100
_BASE_VNC_PORT = 5810
_BASE_WS_PORT = 5910

# Screen dimensions from environment (or defaults)
SCREEN_WIDTH = int(os.getenv("WIDTH", "1024"))
SCREEN_HEIGHT = int(os.getenv("HEIGHT", "768"))


@dataclass
class DisplayAllocation:
    """Tracks a single display allocation with its processes."""
    display_num: int
    vnc_port: int
    ws_port: int
    xvfb_pid: int | None = None
    x11vnc_pid: int | None = None
    websockify_pid: int | None = None


class DisplayManager:
    """Manages dynamic allocation and cleanup of virtual displays and VNC servers.

    Thread-safe via asyncio.Lock. Dynamically spawns Xvfb and x11vnc for each
    new session, and cleans up on session end.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._allocations: dict[int, DisplayAllocation] = {}
        self._next_display = _BASE_DISPLAY_NUM
        self._used_vnc_ports: set[int] = set()
        self._used_ws_ports: set[int] = set()

    def _next_vnc_port(self) -> int:
        """Find the next available VNC port."""
        port = _BASE_VNC_PORT
        while port in self._used_vnc_ports:
            port += 1
        return port

    def _next_ws_port(self) -> int:
        """Find the next available WebSocket port."""
        port = _BASE_WS_PORT
        while port in self._used_ws_ports:
            port += 1
        return port

    async def allocate_display(self) -> DisplayAllocation:
        """Allocate a new virtual display and VNC server.

        Returns a DisplayAllocation with display_num, vnc_port, and ws_port.
        Raises RuntimeError if display fails to start.
        """
        async with self._lock:
            display_num = self._next_display
            self._next_display += 1

            vnc_port = self._next_vnc_port()
            self._used_vnc_ports.add(vnc_port)

            ws_port = self._next_ws_port()
            self._used_ws_ports.add(ws_port)

        allocation = DisplayAllocation(
            display_num=display_num,
            vnc_port=vnc_port,
            ws_port=ws_port,
        )

        try:
            await self._start_xvfb(allocation)
            await self._start_x11vnc(allocation)
            await self._start_websockify(allocation)
        except Exception:
            await self.release_display(display_num)
            raise

        async with self._lock:
            self._allocations[display_num] = allocation

        logger.info(
            f"Allocated display :{display_num} with VNC on port {vnc_port} -> WS on port {ws_port}"
        )
        return allocation

    async def release_display(self, display_num: int) -> None:
        """Release a display allocation, killing its processes."""
        async with self._lock:
            allocation = self._allocations.pop(display_num, None)
            if allocation:
                self._used_vnc_ports.discard(allocation.vnc_port)
                self._used_ws_ports.discard(allocation.ws_port)

        if not allocation:
            return

        # Kill websockify
        if allocation.websockify_pid:
            try:
                os.kill(allocation.websockify_pid, signal.SIGTERM)
                logger.info(f"Killed websockify (pid={allocation.websockify_pid})")
            except ProcessLookupError:
                pass

        # Kill x11vnc
        if allocation.x11vnc_pid:
            try:
                os.kill(allocation.x11vnc_pid, signal.SIGTERM)
                logger.info(f"Killed x11vnc (pid={allocation.x11vnc_pid})")
            except ProcessLookupError:
                pass

        # Kill Xvfb
        if allocation.xvfb_pid:
            try:
                os.kill(allocation.xvfb_pid, signal.SIGTERM)
                logger.info(f"Killed Xvfb (pid={allocation.xvfb_pid})")
            except ProcessLookupError:
                pass

        # Clean up X lock file
        lock_file = f"/tmp/.X{display_num}-lock"
        try:
            os.remove(lock_file)
        except FileNotFoundError:
            pass

        logger.info(f"Released display :{display_num}")

    async def release_all(self) -> None:
        """Release all display allocations. Used during shutdown."""
        async with self._lock:
            display_nums = list(self._allocations.keys())

        for display_num in display_nums:
            await self.release_display(display_num)

    def get_allocation(self, display_num: int) -> DisplayAllocation | None:
        """Get allocation info for a display number."""
        return self._allocations.get(display_num)

    @property
    def active_count(self) -> int:
        """Number of currently active displays."""
        return len(self._allocations)

    # --- Private Process Management ---

    async def _start_xvfb(self, allocation: DisplayAllocation) -> None:
        """Start an Xvfb instance for the given allocation."""
        display_num = allocation.display_num
        res = f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}x24"

        proc = await asyncio.create_subprocess_exec(
            "Xvfb", f":{display_num}",
            "-ac",
            "-screen", "0", res,
            "-retro",
            "-dpi", "96",
            "-nolisten", "tcp",
            "-nolisten", "unix",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        allocation.xvfb_pid = proc.pid

        # Wait for Xvfb to be ready
        for _ in range(50):
            await asyncio.sleep(0.2)
            if os.path.exists(f"/tmp/.X{display_num}-lock"):
                break
        else:
            raise RuntimeError(f"Xvfb failed to start on display :{display_num}")

        logger.info(f"Xvfb started on :{display_num} (pid={proc.pid})")

    async def _start_x11vnc(self, allocation: DisplayAllocation) -> None:
        """Start an x11vnc instance for the given allocation."""
        display_num = allocation.display_num
        vnc_port = allocation.vnc_port

        proc = await asyncio.create_subprocess_exec(
            "x11vnc",
            "-display", f":{display_num}",
            "-forever",
            "-shared",
            "-wait", "50",
            "-rfbport", str(vnc_port),
            "-nopw",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        allocation.x11vnc_pid = proc.pid

        # Wait for VNC server to be ready (check port)
        for _ in range(20):
            await asyncio.sleep(0.5)
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", vnc_port)
                writer.close()
                await writer.wait_closed()
                break
            except (ConnectionRefusedError, OSError):
                continue
        else:
            raise RuntimeError(
                f"x11vnc failed to start on port {vnc_port} for display :{display_num}"
            )

        logger.info(f"x11vnc started on port {vnc_port} (pid={proc.pid})")

    async def _start_websockify(self, allocation: DisplayAllocation) -> None:
        """Start a websockify proxy for the VNC server."""
        display_num = allocation.display_num
        vnc_port = allocation.vnc_port
        ws_port = allocation.ws_port

        proc = await asyncio.create_subprocess_exec(
            "/opt/noVNC/utils/novnc_proxy",
            "--vnc", f"localhost:{vnc_port}",
            "--listen", str(ws_port),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        allocation.websockify_pid = proc.pid

        # Wait for websockify to be ready
        for _ in range(20):
            await asyncio.sleep(0.5)
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", ws_port)
                writer.close()
                await writer.wait_closed()
                break
            except (ConnectionRefusedError, OSError):
                continue
        else:
            raise RuntimeError(
                f"websockify failed to start on port {ws_port} for display :{display_num}"
            )

        logger.info(f"websockify started on port {ws_port} (pid={proc.pid})")

# Global singleton instance
display_manager = DisplayManager()
