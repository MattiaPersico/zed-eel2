"""Curated API hints, not a complete REAPER API or compiler model.

Signatures checked against https://www.reaper.fm/sdk/js/js.php and its reference
pages. Descriptions are deliberately brief; linked reference pages are canonical.
"""

BASE = "https://www.reaper.fm/sdk/js/"
BUILTINS = {}


def add(name, parameters, description, page="basiccode.php", kind=3):
    signature = name + "(" + ", ".join(parameters) + ")" if parameters is not None else name
    BUILTINS[name] = dict(label=name, kind=kind, detail=signature,
                          parameters=parameters, documentation={"kind": "markdown", "value":
                          description + "\n\n[REAPER reference](" + BASE + page + ")"})


for name, text in {
    "sin": "Sine; radians.", "cos": "Cosine; radians.", "tan": "Tangent; radians.",
    "asin": "Inverse sine.", "acos": "Inverse cosine.", "atan": "Inverse tangent.",
    "sqrt": "Square root.", "invsqrt": "Approximate inverse square root.",
    "sqr": "Square.", "exp": "Natural exponential.", "log": "Natural logarithm.",
    "log10": "Base-ten logarithm.", "abs": "Absolute value.", "sign": "Sign.",
    "floor": "Round down.", "ceil": "Round up.", "rand": "Random value scaled by x.",
}.items():
    add(name, ["x"], text)
for name, text in {"min": "Minimum.", "max": "Maximum.", "pow": "Exponentiation.",
                   "atan2": "Angle of x/y, respecting the quadrant."}.items():
    add(name, ["x", "y"], text)
add("loop", ["count", "code"], "Repeat code.")
add("while", ["code"], "Repeat while the result is nonzero; also supports while(condition)(body).")
add("time_precise", [], "High-resolution time in seconds.")
for name, params, text in [
    ("memset", ["destination", "value", "length"], "Fill local memory."),
    ("memcpy", ["destination", "source", "length"], "Copy local memory."),
    ("fft", ["buffer", "size"], "Complex forward FFT; check size and page constraints."),
    ("ifft", ["buffer", "size"], "Complex inverse FFT; normalize as required."),
    ("fft_real", ["buffer", "size"], "Real forward FFT."),
    ("ifft_real", ["buffer", "size"], "Real inverse FFT."),
    ("fft_permute", ["buffer", "size"], "Reorder FFT output."),
    ("fft_ipermute", ["buffer", "size"], "Undo FFT reordering."),
    ("convolve_c", ["destination", "source", "size"], "Multiply complex buffers."),
    ("__memtop", [], "Available local memory size."),
    ("sliderchange", ["slider_or_mask"], "Notify the host of parameter changes."),
    ("slider_automate", ["slider_or_mask", "end_touch_optional"], "Notify automation."),
    ("slider_show", ["slider_or_mask", "visible_optional"], "Query or change parameter visibility."),
    ("atomic_get", ["variable"], "Read atomically."),
    ("atomic_set", ["variable", "value"], "Write atomically."),
    ("atomic_add", ["variable", "value"], "Add atomically."),
]:
    add(name, params, text, "advfunc.php")
for name, params, text in [
    ("midirecv", ["offset", "msg1", "msg23"], "Receive a MIDI event; also has a four-argument form."),
    ("midisend", ["offset", "msg1", "msg23"], "Send MIDI; also has a four-argument form."),
    ("midirecv_buf", ["offset", "buffer", "max_length"], "Receive MIDI into memory."),
    ("midisend_buf", ["offset", "buffer", "length"], "Send MIDI from memory."),
]:
    add(name, params, text, "midi.php")
for name, params, text in [
    ("file_open", ["filename"], "Open a file using REAPER's path rules."),
    ("file_close", ["handle"], "Close a file."),
    ("file_avail", ["handle"], "Query remaining data; negative for writing."),
    ("file_var", ["handle", "variable"], "Read or write a value; handle 0 is project state."),
    ("file_mem", ["handle", "buffer", "length"], "Read or write memory."),
]:
    add(name, params, text, "file.php")
for name, params, text in [
    ("strlen", ["string"], "String length."),
    ("strcpy", ["destination", "source"], "Copy a string."),
    ("strcat", ["destination", "source"], "Append a string."),
    ("strcmp", ["a", "b"], "Compare strings."),
    ("sprintf", ["destination", "format", "..."], "Format into a string."),
    ("match", ["pattern", "string", "..."], "Match a string pattern."),
]:
    add(name, params, text, "strings.php")
for name, params, text in [
    ("gfx_set", ["r", "g_optional", "b_optional", "a_optional", "mode_optional", "dest_optional", "a2_optional"], "Set drawing state."),
    ("gfx_rect", ["x", "y", "width", "height"], "Draw a filled rectangle."),
    ("gfx_line", ["x1", "y1", "x2", "y2", "antialias_optional"], "Draw a line."),
    ("gfx_circle", ["x", "y", "radius", "filled_optional", "antialias_optional"], "Draw a circle."),
    ("gfx_drawstr", ["string", "flags_optional", "right_optional", "bottom_optional"], "Draw text."),
    ("gfx_measurestr", ["string", "width", "height"], "Measure text."),
    ("gfx_setfont", ["index", "face_optional", "size_optional", "flags_optional"], "Select a font."),
    ("gfx_getchar", ["code_optional", "unicodechar_optional"], "Read input or query a key."),
]:
    add(name, params, text, "gfx.php")
for name, text in {
    "srate": "Sample rate in Hz.", "samplesblock": "Frames in the current block.",
    "num_ch": "Available audio channels.", "tempo": "Tempo in BPM.",
    "play_state": "Transport state flags.", "play_position": "Position in seconds.",
    "beat_position": "Position in beats.", "ts_num": "Time signature numerator.",
    "ts_denom": "Time signature denominator.", "pdc_delay": "Reported latency in samples.",
    "pdc_bot_ch": "First latency-compensated channel.", "pdc_top_ch": "End of compensated channel range.",
    "ext_noinit": "Controls transport-triggered initialization.",
    "ext_nodenorm": "Controls denormal-prevention noise.", "ext_tail_size": "Effect tail length.",
    "trigger": "Trigger button bit field.", "midi_bus": "MIDI bus index.",
    "ext_midi_bus": "Enable MIDI bus support.", "gmem": "Shared memory namespace.",
}.items():
    add(name, None, text, "vars.php", 6)
for name in ("gfx_x", "gfx_y", "gfx_w", "gfx_h", "gfx_r", "gfx_g", "gfx_b", "gfx_a",
             "gfx_mode", "gfx_dest", "gfx_texth", "mouse_x", "mouse_y", "mouse_cap", "mouse_wheel"):
    add(name, None, "Graphics/input state.", "gfx.php", 6)
for i in range(64):
    add("spl" + str(i), None, "Audio channel " + str(i) + " sample.", "vars.php", 6)
for name in ("$pi", "$e", "$phi"):
    add(name, None, "Mathematical constant.", kind=21)
SECTIONS = {
    "@init": "Initialization.", "@slider": "Parameter updates.",
    "@block": "Once per audio block.", "@sample": "Once per sample frame.",
    "@serialize": "Load/save extended state.", "@gfx": "Graphics and interaction.",
}
for name, text in SECTIONS.items():
    add(name, None, text, "js.php", 14)
for name in ("function", "local", "instance", "global", "static"):
    add(name, None, "Function declaration or variable scope.", "userfunc.php", 14)
