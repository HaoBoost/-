# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Single-file Python Tkinter Pomodoro timer (`pomodoro.py`). Runs on Windows with toast notifications via PowerShell.

## Running

```bash
python pomodoro.py
# Or double-click 启动番茄钟.bat
```

Delete `__pycache__/` after code changes to ensure Python recompiles from source.

## Architecture

`pomodoro.py` — single `PomodoroApp` class (~590 lines) plus a `PillButton` helper (custom rounded Canvas button).

**State variables** (set in `__init__`):
- `mode`: `"work"`, `"short_break"`, or `"long_break"`
- `remaining`: seconds left in current phase
- `running`: whether the tick loop is active
- `delay_remaining`: buffer seconds between phases (0 = instant switch)
- `pomodoro_count`: completed pomodoros (incremented when work phase ends)

**Tick loop** — `_tick()` runs every 1000ms via `root.after()`. The loop never stops on timeout; instead the `else` branch (remaining == 0) switches mode in-place and continues:

```
remaining > 0 → decrement, update display, schedule next tick
remaining == 0 → increment pomodoro if work, _switch_mode(), notify, decrement once for new phase, update display, schedule next tick
```

**Key methods**:
- `_switch_mode(delay=0)` — changes mode, resets `remaining` and `delay_remaining`, updates display and button states. Does NOT start/stop the tick loop.
- `start()` — sets `running = True`, calls `_tick()` directly (immediate first decrement).
- `pause()` — sets `running = False`, cancels `_after_id`.
- `skip()` — cancels pending tick, calls `_switch_mode(delay=0)`, sets `running = True`, schedules next tick via `after(1000, _tick)`.

**Color dictionary** — `C` dict keys for mode colors are `"work"`, `"short_break"`, `"long_break"` (matching `self.mode` values). Used via `C[self.mode]` in `_update_display()`.

**Config** — saved as `pomodoro_config.json`: `work`, `short`, `long` (minutes), `before` (pomodoros before long break).

**Notifications** — `_toast()` uses `subprocess.Popen` (non-blocking) to run a PowerShell Windows toast. Must stay non-blocking; `subprocess.run` freezes the Tkinter event loop.
