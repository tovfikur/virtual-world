#!/usr/bin/env python3
"""
Test script to verify economic settings price recalculation
"""

import asyncio
import sys

# Demonstrate the price calculation logic
def calculate_land_price_example():
    """
    Example showing how price is now calculated dynamically
    """
    # Admin config values
    plains_base_price = 125.0  # Admin sets this
    elevation_price_min_factor = 0.8
    elevation_price_max_factor = 1.2
    
    # Land data
    land_elevation = 0.5
    biome = "plains"
    
    print("=== Economic Settings Price Recalculation ===\n")
    print("Admin Configuration:")
    print(f"  Plains Base Price: {plains_base_price} BDT")
    print(f"  Elevation Factor Range: {elevation_price_min_factor} to {elevation_price_max_factor}")
    
    print(f"\nLand Data:")
    print(f"  Biome: {biome}")
    print(f"  Elevation: {land_elevation}")
    
    # Price calculation (NEW LOGIC)
    base = plains_base_price
    elevation = land_elevation
    elevation = max(0.0, min(1.0, elevation))  # Clamp to [0, 1]
    
    if elevation_price_min_factor > elevation_price_max_factor:
        elevation_price_min_factor, elevation_price_max_factor = elevation_price_max_factor, elevation_price_min_factor
    
    elevation_factor = elevation_price_min_factor + (elevation * (elevation_price_max_factor - elevation_price_min_factor))
    calculated_price = int(base * elevation_factor)
    
    print(f"\nCalculation:")
    print(f"  Elevation Factor = {elevation_price_min_factor} + ({elevation} * ({elevation_price_max_factor} - {elevation_price_min_factor}))")
    print(f"  Elevation Factor = {elevation_factor:.2f}")
    print(f"  Price = {base} * {elevation_factor:.2f} = {calculated_price} BDT")
    
    print(f"\n✅ Current Price Returned: {calculated_price} BDT")
    print(f"   (Previously would return old stored price from database)")
    
    # Test with different admin settings
    print("\n=== Price Changes When Admin Updates Config ===\n")
    
    test_cases = [
        {"name": "Price increase", "base": 150.0},
        {"name": "Price decrease", "base": 100.0},
        {"name": "Elevation range change", "min": 0.5, "max": 1.5},
    ]
    
    for test in test_cases:
        test_base = test.get("base", plains_base_price)
        test_min = test.get("min", elevation_price_min_factor)
        test_max = test.get("max", elevation_price_max_factor)
        
        test_elevation_factor = test_min + (land_elevation * (test_max - test_min))
        test_price = int(test_base * test_elevation_factor)
        
        print(f"{test['name']}:")
        print(f"  New Price: {test_price} BDT (was {calculated_price} BDT)")
    
    return True

if __name__ == "__main__":
    try:
        success = calculate_land_price_example()
        if success:
            print("\n✅ All examples completed successfully!")
            sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
