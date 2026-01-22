import pandas as pd
import re
from datetime import datetime, timedelta

def convertir_hora(h_str, es_base_0=True):
    try:
        if str(h_str).isdigit():
            h_int = int(h_str)
        else:
            match = re.search(r'(\d+)', str(h_str))
            if match:
                h_int = int(match.group(1))
            else:
                return 0
        
        if not es_base_0: h_int -= 1
        return h_int
    except: return 0

print("Testing convertir_hora...")
print(f"'0' -> {convertir_hora('0')}")
print(f"'23' -> {convertir_hora('23')}")
print(f"'hora0' -> {convertir_hora('hora0')}")
print(f"'h23' -> {convertir_hora('h23')}")
print(f"'Periodo 1' (Base 1) -> {convertir_hora('Periodo 1', es_base_0=False)}")

# Check correctness
assert convertir_hora('hora0') == 0
assert convertir_hora('h23') == 23
assert convertir_hora('Periodo 1', es_base_0=False) == 0

print("✅ Regex logic verified.")
