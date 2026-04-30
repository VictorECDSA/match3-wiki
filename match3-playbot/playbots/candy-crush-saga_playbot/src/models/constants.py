# Screen state constants (mirrors ui_detector)
MAP      = "map"
PRE_PLAY = "pre_play"
PLAYING  = "playing"
COMPLETE = "complete"
FAILED   = "failed"
UNKNOWN  = "unknown"

# Action type constants
ACT_TAP    = "tap"     # tap a single (x, y)
ACT_SWAP   = "swap"    # swap two adjacent cells (r1,c1) <-> (r2,c2)
ACT_WAIT   = "wait"    # do nothing this cycle
ACT_LAUNCH = "launch"  # re-launch / bring game to foreground
