"""Demo script showing KB setup with user approval."""

from smus_cicd.agent.kb_setup import deploy_kb_stack, delete_kb_stack

def demo_setup():
    """Demo KB setup with user approval."""
    region = 'us-east-2'
    
    print("\n" + "="*70)
    print("DEMO: Knowledge Base Setup with User Approval")
    print("="*70)
    
    # This will show the approval prompt
    outputs = deploy_kb_stack(region=region, auto_approve=False)
    
    if outputs:
        print("\n✅ Setup complete!")
        print(f"\nOutputs:")
        for key, value in outputs.items():
            print(f"  {key}: {value}")
        
        # Cleanup
        input("\nPress Enter to cleanup...")
        delete_kb_stack(region=region)
    else:
        print("\n❌ Setup cancelled")

if __name__ == '__main__':
    demo_setup()
