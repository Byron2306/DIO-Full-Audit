# Metatron-Seraph Testing Framework

## Overview

This comprehensive testing framework implements a 5-layer testing strategy for the Metatron-Seraph deception system:

1. **Unit Tests (Layer 1)**: Test individual components in isolation
2. **Integration Tests (Layer 2)**: Test component interactions
3. **API Tests (Layer 3)**: Test REST API endpoints
4. **End-to-End Tests (Layer 4)**: Test complete workflows
5. **Performance Tests (Layer 5)**: Test system performance under load

## Test Structure

```
tests/
├── unit/                    # Layer 1: Unit tests
│   ├── test_agenticity.py
│   ├── test_maze.py
│   ├── test_honey_tokens.py
│   └── test_deception_router.py
├── integration/            # Layer 2: Integration tests
│   └── test_service_integration.py
├── api/                    # Layer 3: API tests
│   └── test_deception_api.py
├── e2e/                    # Layer 4: End-to-end tests
│   └── test_complete_workflow.py
└── performance/            # Layer 5: Performance tests
    └── test_performance.py
```

## Running Tests

### Run All Tests

```bash
# Run complete test suite
python run_tests.py

# Run with options
python run_tests.py --no-performance  # Skip performance tests
python run_tests.py --no-smoke        # Skip smoke tests
```

### Run Specific Layers

```bash
# Run only unit tests
python run_tests.py --layer unit

# Run only API tests
python run_tests.py --layer api

# Run only performance tests
python run_tests.py --layer performance
```

### Run with Pytest Directly

```bash
# Run all tests
pytest

# Run specific markers
pytest -m unit
pytest -m api
pytest -m performance

# Run specific files
pytest tests/unit/test_agenticity.py -v

# Run with coverage
pytest --cov=backend --cov-report=html
```

## Test Categories

### Unit Tests (`pytest -m unit`)
- Test individual functions and classes
- Mock external dependencies
- Fast execution, high coverage

### Integration Tests (`pytest -m integration`)
- Test component interactions
- Mock databases and external services
- Verify data flow between components

### API Tests (`pytest -m api`)
- Test REST API endpoints
- Use FastAPI TestClient
- Verify request/response formats
- Test error handling

### End-to-End Tests (`pytest -m e2e`)
- Test complete deception workflows
- From detection → analysis → persistence
- Verify cross-component coordination

### Performance Tests (`pytest -m performance`)
- Test response times and throughput
- Concurrent load testing
- Memory usage monitoring
- Scalability validation

## Test Data and Fixtures

### Mock Data
Tests use comprehensive mock data that simulates:
- Realistic agent behavior patterns
- Maze navigation scenarios
- Honey token access patterns
- Database operations

### Test Fixtures
- `mock_db`: Mocked MongoDB database
- `client`: FastAPI test client
- `app`: Test application instance

## Performance Benchmarks

### Target Performance Metrics

**API Endpoints:**
- Average response time: < 500ms
- 95th percentile: < 1s
- Concurrent requests (10): < 2s total

**Database Operations:**
- Single operation: < 100ms
- Batch operations (10): < 1s

**Memory Usage:**
- Token creation (1000): < 50MB increase
- No memory leaks detected

## Coverage Requirements

- **Unit Tests**: > 90% coverage
- **Integration Tests**: > 85% coverage
- **API Tests**: 100% endpoint coverage
- **E2E Tests**: All major workflows

## Continuous Integration

Tests are designed to run in CI environments:

```bash
# Quick CI run (skip slow tests)
pytest -m "not slow" --tb=line

# Full CI run
pytest --cov=backend --cov-report=xml

# Performance regression detection
pytest -m performance --durations=10
```

## Debugging Failed Tests

### Common Issues

1. **Import Errors**: Ensure `PYTHONPATH` includes `backend/`
   ```bash
   PYTHONPATH=backend pytest tests/unit/
   ```

2. **Async Test Issues**: Use `pytest-asyncio` and mark async tests
   ```python
   @pytest.mark.asyncio
   async def test_async_function():
       # test code
   ```

3. **Mock Setup**: Ensure mocks are properly configured
   ```python
   with patch('module.Class') as mock_class:
       mock_instance = mock_class.return_value
       mock_instance.method.return_value = expected_value
   ```

### Debugging Commands

```bash
# Run with detailed output
pytest -v -s --tb=long

# Run specific failing test
pytest tests/unit/test_agenticity.py::TestAgenticityScoring::test_compute_score -v

# Run with coverage details
pytest --cov=backend --cov-report=html && open htmlcov/index.html
```

## Test Maintenance

### Adding New Tests

1. **Unit Tests**: Add to `tests/unit/`
2. **Integration Tests**: Add to `tests/integration/`
3. **API Tests**: Add to `tests/api/`
4. **E2E Tests**: Add to `tests/e2e/`
5. **Performance Tests**: Add to `tests/performance/`

### Test Naming Convention

```python
class TestComponentName:
    def test_specific_functionality(self):
        # test code

    def test_edge_case_scenario(self):
        # test code
```

### Mock Best Practices

- Use `AsyncMock` for async functions
- Mock at the module level to avoid import issues
- Use `patch` context managers for isolation
- Verify mock calls when behavior matters

## Reporting

### Test Reports

- **Console Output**: Real-time test results
- **JSON Report**: `test_report_YYYYMMDD_HHMMSS.json`
- **Coverage Report**: `htmlcov/index.html`
- **Performance Metrics**: Printed during performance tests

### Interpreting Results

- **✅ PASSED**: Test successful
- **❌ FAILED**: Test failed - check stderr
- **⚠️ SKIPPED**: Test skipped (missing dependencies, etc.)
- **📊 Coverage**: Code coverage percentage

## Dependencies

Test dependencies are listed in `requirements.txt`:
- `pytest`: Test framework
- `pytest-asyncio`: Async test support
- `pytest-cov`: Coverage reporting
- `httpx`: HTTP client for API tests
- `fastapi[test]`: FastAPI testing tools

Install with:
```bash
pip install -r requirements.txt
```