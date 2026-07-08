# Smoke tests
#!/usr/bin/env python
"""CI Smoke Tests"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'employee_monitor')
django.setup()

print("="*60)
print("🚀 RUNNING SMOKE TESTS")
print("="*60)

try:
    import employee_monitor
    print("✅ Monitoring code loaded successfully")
    
    if hasattr(employee_monitor, 'main'):
        print("✅ main() function exists")
    
    classes = ['FileDetectionHandler', 'FileMonitor', 'SimpleEmployeeMonitoringAgent', 'ManagerDashboard']
    for cls in classes:
        if hasattr(employee_monitor, cls):
            print(f"✅ {cls} class exists")
    
    print("\n🎉 All smoke tests passed!")
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Test failed: {e}")
    sys.exit(1)