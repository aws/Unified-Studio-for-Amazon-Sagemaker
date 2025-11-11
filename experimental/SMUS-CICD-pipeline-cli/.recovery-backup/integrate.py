"""Integration commands for SMUS CLI."""

import subprocess
import sys
from pathlib import Path


def integrate_qcli(status=False, uninstall=False):
    """Integrate SMUS CLI with Amazon Q CLI."""

    if status:
        return show_status()

    if uninstall:
        return uninstall_integration()

    return setup_integration()


def setup_integration():
    """Setup Q CLI integration."""
    print("🔧 Setting up Q CLI integration...\n")

    # 1. Check Q CLI installed
    if not check_qcli_installed():
        print("❌ Amazon Q CLI not found")
        print(
            "   Install: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/command-line-installing.html"
        )
        return 1

    print("✅ Q CLI found")

    # 2. Find SMUS CLI path
    smus_path = Path(__file__).parent.parent.parent.parent
    wrapper_script = smus_path / "run_mcp_server.sh"

    if not wrapper_script.exists():
        print(f"❌ MCP server wrapper not found: {wrapper_script}")
        return 1

    print(f"✅ SMUS CLI found: {smus_path}")

    # 3. Register MCP server
    print("\n📝 Registering MCP server...")
    result = subprocess.run(
        ["q", "mcp", "add", "--name", "smus-cli", "--command", str(wrapper_script)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        if "already exists" in result.stderr.lower():
            print("⚠️  MCP server already registered")
            print("✅ Using existing registration")
        else:
            print(f"❌ Registration failed: {result.stderr}")
            return 1
    else:
        print("✅ MCP server registered")

    # 4. Verify
    print("\n🔍 Verifying registration...")
    result = subprocess.run(["q", "mcp", "list"], capture_output=True, text=True)

    output = result.stdout + result.stderr
    if "smus-cli" in output:
        print("✅ Verification successful")
    else:
        print("⚠️  Registration succeeded but server not visible")
        return 1

    # 5. Show usage
    print("\n" + "=" * 60)
    print("🎉 Q CLI integration complete!")
    print("=" * 60)
    print("\nUsage:")
    print("  q chat")
    print("  You: Show me a notebooks pipeline")
    print("  Q: [Returns complete pipeline.yaml]")
    print("\nAvailable tools:")
    print("  • get_pipeline_example - Generate pipeline manifests")
    print("  • query_smus_kb - Search SMUS documentation")
    print("  • validate_pipeline - Validate pipeline.yaml")
    print("\nLogs:")
    print("  /tmp/smus_mcp_server.log")
    print("\nDocs:")
    print("  docs/Q_CLI_USAGE.md")
    print()

    return 0


def show_status():
    """Show Q CLI integration status."""
    print("📊 Q CLI Integration Status\n")

    # Check Q CLI
    if check_qcli_installed():
        print("✅ Q CLI: Installed")
    else:
        print("❌ Q CLI: Not installed")
        return 1

    # Check MCP registration
    result = subprocess.run(["q", "mcp", "list"], capture_output=True, text=True)

    output = result.stdout + result.stderr
    if "smus-cli" in output:
        print("✅ MCP Server: Registered")

        # Show tools
        print("\n📦 Available Tools:")
        print("  • get_pipeline_example")
        print("  • query_smus_kb")
        print("  • validate_pipeline")

        # Show logs
        log_file = Path("/tmp/smus_mcp_server.log")
        if log_file.exists():
            print(f"\n📝 Logs: {log_file}")
            print(f"   Size: {log_file.stat().st_size} bytes")

    else:
        print("❌ MCP Server: Not registered")
        print("   Run: smus-cli integrate qcli")

    return 0


def uninstall_integration():
    """Uninstall Q CLI integration."""
    print("🗑️  Uninstalling Q CLI integration...\n")

    result = subprocess.run(
        ["q", "mcp", "remove", "--name", "smus-cli"], capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"❌ Uninstall failed: {result.stderr}")
        return 1

    print("✅ MCP server removed")
    print("\nTo reinstall: smus-cli integrate qcli")

    return 0


def check_qcli_installed():
    """Check if Q CLI is installed."""
    result = subprocess.run(["q", "--version"], capture_output=True, text=True)
    return result.returncode == 0
