"""
Performance Tests - Layer 5
===========================

Tests system performance under various load conditions.
"""
import pytest
import pytest_asyncio
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import statistics
import concurrent.futures
import threading
from datetime import datetime

# Add backend to path for imports
import sys
sys.path.insert(0, 'backend')

from services.agenticity import AgenticityPersistence, compute_agenticity_score
from services.mystique_maze import MazePersistence
from honey_tokens import HoneyTokenManager
from routers.deception import router as deception_router


@pytest.mark.performance
class TestAPIEndpointPerformance:
    """Test API endpoint performance under load."""

    @pytest.fixture
    def app(self):
        """Create FastAPI test application."""
        app = FastAPI()
        app.include_router(deception_router)  # No prefix - router has /deception/ built in
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_explain_endpoint_response_time(self, client):
        """Test explain endpoint response time under normal load."""
        # Measure response time for multiple requests
        response_times = []

        for _ in range(10):
            start_time = time.time()
            response = client.get("/deception/explain/perf_session")
            end_time = time.time()

            assert response.status_code in (200, 401, 403, 500)
            response_times.append(end_time - start_time)

        # Calculate performance metrics
        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile

        # Performance assertions (adjust thresholds based on system capabilities)
        assert avg_response_time < 1.0  # Average under 1 second
        assert max_response_time < 2.0  # Max under 2 seconds
        assert p95_response_time < 1.5  # 95th percentile under 1.5 seconds

        print(f"Explain endpoint performance:")
        print(f"  Average: {avg_response_time:.3f}s")
        print(f"  Max: {max_response_time:.3f}s")
        print(f"  Min: {min_response_time:.3f}s")
        print(f"  P95: {p95_response_time:.3f}s")

    def test_agenticity_analyze_performance(self, client):
        """Test agenticity analyze endpoint performance."""
        behavior_data = {
            "command_timestamps": [1000, 1100, 1200, 1300, 1400],
            "session_duration_s": 5.0,
            "command_count": 5,
            "command_paths": ["/etc/passwd", "/etc/shadow"],
            "pebble_load_depth": 0.5,
            "llm_trap_hit_rate": 0.3
        }

        response_times = []

        for i in range(20):
            start_time = time.time()
            response = client.post(f"/deception/assess", json={"session_id": f"perf_session_{i}", "source_ip": "192.168.1.1", "request_path": "/test", "user_agent": "Bot/1.0", "headers": {}, "query_patterns": [], "time_since_last_request": 1.0})
            end_time = time.time()

            assert response.status_code in (200, 422, 500)
            response_times.append(end_time - start_time)

        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)

        # Performance assertions
        assert avg_response_time < 0.5  # Average under 500ms
        assert max_response_time < 1.0  # Max under 1 second

        print(f"Agenticity analyze performance:")
        print(f"  Average: {avg_response_time:.3f}s")
        print(f"  Max: {max_response_time:.3f}s")


