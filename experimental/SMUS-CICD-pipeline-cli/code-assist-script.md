# Code Assist Script

## Automated Workflow for Code Changes

When making any code changes to the SMUS CI/CD CLI, follow this automated workflow to ensure consistency and quality:

### 0. AWS Credentials Setup (when needed)
```bash
# Refresh AWS credentials using validation script
python scripts/validate.py --aws-login

# Or manually:
isenguardcli
aws sts get-caller-identity
```

### 1. Pre-Change Validation
```bash
# Verify current state is clean
python scripts/validate.py --unit
python scripts/validate.py --integration
git status
```

### 2. Make Code Changes
- Implement the requested feature/fix
- Update relevant docstrings and comments

### 3. Update Test Cases
```bash
# Run tests to identify failures
python scripts/validate.py --unit

# Fix any failing tests by:
# - Updating test expectations to match new behavior
# - Adding new test cases for new functionality
# - Ensuring mock objects match actual implementation
# - Verifying CLI parameter usage is correct
```

### 4. Update README and Documentation
```bash
# Update README.md if:
# - CLI syntax changed
# - New commands added
# - Examples need updating
# - Diagrams need modification

# Verify examples work:
python scripts/validate.py --readme
```

### 5. Integration Test Validation
```bash
# Run integration tests (automatically refreshes AWS credentials)
python scripts/validate.py --integration
```

### 6. Final Validation and Commit
```bash
# Full validation pipeline
python scripts/validate.py --all

# Commit changes
git add .
git commit -m "Descriptive commit message

- List specific changes made
- Note test updates
- Note documentation updates"

# Verify clean state
git status
```

## Python-Native Validation Commands

```bash
# Quick validation options
python scripts/validate.py --unit           # Unit tests only
python scripts/validate.py --integration    # Integration tests only  
python scripts/validate.py --readme         # README examples only
python scripts/validate.py --aws-login      # AWS credentials only
python scripts/validate.py --clean          # Clean temp files
python scripts/validate.py --all            # Full validation (default)

# Alternative using pytest directly
pytest tests/unit/                          # Unit tests
pytest tests/integration/ -m "not slow"     # Integration tests
```

## Checklist for Any Code Change

- [ ] AWS credentials refreshed (when needed)
- [ ] Unit tests pass (95/95)
- [ ] Integration tests pass (basic suite)
- [ ] README examples are accurate and tested
- [ ] CLI help text is updated if needed
- [ ] New functionality has corresponding tests
- [ ] Mock objects match real implementation
- [ ] CLI parameter usage is consistent
- [ ] Documentation reflects actual behavior
- [ ] Check that the code and markdown files don't contain aws account ids , nor web addresses, or host names.  mask all of these before committing. 
- [ ] All changes are committed
- [ ] Follow PEP 8 Coding Style 
- [ ] Keep functions short.  Break functions if they contain multiple loops or long if\else clauses.  Use good naming for function names and variables names. 
- [ ] Add a docstring to explain the purpose of the function and its parameters.
- [ ] Add type annotations for better clarity and maintainability

## Common Test Patterns to Maintain

### Unit Test Patterns
- Mock objects need proper attributes, not dictionaries
- Test expectations should match actual output format
- Use proper patch decorators for dependencies

### Integration Test Patterns
- Expected exit codes should match test framework expectations
- Rename DAG files to avoid pytest collection (`.dag` extension)

### README Patterns
- All CLI examples use correct parameter syntax
- Include realistic command outputs
- Keep examples concise but informative
- Verify examples actually work before documenting
- Make sure all markeup files in the project are updated and not only the main README file

## Project Structure (Python-Native)

```
smus_cicd/
├── pyproject.toml          # Modern Python project config
├── scripts/
│   └── validate.py         # Validation script (replaces Makefile)
├── smus_cicd/             # Main package
├── tests/                 # Test suite
└── README.md              # Documentation
```

## AWS Credential Management

When you say "refresh your aws credentials", I will run:
```bash
python scripts/validate.py --aws-login
```

This ensures integration tests that require AWS access will work properly.

This script ensures that every code change maintains the quality and consistency of the codebase using Python-native tools.
