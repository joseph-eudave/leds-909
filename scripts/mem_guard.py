#!/usr/bin/env python3
"""mem_guard — watch TouchDesigner's committed memory; kill it before OOM.

Run alongside the show:  python scripts/mem_guard.py [limit_gb]

Every 5 s it samples TouchDesigner.exe's commit (pagefile-backed virtual
memory, the counter that exhausted the system before the 2026-11-21 crash)
and logs to %TEMP%/leds909_mem_watch.log. If the commit grows monotonically
at an exponential-ish rate (doubling within the window) or crosses the
limit (default 12 GB), TD is terminated so Windows and the rest of the show
PC stay alive.

Exit codes: 0 = TD closed normally, 1 = TD killed by guard, 2 = never saw TD.
"""
import sys
import time

try:
    import psutil
except ImportError:
    print("psutil required: pip install psutil")
    sys.exit(2)

LIMIT_GB = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0
SAMPLE_S = 5.0
WINDOW = 12          # samples (~1 min): used for the doubling test
LOG = None


def log(line):
    print(line, flush=True)
    if LOG:
        with open(LOG, "a") as f:
            f.write(line + "\n")


def main():
    global LOG
    import os
    import tempfile
    LOG = os.path.join(tempfile.gettempdir(), "leds909_mem_watch.log")
    log("mem_guard start: limit=%.1f GB window=%d samples" % (LIMIT_GB, WINDOW))
    seen = False
    hist = []  # (t, gb)
    while True:
        procs = [p for p in psutil.process_iter(["name"]) if p.info["name"] and p.info["name"].lower() == "touchdesigner.exe"]
        if not procs:
            if seen:
                log("mem_guard: TD exited on its own")
                return 0
            time.sleep(SAMPLE_S)
            continue
        seen = True
        try:
            commit = sum(p.memory_info().vms for p in procs) / 2**30
        except psutil.Error:
            time.sleep(SAMPLE_S)
            continue
        now = time.time()
        hist = [(t, g) for t, g in hist if now - t <= WINDOW * SAMPLE_S] + [(now, commit)]
        log("commit %.2f GB (%d samples)" % (commit, len(hist)))
        kill = None
        if commit > LIMIT_GB:
            kill = "commit %.2f GB over limit %.1f GB" % (commit, LIMIT_GB)
        elif len(hist) >= 6:
            old_t, old_g = hist[0]
            if old_g > 0.3 and commit > 2.0 * old_g:
                kill = "commit doubled %.2f -> %.2f GB in ~%ds" % (old_g, commit, now - old_t)
        if kill:
            log("mem_guard: KILLING TD: " + kill)
            for p in procs:
                try:
                    p.kill()
                except psutil.Error:
                    pass
            return 1
        time.sleep(SAMPLE_S)


if __name__ == "__main__":
    sys.exit(main())