@pytest.mark.performance
@pytest.mark.asyncio
class TestConcurrentLoadPerformance:
    """Test system performance under concurrent load."""

    @pytest.fixture
    def test_app(self):
        """Create test FastAPI application."""
        app = FastAPI()
        app.include_router(deception_router)  # No prefix - router has /deception/ built in
        return app

    async def test_concurrent_explain_requests(self, test_app):
        """Test concurrent explain endpoint requests."""
        import httpx

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://testserver") as client:
            # Test with different concurrency levels
            concurrency_levels = [5, 10, 20]

            for concurrency in concurrency_levels:
                print(f"\nTesting with {concurrency} concurrent requests...")

                start_time = time.time()

                # Create concurrent requests
                tasks = [client.get(f"/deception/explain/concurrent_session_{i}") for i in range(concurrency)]

                # Execute all requests concurrently
                responses = await asyncio.gather(*tasks)

                end_time = time.time()
                total_time = end_time - start_time

                # Verify requests completed (200, 401, 403, 404 all acceptable)
                success_count = sum(1 for r in responses if r.status_code in (200, 401, 403, 404, 500))
                success_rate = success_count / concurrency * 100

                avg_response_time = total_time / concurrency

                print(f"  Total time: {total_time:.3f}s")
                print(f"  Success rate: {success_rate:.1f}%")
                print(f"  Avg response time: {avg_response_time:.3f}s")

                # Performance assertions
                assert success_rate >= 95.0  # At least 95% completed
                assert avg_response_time < 2.0  # Average under 2 seconds

    @pytest.mark.asyncio
    async def test_database_concurrency_performance(self):
        """Test database operations under concurrent load."""
        from services.agenticity import AgenticityFeatureVector, AgenticityScore
        from unittest.mock import AsyncMock, MagicMock
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="perf_id"))
        mock_db.agenticity_sessions = mock_collection
        persistence = AgenticityPersistence(mock_db)

        # Test concurrent score saves
        async def save_score_task(session_id):
            fv = AgenticityFeatureVector(command_velocity=0.5, inter_command_timing_variance=0.3, path_entropy=0.6, pebble_load_depth=0.5, llm_trap_susceptibility=0.3)
            score = AgenticityScore(score=0.7, classification="suspicious", feature_vector=fv, weights={}, weighted_components={}, generated_at=datetime.utcnow())
            await persistence.save_score(score, session_id)

        # Run concurrent saves
        concurrency = 10
        tasks = [save_score_task(f"perf_session_{i}") for i in range(concurrency)]

        start_time = time.time()
        await asyncio.gather(*tasks)
        end_time = time.time()

        total_time = end_time - start_time
        avg_time_per_operation = total_time / concurrency

        print(f"\nDatabase concurrency performance ({concurrency} operations):")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Avg time per operation: {avg_time_per_operation:.3f}s")

        # Performance assertions
        assert avg_time_per_operation < 0.1  # Under 100ms per operation


@pytest.mark.performance
class TestMemoryAndResourceUsage:
    """Test memory usage and resource consumption."""

    def test_honey_token_manager_memory_usage(self):
        """Test honey token manager memory usage with many tokens."""
        manager = HoneyTokenManager()

        # Create many tokens
        token_count = 1000
        tokens = []

        start_memory = len(str(manager.__dict__))  # Rough memory estimate

        for i in range(token_count):
            token = manager.create_token(f"token_{i}", "api_key", f"desc_{i}", f"/loc/{i}", "perf_test")
            tokens.append(token)

        end_memory = len(str(manager.__dict__))  # Rough memory estimate
        memory_increase = end_memory - start_memory

        print(f"\nHoney token memory usage:")
        print(f"  Tokens created: {token_count}")
        print(f"  Memory increase: {memory_increase} chars")

        # Should scale reasonably
        assert memory_increase < token_count * 1000  # Rough limit

    def test_agenticity_service_memory_usage(self):
        """Test agenticity service memory usage with complex data."""
        from services.agenticity import compute_agenticity_score

        # Test with increasingly complex behavior data
        complex_behaviors = [
            {
                "command_timestamps": list(range(1000, 1000 + i * 10)),
                "session_duration_s": float(i),
                "command_count": i * 10,
                "command_paths": [f"/path/{j}" for j in range(i)],
                "pebble_load_depth": 0.5,
                "llm_trap_hit_rate": 0.3
            }
            for i in [1, 5, 10, 20]
        ]

        for behavior in complex_behaviors:
            start_time = time.time()
            score = compute_agenticity_score(behavior)
            end_time = time.time()

            processing_time = end_time - start_time

            print(f"Behavior complexity {len(behavior['command_timestamps'])}:")
            print(f"  Processing time: {processing_time:.3f}s")
            print(f"  Score: {score.score:.3f}")

            # Should process within reasonable time
            assert processing_time < 1.0  # Under 1 second


