"""
Resource monitoring for localization approaches.

Captures:
  - Wall-clock latency (ms)                  — already tracked by localisers
  - Peak RSS memory (MB)                      — process memory before vs after
  - Average CPU% during the call              — sampled every 0.2 s
  - GPU utilisation                           — always N/A (no GPU dependency added)

Usage:
  result, metrics = run_with_resources(fn, *args, **kwargs)

The metrics dict is safe to attach directly to an approach_done SSE payload or
to LocalizationResult (as the new `resource_usage` field).

DESIGN CONSTRAINTS:
  - Does NOT modify the return value of fn.
  - Does NOT raise exceptions if psutil is unavailable (graceful degradation).
  - Does NOT block the event loop — intended to be called from a thread executor,
    same as the existing LLM/embedding calls.
  - CPU sampling uses a background thread so the measurement interval covers
    the actual call, not just the Python thread that launched it.
"""
from __future__ import annotations
import logging
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

try:
    import psutil as _psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _psutil = None        # type: ignore[assignment]
    _PSUTIL_AVAILABLE = False
    logger.warning("psutil not available — resource monitoring disabled")


def _unavailable() -> dict:
    return {
        "cpu_avg_percent":   None,
        "cpu_peak_percent":  None,
        "memory_rss_mb_start": None,
        "memory_rss_mb_peak":  None,
        "memory_delta_mb":   None,
        "gpu_utilization":   "N/A – no GPU monitoring dependency installed",
        "measurement_note":  "psutil not available",
    }


def run_with_resources(fn: Callable, *args, **kwargs) -> tuple[Any, dict]:
    """
    Call fn(*args, **kwargs) and return (result, resource_metrics).

    resource_metrics keys:
      cpu_avg_percent     float | None   — average CPU% of this process during the call
      cpu_peak_percent    float | None   — peak CPU% sample
      memory_rss_mb_start float | None   — resident set size before call (MB)
      memory_rss_mb_peak  float | None   — peak RSS observed during call (MB)
      memory_delta_mb     float | None   — peak − start (MB used by this call)
      gpu_utilization     str            — always "N/A – ..."
      measurement_note    str            — description of methodology
    """
    if not _PSUTIL_AVAILABLE:
        result = fn(*args, **kwargs)
        return result, _unavailable()

    proc = _psutil.Process()

    # Baseline
    try:
        mem_start = proc.memory_info().rss / (1024 * 1024)
    except Exception:
        mem_start = None

    cpu_samples: list[float] = []
    mem_samples: list[float] = [mem_start] if mem_start is not None else []
    stop_flag   = threading.Event()

    def _sampler():
        """Sample CPU and memory every 200 ms until stop_flag is set."""
        while not stop_flag.is_set():
            try:
                cpu_samples.append(proc.cpu_percent(interval=None))
                mem_samples.append(proc.memory_info().rss / (1024 * 1024))
            except Exception:
                pass
            stop_flag.wait(timeout=0.2)

    # Warm up cpu_percent (first call always returns 0.0)
    try:
        proc.cpu_percent(interval=None)
    except Exception:
        pass

    sampler_thread = threading.Thread(target=_sampler, daemon=True)
    sampler_thread.start()

    try:
        result = fn(*args, **kwargs)
    finally:
        stop_flag.set()
        sampler_thread.join(timeout=1.0)

        if not cpu_samples:
            try:
                cpu_samples.append(proc.cpu_percent(interval=0.1))
            except Exception:
                pass
        try:
            mem_samples.append(proc.memory_info().rss / (1024 * 1024))
        except Exception:
            pass

    # Aggregate
    cpu_avg  = round(sum(cpu_samples) / len(cpu_samples), 1) if cpu_samples else None
    cpu_peak = round(max(cpu_samples), 1)                     if cpu_samples else None
    mem_peak = round(max(mem_samples), 1)                     if mem_samples else None
    mem_delta = round(mem_peak - mem_start, 1) if (mem_peak is not None and mem_start is not None) else None

    metrics = {
        "cpu_avg_percent":    cpu_avg,
        "cpu_peak_percent":   cpu_peak,
        "memory_rss_mb_start": round(mem_start, 1) if mem_start is not None else None,
        "memory_rss_mb_peak":  mem_peak,
        "memory_delta_mb":     mem_delta,
        "gpu_utilization":    "N/A – no GPU monitoring dependency installed",
        "measurement_note":   (
            "CPU sampled every 200 ms (process-level). "
            "Memory = peak RSS during call. "
            "GPU not monitored."
        ),
    }
    return result, metrics
