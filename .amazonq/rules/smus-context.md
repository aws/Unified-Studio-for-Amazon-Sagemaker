# SMUS CI/CD Pipeline Development Context

This is the Amazon SageMaker Unified Studio (SMUS) CI/CD Pipeline CLI project. Follow these development guidelines:

## Project Structure
- Main CLI code: `experimental/SMUS-CICD-pipeline-cli/src/smus_cicd/`
- Tests: `experimental/SMUS-CICD-pipeline-cli/tests/`
- Examples: `experimental/SMUS-CICD-pipeline-cli/examples/`

## Development Workflow
1. **Pre-change validation**: Run unit/integration tests
2. **Code changes**: Follow PEP 8, proper exception handling
3. **Linting**: `flake8`, `black`, `isort` must pass
4. **Testing**: Update and run all tests
5. **Documentation**: Update README if CLI changes
6. **Integration tests**: Validate end-to-end workflows

## Key Commands
```bash
# Style checks
flake8 src/smus_cicd/ --config=setup.cfg
black --check src/smus_cicd/
isort --check-only src/smus_cicd/

# Auto-fix formatting
black src/smus_cicd/
isort src/smus_cicd/

# Run tests
python tests/run_tests.py --type unit
python tests/run_tests.py --type integration
python tests/run_tests.py --type all
```

## Test Environment
- AWS Account: 198737698272
- Region: us-east-1
- Project: test-marketing
- Service: mwaaserverless-internal (pre-GA)

## Critical Standards
- Never swallow exceptions
- DataZone functions must raise exceptions for proper CLI exit codes
- Mock objects need proper attributes, not dictionaries
- No hardcoded AWS account IDs, regions, or endpoints
- All CLI examples must use correct parameter syntax