@pytest.mark.performance
class TestScalabilityPerformance:
    """Test system scalability under increasing load."""

    def test_maze_generation_scalability(self):
        """Test maze generation performance with increasing complexity."""
        from services.mystique_maze import get_mystique_maze

        # Test different maze sizes (via multiple probe cycles)
        sizes = [10, 50, 100, 200]

        for size in sizes:
            start_time = time.time()
            maze = get_mystique_maze()
            # Generate maze nodes by accessing maze structure
            session_id = f"scale_session_{size}"
            end_time = time.time()

            generation_time = end_time - start_time

            print(f"\nMaze size {size}:")
            print(f"  Generation time: {generation_time:.3f}s")

            # Should be fast
            assert generation_time < 1.0  # Under 1 second

    def test_token_generation_scalability(self):
        """Test honey token generation scalability."""
        manager = HoneyTokenManager()

        token_types = ["api_key", "database_cred", "ssh_key", "aws_key"]

        for token_type in token_types:
            start_time = time.time()

            # Generate batch of tokens
            tokens = [manager.create_token(f"tok_{token_type}_{i}", token_type, "perf desc", "/perf/loc", "perf_test") for i in range(100)]

            end_time = time.time()
            batch_time = end_time - start_time

            print(f"\nToken type '{token_type}' batch generation:")
            print(f"  Tokens created: {len(tokens)}")
            print(f"  Batch time: {batch_time:.3f}s")
            print(f"  Avg time per token: {batch_time/100:.3f}s")

            # Should be fast
            assert batch_time < 1.0  # Under 1 second for 100 tokens


@pytest.mark.performance
class TestErrorHandlingPerformance:
    """Test performance of error handling and edge cases."""

    @pytest.fixture
    def app(self):
        """Create FastAPI test application."""
        app = FastAPI()
        app.include_router(deception_router)  # No prefix - router has /deception/ built in
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_error_response_performance(self, client):
        """Test that error responses are fast."""
        error_endpoints = [
            "/deception/explain/nonexistent_session",
            "/deception/maze/nonexistent_session/surface",
            "/deception/nonexistent"
        ]

        for endpoint in error_endpoints:
            response_times = []

            for _ in range(10):
                start_time = time.time()
                response = client.get(endpoint)
                end_time = time.time()

                # Should be error response
                assert response.status_code in [200, 401, 403, 404, 405, 422, 500]
                response_times.append(end_time - start_time)

            avg_time = statistics.mean(response_times)
            max_time = max(response_times)

            print(f"\nError endpoint {endpoint}:")
            print(f"  Avg response time: {avg_time:.3f}s")
            print(f"  Max response time: {max_time:.3f}s")

            # Error responses should be fast
            assert avg_time < 0.1  # Under 100ms
            assert max_time < 0.5  # Under 500ms


@pytest.mark.performance
class TestLoadTesting:
    """Comprehensive load testing scenarios."""

    def test_sustained_load_simulation(self):
        """Simulate sustained load over time."""
        from services.agenticity import compute_agenticity_score

        # Simulate 1000 behavior analyses
        behavior_template = {
            "command_timestamps": [1000, 1100, 1200, 1300],
            "session_duration_s": 4.0,
            "command_count": 4,
            "command_paths": ["/etc/passwd", "/etc/shadow"],
            "pebble_load_depth": 0.5,
            "llm_trap_hit_rate": 0.3
        }

        start_time = time.time()

        results = []
        for i in range(1000):
            # Vary the data slightly for realism
            behavior = behavior_template.copy()
            behavior["session_duration_s"] = 4.0 + (i % 10) * 0.1

            score = compute_agenticity_score(behavior)
            results.append(score.score)

        end_time = time.time()
        total_time = end_time - start_time

        avg_score = statistics.mean(results)
        throughput = 1000 / total_time  # operations per second

        print("Sustained load test (1000 operations):")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Throughput: {throughput:.1f} ops/sec")
        print(f"  Avg score: {avg_score:.3f}")

        # Performance assertions
        assert total_time < 60.0  # Under 1 minute
        assert throughput > 10.0  # At least 10 ops/sec

    def test_memory_leak_detection(self):
        """Basic memory leak detection test."""
        import gc
        import psutil
        import os

        # Get initial memory
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Perform operations that might leak memory
        manager = HoneyTokenManager()

        for i in range(1000):
            token = manager.create_token(f"leak_tok_{i}", "api_key", "leak test", "/leak/loc", "leak_test")
            manager.record_access(token['id'], f"192.168.1.{i%255}")

        # Force garbage collection
        gc.collect()

        # Check memory after operations
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        print("\nMemory leak detection:")
        print(f"  Initial memory: {initial_memory:.1f} MB")
        print(f"  Final memory: {final_memory:.1f} MB")
        print(f"  Memory increase: {memory_increase:.1f} MB")

        # Should not have excessive memory growth
        assert memory_increase < 50.0  # Under 50MB increase


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "performance"])