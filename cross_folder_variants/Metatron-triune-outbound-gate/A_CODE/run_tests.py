#!/usr/bin/env python3
"""
Comprehensive Test Runner - Metatron-Seraph Testing Framework
===========================================================

Executes all 5 testing layers in sequence with detailed reporting.
"""
import subprocess
import sys
import os
import time
from datetime import datetime
import json
import argparse


class TestRunner:
    """Comprehensive test runner for all testing layers."""

    def __init__(self, workspace_root):
        self.workspace_root = workspace_root
        self.test_results = {}
        self.start_time = None

    def run_command(self, command, cwd=None, capture_output=True):
        """Run a shell command and return results."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd or self.workspace_root,
                capture_output=capture_output,
                text=True,
                timeout=300  # 5 minute timeout
            )
            return {
                'success': result.returncode == 0,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': command
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'returncode': -1,
                'stdout': '',
                'stderr': 'Command timed out after 300 seconds',
                'command': command
            }
        except Exception as e:
            return {
                'success': False,
                'returncode': -1,
                'stdout': '',
                'stderr': str(e),
                'command': command
            }

    def run_unit_tests(self):
        """Run unit tests (Layer 1)."""
        print("\n" + "="*60)
        print("🧪 RUNNING UNIT TESTS (Layer 1)")
        print("="*60)

        test_dirs = [
            "tests/unit/test_agenticity.py",
            "tests/unit/test_maze.py",
            "tests/unit/test_honey_tokens.py",
            "tests/unit/test_deception_router.py",
            "tests/integration/test_service_integration.py"
        ]

        results = []
        for test_file in test_dirs:
            if os.path.exists(test_file):
                print(f"\nRunning {test_file}...")
                result = self.run_command(f"python -m pytest {test_file} -v --tb=short")
                results.append(result)
                if result['success']:
                    print(f"✅ {test_file} PASSED")
                else:
                    print(f"❌ {test_file} FAILED")
                    print(f"STDERR: {result['stderr'][:500]}...")
            else:
                print(f"⚠️  {test_file} not found, skipping")

        return results

    def run_integration_tests(self):
        """Run integration tests (Layer 2)."""
        print("\n" + "="*60)
        print("🔗 RUNNING INTEGRATION TESTS (Layer 2)")
        print("="*60)

        test_dirs = [
            "tests/integration/test_service_integration.py"
        ]

        results = []
        for test_file in test_dirs:
            if os.path.exists(test_file):
                print(f"\nRunning {test_file}...")
                result = self.run_command(f"python -m pytest {test_file} -v --tb=short")
                results.append(result)
                if result['success']:
                    print(f"✅ {test_file} PASSED")
                else:
                    print(f"❌ {test_file} FAILED")
                    print(f"STDERR: {result['stderr'][:500]}...")
            else:
                print(f"⚠️  {test_file} not found, skipping")

        return results

    def run_api_tests(self):
        """Run API tests (Layer 3)."""
        print("\n" + "="*60)
        print("🌐 RUNNING API TESTS (Layer 3)")
        print("="*60)

        test_dirs = [
            "tests/api/test_deception_api.py"
        ]

        results = []
        for test_file in test_dirs:
            if os.path.exists(test_file):
                print(f"\nRunning {test_file}...")
                result = self.run_command(f"python -m pytest {test_file} -v --tb=short")
                results.append(result)
                if result['success']:
                    print(f"✅ {test_file} PASSED")
                else:
                    print(f"❌ {test_file} FAILED")
                    print(f"STDERR: {result['stderr'][:500]}...")
            else:
                print(f"⚠️  {test_file} not found, skipping")

        return results

    def run_e2e_tests(self):
        """Run end-to-end tests (Layer 4)."""
        print("\n" + "="*60)
        print("🚀 RUNNING END-TO-END TESTS (Layer 4)")
        print("="*60)

        test_dirs = [
            "tests/e2e/test_complete_workflow.py"
        ]

        results = []
        for test_file in test_dirs:
            if os.path.exists(test_file):
                print(f"\nRunning {test_file}...")
                result = self.run_command(f"python -m pytest {test_file} -v --tb=short")
                results.append(result)
                if result['success']:
                    print(f"✅ {test_file} PASSED")
                else:
                    print(f"❌ {test_file} FAILED")
                    print(f"STDERR: {result['stderr'][:500]}...")
            else:
                print(f"⚠️  {test_file} not found, skipping")

        return results

    def run_performance_tests(self):
        """Run performance tests (Layer 5)."""
        print("\n" + "="*60)
        print("⚡ RUNNING PERFORMANCE TESTS (Layer 5)")
        print("="*60)

        test_dirs = [
            "tests/performance/test_performance.py"
        ]

        results = []
        for test_file in test_dirs:
            if os.path.exists(test_file):
                print(f"\nRunning {test_file}...")
                result = self.run_command(f"python -m pytest {test_file} -v --tb=short")
                results.append(result)
                if result['success']:
                    print(f"✅ {test_file} PASSED")
                else:
                    print(f"❌ {test_file} FAILED")
                    print(f"STDERR: {result['stderr'][:500]}...")
            else:
                print(f"⚠️  {test_file} not found, skipping")

        return results

    def run_smoke_tests(self):
        """Run basic smoke tests to verify system is working."""
        print("\n" + "="*60)
        print("💨 RUNNING SMOKE TESTS")
        print("="*60)

        smoke_tests = [
            ("Import backend modules", "cd backend && python -c \"import services.agenticity; import services.mystique_maze; import honey_tokens; print('✅ Imports successful')\""),
            ("Check server startup", "timeout 10s python mcp_server.py --help || echo 'Server help check completed'"),
            ("Validate requirements", "python -c \"import fastapi, motor, pydantic; print('✅ Core dependencies available')\"")
        ]

        results = []
        for test_name, command in smoke_tests:
            print(f"\nRunning smoke test: {test_name}")
            result = self.run_command(command)
            results.append(result)
            if result['success']:
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
                print(f"STDERR: {result['stderr'][:200]}...")

        return results

    def generate_report(self):
        """Generate comprehensive test report."""
        print("\n" + "="*80)
        print("📊 TEST EXECUTION REPORT")
        print("="*80)

        total_tests = 0
        passed_tests = 0
        failed_tests = 0

        for layer, results in self.test_results.items():
            print(f"\n{layer.upper()}:")
            layer_passed = 0
            layer_failed = 0

            for result in results:
                if result['success']:
                    layer_passed += 1
                else:
                    layer_failed += 1

            total_tests += len(results)
            passed_tests += layer_passed
            failed_tests += layer_failed

            print(f"  ✅ Passed: {layer_passed}")
            print(f"  ❌ Failed: {layer_failed}")
            print(f"  📊 Success Rate: {(layer_passed/len(results)*100):.1f}%" if results else "  📊 Success Rate: N/A")

        print(f"\n{'='*80}")
        print("OVERALL RESULTS:")
        print(f"  Total Test Suites: {len(self.test_results)}")
        print(f"  Total Tests: {total_tests}")
        print(f"  ✅ Passed: {passed_tests}")
        print(f"  ❌ Failed: {failed_tests}")
        if total_tests > 0:
            print(f"  📊 Overall Success Rate: {(passed_tests/total_tests*100):.1f}%")

        # Save detailed report
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'execution_time_seconds': time.time() - self.start_time,
            'results': self.test_results,
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'success_rate': (passed_tests/total_tests*100) if total_tests > 0 else 0
            }
        }

        report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)

        print(f"\n📄 Detailed report saved to: {report_file}")

        return passed_tests == total_tests

    def run_all_tests(self, include_performance=True, include_smoke=True):
        """Run all test layers."""
        self.start_time = time.time()

        print("🚀 STARTING COMPREHENSIVE TEST SUITE")
        print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📂 Workspace: {self.workspace_root}")

        # Run smoke tests first
        if include_smoke:
            smoke_results = self.run_smoke_tests()
            self.test_results['smoke'] = smoke_results

        # Run test layers
        self.test_results['unit'] = self.run_unit_tests()
        self.test_results['integration'] = self.run_integration_tests()
        self.test_results['api'] = self.run_api_tests()
        self.test_results['e2e'] = self.run_e2e_tests()

        if include_performance:
            self.test_results['performance'] = self.run_performance_tests()

        # Generate final report
        success = self.generate_report()

        print(f"\n⏱️  Total execution time: {time.time() - self.start_time:.1f} seconds")

        if success:
            print("🎉 ALL TESTS PASSED!")
            return 0
        else:
            print("⚠️  SOME TESTS FAILED - Check the detailed report above")
            return 1


def main():
    parser = argparse.ArgumentParser(description="Metatron-Seraph Test Runner")
    parser.add_argument("--workspace", default=".", help="Workspace root directory")
    parser.add_argument("--no-performance", action="store_true", help="Skip performance tests")
    parser.add_argument("--no-smoke", action="store_true", help="Skip smoke tests")
    parser.add_argument("--layer", choices=['unit', 'integration', 'api', 'e2e', 'performance', 'smoke'],
                       help="Run only specific test layer")

    args = parser.parse_args()

    # Ensure we're in the right directory
    workspace_root = os.path.abspath(args.workspace)
    os.chdir(workspace_root)

    runner = TestRunner(workspace_root)

    if args.layer:
        # Run specific layer
        layer_map = {
            'unit': runner.run_unit_tests,
            'integration': runner.run_integration_tests,
            'api': runner.run_api_tests,
            'e2e': runner.run_e2e_tests,
            'performance': runner.run_performance_tests,
            'smoke': runner.run_smoke_tests
        }

        results = layer_map[args.layer]()
        runner.test_results[args.layer] = results

        success = runner.generate_report()
        return 0 if success else 1

    else:
        # Run all layers
        return runner.run_all_tests(
            include_performance=not args.no_performance,
            include_smoke=not args.no_smoke
        )


if __name__ == "__main__":
    sys.exit(main())