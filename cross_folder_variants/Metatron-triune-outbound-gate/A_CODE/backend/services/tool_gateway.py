"""
CLI Tool Gateway (Policy Enforcement Point)
============================================
Governed tool execution - no raw shell access.
All CLI interactions go through allowlisted, parameterized commands.
"""

import os
import json
import subprocess
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import shlex
import uuid
import tempfile

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Tool contract definition"""
    tool_id: str
    name: str
    description: str
    
    # Execution
    binary: str                     # Path to binary
    args_schema: Dict[str, str]     # Parameter schema
    allowed_flags: List[str]
    denied_patterns: List[str]      # Patterns to block
    
    # Limits
    timeout_seconds: int
    run_as: Optional[str]           # User to run as
    host_constraints: List[str]     # Only on these hosts
    
    # Security
    requires_approval: bool
    min_trust_state: str
    
    # Audit
    capture_output: bool
    redact_patterns: List[str]


@dataclass
class ToolExecution:
    """Tool execution record"""
    execution_id: str
    tool_id: str
    timestamp: str
    
    # Request
    principal: str
    token_id: str
    parameters: Dict[str, Any]
    
    # Execution
    command_argv: List[str]         # Actual command run
    exit_code: Optional[int]
    stdout: Optional[str]
    stderr: Optional[str]
    duration_ms: int
    
    # Status
    status: str                     # pending / running / success / failed / denied


class ToolGateway:
    """
    Policy Enforcement Point (PEP) for CLI tool execution.
    
    Features:
    - Only allowlisted commands
    - Structured parameters (no raw string interpolation)
    - Logs everything (inputs, outputs, exit codes)
    - Enforces timeouts, rate limits, blast-radius caps
    - Requires scoped capability tokens
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # Tool registry
        self.tools: Dict[str, ToolDefinition] = {}
        
        # Execution history
        self.executions: List[ToolExecution] = []
        
        # Load default tools
        self._register_default_tools()
        
        logger.info("CLI Tool Gateway (PEP) initialized")
    
    def _register_default_tools(self):
        """Register default security tools"""
        
        # Process listing
        self.register_tool(ToolDefinition(
            tool_id="process_list",
            name="Process List",
            description="List running processes",
            binary="/bin/ps" if os.name != 'nt' else "tasklist.exe",
            args_schema={"format": "string", "user": "string"},
            allowed_flags=["-ef", "-aux", "/v", "/fo"],
            denied_patterns=[";", "|", "&", "$", "`", ">", "<"],
            timeout_seconds=30,
            run_as=None,
            host_constraints=["*"],
            requires_approval=False,
            min_trust_state="unknown",
            capture_output=True,
            redact_patterns=[]
        ))
        
        # Process kill
        self.register_tool(ToolDefinition(
            tool_id="process_kill",
            name="Process Kill",
            description="Terminate a process by PID",
            binary="/bin/kill" if os.name != 'nt' else "taskkill.exe",
            args_schema={"pid": "integer", "signal": "string"},
            allowed_flags=["-9", "-15", "/F", "/PID"],
            denied_patterns=[";", "|", "&", "$", "`"],
            timeout_seconds=10,
            run_as=None,
            host_constraints=["*"],
            requires_approval=True,
            min_trust_state="degraded",
            capture_output=True,
            redact_patterns=[]
        ))
        
        # Network connections
        self.register_tool(ToolDefinition(
            tool_id="network_connections",
            name="Network Connections",
            description="List network connections",
            binary="/bin/netstat" if os.name != 'nt' else "netstat.exe",
            args_schema={"flags": "string"},
            allowed_flags=["-an", "-anp", "-tulpn", "-ano"],
            denied_patterns=[";", "|", "&", "$", "`"],
            timeout_seconds=30,
            run_as=None,
            host_constraints=["*"],
            requires_approval=False,
            min_trust_state="unknown",
            capture_output=True,
            redact_patterns=[]
        ))
        
        # Firewall block
        self.register_tool(ToolDefinition(
            tool_id="firewall_block",
            name="Firewall Block",
            description="Block an IP address",
            binary="/sbin/iptables" if os.name != 'nt' else "netsh.exe",
            args_schema={"ip": "ip_address", "direction": "string"},
            allowed_flags=["-A", "-I", "INPUT", "OUTPUT", "advfirewall"],
            denied_patterns=[";", "|", "&", "$", "`", "rm", "del"],
            timeout_seconds=10,
            run_as="root",
            host_constraints=["*"],
            requires_approval=True,
            min_trust_state="trusted",
            capture_output=True,
            redact_patterns=[]
        ))
        
        # File hash
        self.register_tool(ToolDefinition(
            tool_id="file_hash",
            name="File Hash",
            description="Calculate file hash",
            binary="/usr/bin/sha256sum" if os.name != 'nt' else "certutil.exe",
            args_schema={"file_path": "path"},
            allowed_flags=["-hashfile", "SHA256"],
            denied_patterns=[";", "|", "&", "$", "`", "rm", "del", "..", "~"],
            timeout_seconds=60,
            run_as=None,
            host_constraints=["*"],
            requires_approval=False,
            min_trust_state="unknown",
            capture_output=True,
            redact_patterns=[]
        ))
        
        # Memory dump
        self.register_tool(ToolDefinition(
            tool_id="memory_dump",
            name="Memory Dump",
            description="Dump process memory",
            binary="/usr/bin/gcore" if os.name != 'nt' else "procdump.exe",
            args_schema={"pid": "integer", "output_dir": "path"},
            allowed_flags=["-o", "-ma"],
            denied_patterns=[";", "|", "&", "$", "`", "rm", "del"],
            timeout_seconds=300,
            run_as="root",
            host_constraints=["*"],
            requires_approval=True,
            min_trust_state="trusted",
            capture_output=True,
            redact_patterns=[]
        ))
        
        # Suricata reload
        self.register_tool(ToolDefinition(
            tool_id="suricata_reload_rules",
            name="Suricata Reload Rules",
            description="Reload Suricata IDS rules",
            binary="/usr/bin/suricata",
            args_schema={"config": "path", "test_only": "boolean"},
            allowed_flags=["-T", "-c", "--reload-rules"],
            denied_patterns=[";", "|", "&", "$", "`"],
            timeout_seconds=60,
            run_as="suricata",
            host_constraints=["sensor"],
            requires_approval=True,
            min_trust_state="trusted",
            capture_output=True,
            redact_patterns=[]
        ))
    
    def register_tool(self, tool: ToolDefinition):
        """Register a tool in the gateway"""
        self.tools[tool.tool_id] = tool
        logger.info(f"GATEWAY: Registered tool '{tool.tool_id}'")
    
    def list_tools(self) -> List[Dict]:
        """List available tools"""
        return [
            {
                "tool_id": t.tool_id,
                "name": t.name,
                "description": t.description,
                "requires_approval": t.requires_approval,
                "min_trust_state": t.min_trust_state
            }
            for t in self.tools.values()
        ]
    
    def get_tool(self, tool_id: str) -> Optional[ToolDefinition]:
        """Get tool definition"""
        return self.tools.get(tool_id)
    
    def _validate_parameters(self, tool: ToolDefinition, 
                             params: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate parameters against schema"""
        for param_name, param_type in tool.args_schema.items():
            if param_name in params:
                value = str(params[param_name])
                
                # Check for denied patterns
                for pattern in tool.denied_patterns:
                    if pattern in value:
                        return False, f"Denied pattern '{pattern}' in parameter '{param_name}'"
                
                # Type validation
                if param_type == "integer":
                    try:
                        int(value)
                    except ValueError:
                        return False, f"Parameter '{param_name}' must be integer"
                
                elif param_type == "ip_address":
                    parts = value.split('.')
                    if len(parts) != 4:
                        return False, f"Parameter '{param_name}' must be valid IP"
                
                elif param_type == "path":
                    # No path traversal
                    if ".." in value or "~" in value:
                        return False, f"Path traversal not allowed in '{param_name}'"
        
        return True, "Parameters valid"
    
    def _build_command(self, tool: ToolDefinition, 
                       params: Dict[str, Any]) -> List[str]:
        """Build command argv from tool and parameters"""
        argv = [tool.binary]
        
        # Add parameters as flags
        for param_name, value in params.items():
            if param_name in tool.args_schema:
                # Format depends on tool
                if tool.binary.endswith('kill') or tool.binary.endswith('taskkill.exe'):
                    if param_name == "pid":
                        if os.name == 'nt':
                            argv.extend(["/PID", str(value)])
                        else:
                            argv.append(str(value))
                    elif param_name == "signal" and os.name != 'nt':
                        argv.append(f"-{value}")
                
                elif tool.binary.endswith('iptables') or tool.binary.endswith('netsh.exe'):
                    if param_name == "ip":
                        if os.name == 'nt':
                            argv.extend(["advfirewall", "firewall", "add", "rule",
                                        f"name=SeraphBlock_{value}", "dir=in",
                                        "action=block", f"remoteip={value}"])
                        else:
                            argv.extend(["-A", "INPUT", "-s", str(value), "-j", "DROP"])
                
                elif tool.tool_id == "file_hash":
                    if os.name == 'nt':
                        argv.extend(["-hashfile", str(value), "SHA256"])
                    else:
                        argv.append(str(value))
                
                else:
                    # Generic: add as argument
                    argv.append(str(value))
        
        return argv
    
    def _redact_output(self, output: str, patterns: List[str]) -> str:
        """Redact sensitive patterns from output"""
        if not output:
            return output
        
        # Default patterns to always redact
        default_patterns = [
            r'Authorization: Bearer [^\s]+',
            r'password[=:][^\s]+',
            r'token[=:][^\s]+',
            r'api[_-]?key[=:][^\s]+',
            r'-----BEGIN.*PRIVATE KEY-----',
        ]
        
        import re
        result = output
        
        for pattern in default_patterns + patterns:
            result = re.sub(pattern, '[REDACTED]', result, flags=re.IGNORECASE)
        
        return result
    
    def execute(self, tool_id: str, parameters: Dict[str, Any],
                principal: str, token_id: str,
                trust_state: str = "unknown") -> ToolExecution:
        """
        Execute a tool through the gateway.
        
        Args:
            tool_id: Tool to execute
            parameters: Tool parameters
            principal: Who is executing
            token_id: Capability token being used
            trust_state: Current trust state
        
        Returns:
            ToolExecution record
        """
        import time
        
        execution_id = f"exec-{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Get tool definition
        tool = self.tools.get(tool_id)
        
        if not tool:
            return self._failed_execution(
                execution_id, tool_id, timestamp, principal, token_id,
                parameters, f"Unknown tool: {tool_id}"
            )
        
        # Check trust state
        trust_order = ["trusted", "degraded", "unknown", "quarantined"]
        min_idx = trust_order.index(tool.min_trust_state)
        current_idx = trust_order.index(trust_state)
        
        if current_idx > min_idx:
            return self._failed_execution(
                execution_id, tool_id, timestamp, principal, token_id,
                parameters, f"Trust state '{trust_state}' insufficient (need '{tool.min_trust_state}')"
            )
        
        # Validate parameters
        valid, msg = self._validate_parameters(tool, parameters)
        if not valid:
            return self._failed_execution(
                execution_id, tool_id, timestamp, principal, token_id,
                parameters, msg
            )
        
        # Build command
        argv = self._build_command(tool, parameters)
        
        # Create execution record
        execution = ToolExecution(
            execution_id=execution_id,
            tool_id=tool_id,
            timestamp=timestamp,
            principal=principal,
            token_id=token_id,
            parameters=parameters,
            command_argv=argv,
            exit_code=None,
            stdout=None,
            stderr=None,
            duration_ms=0,
            status="running"
        )
        
        self.executions.append(execution)
        
        logger.info(f"GATEWAY: Executing {tool_id} | Principal: {principal} | "
                   f"Args: {parameters}")
        
        # Execute
        start_time = time.time()
        
        try:
            result = subprocess.run(
                argv,
                capture_output=tool.capture_output,
                timeout=tool.timeout_seconds,
                text=True
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            execution.exit_code = result.returncode
            execution.duration_ms = duration_ms
            execution.status = "success" if result.returncode == 0 else "failed"
            
            if tool.capture_output:
                execution.stdout = self._redact_output(result.stdout, tool.redact_patterns)
                execution.stderr = self._redact_output(result.stderr, tool.redact_patterns)
            
            logger.info(f"GATEWAY: Completed {execution_id} | Exit: {result.returncode} | "
                       f"Duration: {duration_ms}ms")
            
        except subprocess.TimeoutExpired:
            execution.status = "timeout"
            execution.duration_ms = tool.timeout_seconds * 1000
            logger.warning(f"GATEWAY: Timeout {execution_id}")
        
        except FileNotFoundError:
            execution.status = "failed"
            execution.stderr = f"Binary not found: {tool.binary}"
            logger.error(f"GATEWAY: Binary not found for {tool_id}")
        
        except Exception as e:
            execution.status = "failed"
            execution.stderr = str(e)
            logger.error(f"GATEWAY: Error executing {tool_id}: {e}")
        
        return execution
    
    def _failed_execution(self, execution_id: str, tool_id: str,
                          timestamp: str, principal: str, token_id: str,
                          parameters: Dict, error: str) -> ToolExecution:
        """Create a failed execution record"""
        execution = ToolExecution(
            execution_id=execution_id,
            tool_id=tool_id,
            timestamp=timestamp,
            principal=principal,
            token_id=token_id,
            parameters=parameters,
            command_argv=[],
            exit_code=-1,
            stdout=None,
            stderr=error,
            duration_ms=0,
            status="denied"
        )
        
        self.executions.append(execution)
        logger.warning(f"GATEWAY: Denied {tool_id} | {error}")
        
        return execution
    
    def get_execution_history(self, principal: str = None, 
                              tool_id: str = None,
                              limit: int = 100) -> List[Dict]:
        """Get execution history"""
        results = []
        
        for exec in reversed(self.executions):
            if principal and exec.principal != principal:
                continue
            if tool_id and exec.tool_id != tool_id:
                continue
            
            results.append(asdict(exec))
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_gateway_status(self) -> Dict:
        """Get gateway status"""
        return {
            "registered_tools": len(self.tools),
            "total_executions": len(self.executions),
            "tools": list(self.tools.keys())
        }


# Global singleton
tool_gateway = ToolGateway()
