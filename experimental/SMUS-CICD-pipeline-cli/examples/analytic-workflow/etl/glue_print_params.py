import sys
import json

print("=" * 80)
print("GLUE JOB PARAMETERS RECEIVED")
print("=" * 80)

print("\nAll sys.argv:")
print(json.dumps(sys.argv, indent=2))

print("\nParsed parameters:")
for i, arg in enumerate(sys.argv):
    print(f"  [{i}] {arg}")

print("\n" + "=" * 80)
