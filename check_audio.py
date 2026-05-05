import sounddevice as sd
devices = sd.query_devices()
print("All devices:")
for i, d in enumerate(devices):
    inp = d["max_input_channels"]
    outp = d["max_output_channels"]
    print(f"  [{i:2d}] {d['name'][:60]:60s}  IN={inp}  OUT={outp}")

print("\n--- Output devices (non-zero OUT) ---")
for i, d in enumerate(devices):
    if d["max_output_channels"] > 0:
        print(f"  [{i:2d}] {d['name'][:60]}  SR={d.get('default_samplerate','?')}")
