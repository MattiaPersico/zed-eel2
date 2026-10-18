"""Curated API hints, not a complete REAPER API or compiler model.

Signatures checked against https://www.reaper.fm/sdk/js/js.php and its reference
pages. Descriptions are deliberately brief; linked reference pages are canonical.
"""

BASE = "https://www.reaper.fm/sdk/js/"
BUILTINS = {}
OVERLOADS = {}


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
add("time_precise", ["output_optional"], "High-resolution time in seconds; optionally writes the result to output.")
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

# Additional JSFX APIs checked against the linked official reference pages.
# Parameter names ending in _optional describe optional trailing arguments.
for page, entries in {
    "basiccode.php": [
        ("time", ["output_optional"], "Unix time in seconds; optionally writes the result to output."),
    ],
    "vars.php": [
        ("spl", ["channel_index"], "Read or write a channel sample in @sample."),
        ("slider", ["slider_index"], "Read or write a slider by index."),
        ("slider_next_chg", ["slider_index", "next_value"], "Read the next automation offset and value in @block or @sample."),
    ],
    "advfunc.php": [
        ("mdct", ["buffer", "size"], "Forward MDCT; consult the size and memory-boundary requirements."),
        ("imdct", ["buffer", "size"], "Inverse MDCT."),
        ("freembuf", ["top"], "Hint that local memory above top is no longer needed."),
        ("mem_set_values", ["buffer", "..."], "Write successive values to memory."),
        ("mem_get_values", ["buffer", "..."], "Read successive memory values into output variables."),
        ("mem_multiply_sum", ["buffer1", "buffer2", "length"], "Sum products of memory values; special second-buffer modes are documented."),
        ("mem_insert_shuffle", ["buffer", "length", "value"], "Insert a value while shifting a memory range."),
        ("stack_push", ["value"], "Push onto the user stack."),
        ("stack_pop", ["output_optional"], "Pop from the user stack, optionally into a variable."),
        ("stack_peek", ["index"], "Access a stack entry; zero refers to the top."),
        ("stack_exch", ["value"], "Exchange a variable with the stack top."),
        ("atomic_setifequal", ["destination", "expected", "replacement"], "Compare and replace atomically; return the previous value."),
        ("atomic_exch", ["a", "b"], "Atomically exchange two values."),
        ("get_host_numchan", [], "Get the host channel count."),
        ("set_host_numchan", ["channels"], "Set the host channel count from @gfx."),
        ("get_pin_mapping", ["input_output", "pin", "start_channel", "channel_mask"], "Read pin routing bits."),
        ("set_pin_mapping", ["input_output", "pin", "start_channel", "channel_mask", "mapping"], "Set pin routing from @gfx."),
        ("get_pinmapper_flags", [], "Read pin mapper flags."),
        ("set_pinmapper_flags", ["flags"], "Set pin mapper flags from @gfx."),
        ("get_host_placement", ["chain_position_optional", "flags_optional"], "Get host placement and optional chain position/flags."),
        ("export_buffer_to_project", ["buffer", "length_samples", "channels", "sample_rate", "track_index", "flags_optional", "tempo_optional", "planar_pitch_optional"], "Export audio to the project from @gfx only."),
    ],
    "midi.php": [
        ("midisend_str", ["offset", "string"], "Send MIDI bytes stored in a string."),
        ("midirecv_str", ["offset", "string"], "Receive MIDI bytes into a string."),
        ("midisyx", ["offset", "buffer", "length"], "Legacy SysEx sender; deprecated in favor of midisend_buf."),
    ],
    "file.php": [
        ("file_rewind", ["handle"], "Return a file to its beginning."),
        ("file_riff", ["handle", "channels", "sample_rate"], "Query audio-file format into output variables."),
        ("file_text", ["handle", "is_text"], "Query whether the file uses text format."),
        ("file_string", ["handle", "string"], "Transfer a text line, or a serialized string when handle is zero."),
    ],
    "strings.php": [
        ("stricmp", ["a", "b"], "Compare strings ignoring case."),
        ("strncmp", ["a", "b", "max_length"], "Compare a bounded byte prefix."),
        ("strnicmp", ["a", "b", "max_length"], "Compare a bounded byte prefix ignoring case."),
        ("strncpy", ["destination", "source", "max_length"], "Copy a bounded byte prefix."),
        ("strncat", ["destination", "source", "max_length"], "Append a bounded byte prefix."),
        ("strcpy_from", ["destination", "source", "offset"], "Copy from a byte offset."),
        ("strcpy_substr", ["destination", "source", "offset", "max_length"], "Copy a substring using byte offsets."),
        ("str_getchar", ["string", "offset", "type_optional"], "Read data at a byte offset; type selects its binary format."),
        ("str_setchar", ["string", "offset", "value", "type_optional"], "Write data at a byte offset."),
        ("strcpy_fromslider", ["destination", "slider"], "Get a slider's filename or display string."),
        ("matchi", ["pattern", "string", "..."], "Match a pattern ignoring case."),
    ],
    "gfx.php": [
        ("gfx_lineto", ["x", "y", "antialias_optional"], "Draw from the current graphics position and move it."),
        ("gfx_rectto", ["x", "y"], "Fill a rectangle from the current graphics position."),
        ("gfx_setpixel", ["r", "g", "b"], "Write a pixel at the current graphics position."),
        ("gfx_getpixel", ["r", "g", "b"], "Read a pixel into output variables."),
        ("gfx_drawnumber", ["number", "digits"], "Draw a number with the requested decimal precision."),
        ("gfx_drawchar", ["character"], "Draw a character code."),
        ("gfx_getfont", [], "Get the selected font index."),
        ("gfx_printf", ["format", "..."], "Draw formatted text."),
        ("gfx_blurto", ["x", "y"], "Blur a rectangle from the current graphics position."),
        ("gfx_blit", ["source", "scale", "rotation", "src_x_optional", "src_y_optional", "src_w_optional", "src_h_optional", "dest_x_optional", "dest_y_optional", "dest_w_optional", "dest_h_optional", "rotation_x_optional", "rotation_y_optional"], "Copy an image with optional source/destination rectangles and rotation pivot."),
        ("gfx_blitext", ["source", "coordinate_list", "rotation"], "Copy an image using a memory list of coordinates."),
        ("gfx_getimgdim", ["image", "width", "height"], "Read image dimensions into output variables."),
        ("gfx_setimgdim", ["image", "width", "height"], "Resize an image buffer."),
        ("gfx_loadimg", ["image", "filename"], "Load an image into a buffer."),
        ("gfx_gradrect", ["x", "y", "width", "height", "r", "g", "b", "a", "drdx_optional", "dgdx_optional", "dbdx_optional", "dadx_optional", "drdy_optional", "dgdy_optional", "dbdy_optional", "dady_optional"], "Fill a rectangle with a color gradient."),
        ("gfx_muladdrect", ["x", "y", "width", "height", "mul_r", "mul_g", "mul_b", "mul_a_optional", "add_r_optional", "add_g_optional", "add_b_optional", "add_a_optional"], "Transform pixel colors in a rectangle."),
        ("gfx_deltablit", ["source", "src_x", "src_y", "src_w", "src_h", "dest_x", "dest_y", "dest_w", "dest_h", "dsdx", "dtdx", "dsdy", "dtdy", "dsdxdy", "dtdxdy", "use_clip_rect_optional"], "Copy an image with incremental texture coordinates."),
        ("gfx_transformblit", ["source", "dest_x", "dest_y", "dest_w", "dest_h", "div_w", "div_h", "table"], "Copy an image using a grid of texture coordinates."),
        ("gfx_roundrect", ["x", "y", "width", "height", "radius", "antialias_optional"], "Draw a rounded rectangle."),
        ("gfx_arc", ["x", "y", "radius", "angle1", "angle2", "antialias_optional"], "Draw a circular arc; angles are in radians."),
        ("gfx_triangle", ["x1", "y1", "x2", "y2", "x3", "y3", "..."], "Fill a triangle or convex polygon."),
        ("gfx_showmenu", ["items"], "Show a popup menu at the current graphics position."),
        ("gfx_setcursor", ["resource_id", "custom_name_optional"], "Choose the pointer appearance."),
    ],
}.items():
    for name, params, text in entries:
        add(name, params, text, page)

for name, text, page in [
    ("gfx_a2", "Secondary drawing alpha.", "gfx.php"),
    ("gfx_clear", "Graphics background clearing color/control.", "gfx.php"),
    ("gfx_ext_retina", "High-density display scaling state.", "gfx.php"),
    ("gfx_ext_flags", "Graphics host/window flags.", "gfx.php"),
    ("mouse_hwheel", "Horizontal wheel movement.", "gfx.php"),
    ("ext_gr_meter", "Gain-reduction metering for the host (REAPER 7.0+).", "vars.php"),
    ("pdc_midi", "MIDI latency-compensation control.", "vars.php"),
]:
    add(name, None, text, page, 6)

for name in ("midirecv", "midisend"):
    OVERLOADS[name] = [BUILTINS[name]["parameters"], ["offset", "msg1", "msg2", "msg3"]]
