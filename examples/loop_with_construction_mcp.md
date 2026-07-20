# Closing the loop: a construction MCP + pdverify

pdverify only *verifies* — it never builds patches. That's deliberate: its input
is a `.pd` file, which every Pd construction tool can already produce, so it
composes with any of them. This is a worked example of pairing it with a real
construction MCP server ([jfboisvenue/pd-mcp-server](https://github.com/jfboisvenue/pd-mcp-server))
to run a **build → hear → fix** loop, with pdverify's measurements driving the fix.

The construction server builds patches over Pd's FUDI protocol and exports a
standalone `.pd` via its `pd_export_pd` tool. pdverify renders and analyzes that
file. The agent (or a script) reads pdverify's report and issues corrective
construction calls. Neither tool knows about the other; the `.pd` file is the
only contract.

## The three things this demonstrates

### 1. Happy path — build and confirm

The MCP builds `osc~ 440 → *~ 0.2 → dac~`, exports `sine_a440.pd`, and pdverify
confirms it:

```
PASS - score 1.00
  A warm pure tone, pitched near A4.
```

### 2. Closed fix loop — pdverify's numbers drive the correction

The MCP builds it *wrong* (`osc~ 220`). pdverify hears the mistake and says how
to fix it:

```
FAIL - score 0.00
  - note: got 220.0 Hz (A3), expected 440.0 Hz (A4): -1200 cents (~an octave down)
          -> scale the oscillator frequency by 2.000 (e.g. [osc~ 440])
```

The driver reads the measured/target frequencies straight off the report,
computes the ratio (440 / 220 = 2.0), and rebuilds via the MCP at the corrected
frequency:

```
pdverify says: measured 219.96 Hz, want 440.0 Hz
-> applying correction: rebuild osc~ at 220 x 2.000 = 440
re-verify: PASS - score 1.00
  A warm pure tone, pitched near A4.
```

That is the whole point: a construction tool that was previously *blind* now has
a perception-and-feedback loop, and it converges.

### 3. An instrument — construction + control injection

The MCP builds a MIDI synth (`notein → mtof → osc~ → *~ → dac~`). On its own it
makes no note; pdverify plays it a C4 and confirms:

```
un-played: A dark, sub-heavy tone with no single clear pitch.
played C4: PASS - score 1.00
  A gently moving, warm pure tone, pitched near C4.
```

## The pattern, in code

```python
# build via the construction MCP (tool calls over stdio) ...
osc = await create(session, "osc~", ["440"])
amp = await create(session, "*~", ["0.2"])
dac = await create(session, "dac~")
await connect(session, osc, 0, amp, 0)
await connect(session, amp, 0, dac, 0); await connect(session, amp, 0, dac, 1)
path = await export(session, "build.pd")          # pd_export_pd -> standalone .pd

# ... then verify with pdverify (no shared state; just the file)
from pdverify import verify, expect
card = verify(path, [expect.not_silent(), expect.no_clipping(), expect.note("A4")])
if not card.passed:
    print(card.feedback())                        # actionable, e.g. "scale frequency by 2.0"
```

A complete, runnable driver (spawning the MCP server, running all three
scenarios) lives in this repo's sibling workspace at `integration/driver.py`.

## Running it yourself

1. Install the construction server (`git clone` + `uv sync`), and open its
   `pd/mcp_host.pd` in Pd so it listens on `netreceive 3000`. (For an automated
   run, launch it headless: `pd -nogui -noaudio -open pd/mcp_host.pd`.)
2. Have pdverify installed with `mcp` available in the same environment.
3. Run the driver.

For native use inside an MCP client (Claude Code / Desktop), register the server
per its README; pdverify sits alongside it as the verification half of the loop.
