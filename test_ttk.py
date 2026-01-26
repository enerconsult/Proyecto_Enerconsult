import sys
print(f"Exec: {sys.executable}")
try:
    import ttkbootstrap
    print("SUCCESS: ttkbootstrap imported")
except ImportError as e:
    print(f"FAIL: {e}")
