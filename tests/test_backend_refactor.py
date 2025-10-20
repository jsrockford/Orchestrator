#!/usr/bin/env python3
"""
Quick validation that TmuxController properly implements SessionBackend interface.
"""

from src.controllers.tmux_controller import TmuxController
from src.controllers.session_backend import SessionBackend, SessionSpec
import inspect

def test_interface_compliance():
    """Verify TmuxController implements all SessionBackend abstract methods."""

    print("=== SessionBackend Interface Compliance Test ===\n")

    # Check inheritance
    print("1. Checking inheritance...")
    assert issubclass(TmuxController, SessionBackend), "TmuxController must inherit from SessionBackend"
    print("   ✓ TmuxController inherits from SessionBackend\n")

    # Get all abstract methods from SessionBackend
    abstract_methods = {
        name for name, method in inspect.getmembers(SessionBackend, predicate=inspect.isfunction)
        if getattr(method, '__isabstractmethod__', False)
    }

    print("2. Checking abstract method implementation...")
    print(f"   Required methods: {sorted(abstract_methods)}\n")

    # Check each abstract method is implemented
    for method_name in abstract_methods:
        assert hasattr(TmuxController, method_name), f"Missing method: {method_name}"
        method = getattr(TmuxController, method_name)
        assert callable(method), f"{method_name} must be callable"
        print(f"   ✓ {method_name} implemented")

    print("\n3. Checking SessionSpec usage...")
    # Create a test instance
    controller = TmuxController(
        session_name="test-session",
        executable="echo",
        working_dir="/tmp"
    )

    # Verify spec attribute exists
    assert hasattr(controller, 'spec'), "Controller must have 'spec' attribute"
    assert isinstance(controller.spec, SessionSpec), "spec must be a SessionSpec instance"
    assert controller.spec.name == "test-session"
    assert controller.spec.executable == "echo"
    assert controller.spec.working_dir == "/tmp"
    print("   ✓ SessionSpec properly initialized\n")

    print("4. Checking backward compatibility...")
    assert hasattr(controller, 'session_name'), "Must maintain session_name attribute"
    assert hasattr(controller, 'executable'), "Must maintain executable attribute"
    assert hasattr(controller, 'working_dir'), "Must maintain working_dir attribute"
    assert controller.session_name == "test-session"
    assert controller.executable == "echo"
    assert controller.working_dir == "/tmp"
    print("   ✓ Backward compatible attributes preserved\n")

    print("5. Checking interface method signatures...")
    # Verify new interface methods exist
    interface_methods = [
        'start', 'send_text', 'send_enter', 'send_ctrl_c',
        'capture_output', 'capture_scrollback', 'list_clients',
        'attach', 'kill', 'session_exists', 'get_status'
    ]

    for method_name in interface_methods:
        assert hasattr(controller, method_name), f"Missing interface method: {method_name}"
        print(f"   ✓ {method_name} available")

    print("\n6. Checking legacy method compatibility...")
    legacy_methods = ['start_session', 'send_command', 'kill_session', 'attach_for_manual']
    for method_name in legacy_methods:
        assert hasattr(controller, method_name), f"Missing legacy method: {method_name}"
        print(f"   ✓ {method_name} available (backward compatibility)")

    print("\n" + "="*50)
    print("✅ ALL CHECKS PASSED - Interface refactoring successful!")
    print("="*50)

if __name__ == "__main__":
    try:
        test_interface_compliance()
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
