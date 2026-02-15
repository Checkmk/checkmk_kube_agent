#!/usr/bin/env python3
"""Simple test to verify DedupTTLCache size() and utilization() methods work correctly."""

import sys
sys.path.insert(0, 'src')

from checkmk_kube_agent.dedup_ttl_cache import DedupTTLCache

# Create a small cache for testing
cache = DedupTTLCache(
    key=lambda x: x[0],
    maxsize=10,
    ttl=60
)

print("Testing DedupTTLCache size and utilization methods:")
print("=" * 50)

# Test 1: Empty cache
print(f"\n1. Empty cache:")
print(f"   Size: {cache.size()}")
print(f"   Utilization: {cache.utilization():.1f}%")
assert cache.size() == 0
assert cache.utilization() == 0.0

# Test 2: Add some entries
print(f"\n2. After adding 3 entries:")
cache.put(("foo", "bar"))
cache.put(("baz", "qux"))
cache.put(("hello", "world"))
print(f"   Size: {cache.size()}")
print(f"   Utilization: {cache.utilization():.1f}%")
assert cache.size() == 3
assert cache.utilization() == 30.0

# Test 3: Add duplicate (should not increase size)
print(f"\n3. After adding duplicate 'foo':")
cache.put(("foo", "updated"))
print(f"   Size: {cache.size()}")
print(f"   Utilization: {cache.utilization():.1f}%")
assert cache.size() == 3
assert cache.utilization() == 30.0

# Test 4: Fill cache to capacity
print(f"\n4. After filling to capacity (10 entries):")
for i in range(7):
    cache.put((f"key{i}", f"value{i}"))
print(f"   Size: {cache.size()}")
print(f"   Utilization: {cache.utilization():.1f}%")
assert cache.size() == 10
assert cache.utilization() == 100.0

# Test 5: Exceed capacity (oldest should be evicted)
print(f"\n5. After exceeding capacity:")
cache.put(("new", "entry"))
print(f"   Size: {cache.size()}")
print(f"   Utilization: {cache.utilization():.1f}%")
assert cache.size() == 10  # Should still be 10
assert cache.utilization() == 100.0

print("\n" + "=" * 50)
print("✅ All tests passed!")
print("\nThese methods can now be used in the API to log cache statistics.")
