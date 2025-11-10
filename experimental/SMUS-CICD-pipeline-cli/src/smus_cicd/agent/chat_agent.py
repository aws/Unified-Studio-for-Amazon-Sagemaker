"""Main SMUS CLI Chat Agent."""

from typing import List, Dict, Any
from pathlib import Path

from .config import load_config, get_model_id, get_kb_id
from .bedrock_client import BedrockClient
from .kb_retrieval import KnowledgeBaseRetriever
from .kb_setup import ensure_kb_exists


SYSTEM_PROMPT = """You are an expert SMUS CLI assistant for Amazon SageMaker Unified Studio CI/CD pipelines.

CRITICAL CONTEXT:
- SMUS = SageMaker Unified Studio (NOT generic ML pipelines)
- This CLI creates CI/CD pipelines for deploying code/workflows to SMUS projects
- Pipelines have: targets (dev/test/prod), bundles (code packages), workflows (Airflow DAGs)
- Users deploy notebooks, Python scripts, SQL queries, Glue jobs to SMUS environments

Your capabilities:
1. Answer questions about SMUS CLI features and usage
2. Build SMUS CI/CD pipeline manifests interactively when requested
3. Troubleshoot SMUS deployment and workflow issues
4. Provide examples of pipeline.yaml manifests
5. Explain SMUS concepts: domains, projects, connections, bundles, targets
6. Generate pipeline manifests, Airflow workflows, tests, and GitHub Actions

When user asks to "set up a pipeline" or "create a pipeline":
- They want a SMUS CI/CD pipeline (pipeline.yaml manifest)
- Ask about: pipeline name, SMUS domain, projects (dev/test/prod), code location
- NOT about ML model types or SageMaker endpoints
- Focus on: bundle configuration, target environments, workflow deployment

When building SMUS pipelines:
- Start with: pipeline name, domain name, source project
- Ask about target environments (dev, test, prod)
- Ask about bundle contents (notebooks, scripts, workflows)
- Ask about SMUS connections (S3, Athena, Spark, workflows)
- Generate pipeline.yaml manifest following SMUS schema

When answering questions:
- Search knowledge base for SMUS CLI documentation
- Provide complete pipeline.yaml examples
- Explain SMUS-specific concepts
- Keep answers concise but comprehensive

Always maintain conversation context and adapt to user needs."""


class SMUSChatAgent:
    """Unified chat agent for SMUS CLI."""
    
    def __init__(self, model_id: str = None, kb_id: str = None):
        """
        Initialize chat agent.
        
        Args:
            model_id: Bedrock model ID (uses config default if None)
            kb_id: Knowledge Base ID (uses config default if None)
        """
        self.config = load_config()
        self.model_id = model_id or get_model_id(self.config)
        
        # Try to ensure KB exists (auto-setup on first run)
        if kb_id is None and not get_kb_id(self.config):
            kb_id = ensure_kb_exists()
        
        self.kb_id = kb_id or get_kb_id(self.config)
        
        # Initialize clients
        region = self.config.get('interactive', {}).get('region', 'us-east-1')
        self.bedrock = BedrockClient(self.model_id, region)
        self.kb_retriever = KnowledgeBaseRetriever(self.kb_id, region) if self.kb_id else None
        
        # Conversation state
        self.conversation_history = []
        self.building_pipeline = False
        self.pipeline_state = {}
    
    def start(self):
        """Start interactive chat session."""
        self._show_welcome()
        
        while True:
            try:
                user_input = input("\n\033[1;36mYou:\033[0m ").strip()
                
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    self._show_goodbye()
                    break
                
                if not user_input:
                    continue
                
                # Process message and get response
                response = self._process_message(user_input)
                print(f"\n\033[1;32mAgent:\033[0m {response}")
                
            except KeyboardInterrupt:
                print("\n")
                self._show_goodbye()
                break
            except Exception as e:
                print(f"\n\033[1;31m❌ Error:\033[0m {str(e)}")
    
    def _process_message(self, user_message: str) -> str:
        """
        Process user message and return agent response.
        
        Args:
            user_message: User's input message
            
        Returns:
            Agent's response
        """
        # Retrieve relevant context from KB
        retrieved_docs = []
        if self.kb_retriever:
            retrieved_docs = self.kb_retriever.retrieve(user_message, max_results=3)
        
        # Generate response with context
        response = self.bedrock.invoke_with_context(
            user_message=user_message,
            conversation_history=self.conversation_history,
            system_prompt=SYSTEM_PROMPT,
            retrieved_context=retrieved_docs
        )
        
        # Update conversation history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })
        
        # Keep history manageable (last 10 exchanges)
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
        
        return response
    
    def _show_welcome(self):
        """Display welcome message."""
        print("\n" + "="*70)
        print("\033[1;34m🤖 SMUS CLI Agent\033[0m")
        print("Your AI assistant for SageMaker Unified Studio CI/CD")
        print("\nType 'exit' to quit")
        print("="*70)
        
        if not self.kb_id:
            print("\n\033[1;33m⚠️  Knowledge Base not configured\033[0m")
            print("Enhanced search with documentation is not available.")
            
            response = input("\nWould you like to set up the Knowledge Base now? (yes/no): ").strip().lower()
            if response in ['yes', 'y']:
                print("\n🚀 Starting Knowledge Base setup...")
                try:
                    from .kb_setup import (
                        deploy_kb_stack,
                        create_opensearch_index,
                        create_bedrock_kb,
                        create_data_source,
                        start_ingestion
                    )
                    from .config import save_config
                    import time
                    
                    # Get region from config
                    region = self.config.get('interactive', {}).get('region', 'us-east-1')
                    
                    # Deploy stack
                    outputs = deploy_kb_stack(region=region, auto_approve=False)
                    if not outputs:
                        print("\n❌ Setup cancelled by user")
                        print("\nExiting. Run 'smus-cli chat' again when ready.")
                        exit(0)
                    
                    # Wait for policies
                    print("\n⏳ Waiting 2 minutes for policies to propagate...")
                    time.sleep(120)
                    
                    # Create index
                    create_opensearch_index(outputs['CollectionEndpoint'], region)
                    
                    # Create KB
                    kb_result = create_bedrock_kb(
                        outputs['KnowledgeBaseRoleArn'],
                        outputs['CollectionArn'],
                        region
                    )
                    
                    # Create data source
                    ds_id = create_data_source(
                        kb_result['kb_id'],
                        outputs['BucketName'],
                        region
                    )
                    
                    # Start ingestion
                    start_ingestion(kb_result['kb_id'], ds_id, region)
                    
                    # Save to config
                    self.config['bedrock'] = {
                        'knowledge_base_id': kb_result['kb_id'],
                        'data_source_id': ds_id
                    }
                    save_config(self.config)
                    
                    self.kb_id = kb_result['kb_id']
                    self.kb_retriever = KnowledgeBaseRetriever(kb_result['kb_id'], region)
                    
                    print("\n✅ Knowledge Base setup complete!")
                    print(f"KB ID: {kb_result['kb_id']}")
                    
                except Exception as e:
                    print(f"\n❌ Setup failed: {e}")
                    print("\n" + "="*70)
                    print("Knowledge Base setup is required to continue.")
                    print("\nPlease fix the issue and try again:")
                    print("  1. Check the error details above")
                    print("  2. Clean up any partial resources: smus-cli kb delete")
                    print("  3. Try setup again: smus-cli chat")
                    print("="*70)
                    exit(1)
            else:
                print("\nContinuing without Knowledge Base (model knowledge only)")
                print("You can set it up later with: smus-cli kb setup")
    
    def _show_goodbye(self):
        """Display goodbye message."""
        print("\n\033[1;34m👋 Goodbye!\033[0m")
        print("Your conversation has been saved.")


def start_chat(model_id: str = None, kb_id: str = None):
    """
    Start chat session (entry point for CLI).
    
    Args:
        model_id: Optional Bedrock model ID
        kb_id: Optional Knowledge Base ID
    """
    agent = SMUSChatAgent(model_id=model_id, kb_id=kb_id)
    agent.start()


def setup_kb():
    """Setup Knowledge Base (entry point for CLI)."""
    from .kb_setup import ensure_kb_exists
    kb_id = ensure_kb_exists()
    if kb_id:
        print(f"\n✅ Knowledge Base ready: {kb_id}")
        print("You can now use: smus-cli chat")


def sync_kb():
    """Sync Knowledge Base (entry point for CLI)."""
    from .kb_setup import sync_kb as do_sync
    do_sync()
