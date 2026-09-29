"""
MCP (Model Context Protocol) Client - Integrate external tools via MCP servers.

This module handles:
- Starting and managing MCP server processes
- Discovering available tools from MCP servers
- Calling tools and passing results back to LLM

Official MCP Servers:
- filesystem: Read/write files and directories
- memory: In-memory key-value store for state
- fetch: HTTP requests to URLs
- browser: Browser automation (requires playwright)

Example usage:
    mcp_client = MCPClient()
    await mcp_client.connect_server("filesystem")
    
    tools = await mcp_client.list_tools("filesystem")
    
    result = await mcp_client.call_tool(
        server="filesystem",
        tool_name="read_file",
        arguments={"path": "config.json"}
    )
"""

import json
import logging
import subprocess
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, AsyncIterator
from dataclasses import dataclass, asdict

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """Represents an MCP tool."""
    name: str
    description: str
    server: str
    input_schema: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolResult:
    """Result from calling an MCP tool."""
    success: bool
    output: Any
    error: Optional[str] = None
    server: Optional[str] = None


class MCPClient:
    """Client for interacting with MCP servers."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize MCP client.
        
        Args:
            config_path: Path to MCP configuration JSON (default from settings)
        """
        self.config_path = Path(config_path or settings.mcp_config_path)
        self.servers: Dict[str, Any] = {}
        self.tools: Dict[str, List[Tool]] = {}  # server_name -> [tools]
        self.processes: Dict[str, subprocess.Popen] = {}
        self.enabled = settings.mcp_enabled
        
        if not self.enabled:
            logger.info("MCP is disabled")
            return
        
        self._load_config()
        logger.info(f"MCPClient initialized with {len(self.servers)} servers")
    
    def _load_config(self):
        """Load MCP servers configuration from JSON file."""
        if not self.config_path.exists():
            logger.warning(f"MCP config not found at {self.config_path}")
            return
        
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
            
            self.servers = config.get("servers", {})
            logger.info(f"Loaded {len(self.servers)} MCP servers from config")
        
        except Exception as e:
            logger.error(f"Error loading MCP config: {e}")
            self.servers = {}
    
    async def connect_server(self, server_name: str) -> bool:
        """
        Start and connect to an MCP server.
        
        Args:
            server_name: Name of server in config
        
        Returns:
            True if connection successful, False otherwise
        """
        if not self.enabled:
            logger.debug("MCP disabled, skipping server connection")
            return False
        
        if server_name not in self.servers:
            logger.error(f"Server '{server_name}' not found in config")
            return False
        
        server_config = self.servers[server_name]
        
        if not server_config.get("enabled", True):
            logger.info(f"Server '{server_name}' is disabled in config")
            return False
        
        try:
            # In a real implementation, this would:
            # 1. Start the server subprocess
            # 2. Connect to it via stdio or SSE
            # 3. Discover available tools
            
            # For now, we mock tool discovery
            logger.info(f"Connecting to MCP server: {server_name}")
            
            # Initialize tool list for this server
            self.tools[server_name] = await self._discover_tools(server_name)
            
            logger.info(f"Connected to {server_name}: {len(self.tools.get(server_name, []))} tools available")
            return True
        
        except Exception as e:
            logger.error(f"Error connecting to server {server_name}: {e}")
            return False
    
    async def _discover_tools(self, server_name: str) -> List[Tool]:
        """Discover available tools from a server."""
        # This would normally communicate with the MCP server
        # For demo, return mock tools
        
        if server_name == "filesystem":
            return [
                Tool(
                    name="read_file",
                    description="Read contents of a file",
                    server=server_name,
                    input_schema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path to read"}
                        },
                        "required": ["path"]
                    }
                ),
                Tool(
                    name="write_file",
                    description="Write contents to a file",
                    server=server_name,
                    input_schema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"}
                        },
                        "required": ["path", "content"]
                    }
                ),
                Tool(
                    name="list_directory",
                    description="List contents of a directory",
                    server=server_name,
                    input_schema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Directory path"}
                        },
                        "required": ["path"]
                    }
                ),
            ]
        
        elif server_name == "memory":
            return [
                Tool(
                    name="set",
                    description="Store a key-value pair in memory",
                    server=server_name,
                    input_schema={
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "string"}
                        },
                        "required": ["key", "value"]
                    }
                ),
                Tool(
                    name="get",
                    description="Retrieve a value from memory",
                    server=server_name,
                    input_schema={
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"}
                        },
                        "required": ["key"]
                    }
                ),
            ]
        
        elif server_name == "fetch":
            return [
                Tool(
                    name="fetch_url",
                    description="Fetch content from a URL",
                    server=server_name,
                    input_schema={
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "URL to fetch"},
                            "method": {"type": "string", "default": "GET"}
                        },
                        "required": ["url"]
                    }
                ),
            ]
        
        return []
    
    async def call_tool(
        self,
        server: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> ToolResult:
        """
        Call a tool from an MCP server.
        
        Args:
            server: Server name
            tool_name: Tool name
            arguments: Tool arguments (dict)
        
        Returns:
            ToolResult with success status and output
        """
        if not self.enabled:
            return ToolResult(
                success=False,
                output=None,
                error="MCP is disabled"
            )
        
        if server not in self.tools:
            return ToolResult(
                success=False,
                output=None,
                error=f"Server '{server}' not connected. Call connect_server() first."
            )
        
        # Find tool in server
        tool = next((t for t in self.tools[server] if t.name == tool_name), None)
        if not tool:
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool '{tool_name}' not found in server '{server}'"
            )
        
        try:
            # In a real implementation, this would send a request to the MCP server
            # For now, we'll mock the response
            
            logger.info(f"Calling tool: {server}/{tool_name} with args: {arguments}")
            
            # Mock tool execution
            result = await self._execute_tool_mock(server, tool_name, arguments)
            
            return ToolResult(
                success=True,
                output=result,
                server=server
            )
        
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                server=server
            )
    
    async def _execute_tool_mock(
        self,
        server: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """Mock tool execution for demonstration."""
        # This would normally communicate with the actual MCP server
        
        if server == "filesystem" and tool_name == "read_file":
            path = arguments.get("path", "")
            try:
                with open(path, "r") as f:
                    return f.read()
            except FileNotFoundError:
                return f"File not found: {path}"
        
        elif server == "memory" and tool_name == "set":
            # In-memory storage would be implemented here
            return {"status": "stored", "key": arguments.get("key")}
        
        elif server == "memory" and tool_name == "get":
            # Would return stored value
            return {"value": None, "key": arguments.get("key")}
        
        elif server == "fetch" and tool_name == "fetch_url":
            url = arguments.get("url")
            return f"Would fetch: {url}"
        
        return {"status": "tool executed"}
    
    async def disconnect_server(self, server_name: str) -> bool:
        """Disconnect from an MCP server."""
        if server_name in self.processes:
            try:
                self.processes[server_name].terminate()
                self.processes[server_name].wait(timeout=5)
                del self.processes[server_name]
                logger.info(f"Disconnected from server: {server_name}")
                return True
            except Exception as e:
                logger.error(f"Error disconnecting from {server_name}: {e}")
                return False
        return True
    
    async def disconnect_all(self):
        """Disconnect from all servers."""
        for server_name in list(self.processes.keys()):
            await self.disconnect_server(server_name)
    
    def list_servers(self) -> Dict[str, Any]:
        """Get list of configured servers."""
        return {
            name: {
                "enabled": config.get("enabled", True),
                "tools": len(self.tools.get(name, []))
            }
            for name, config in self.servers.items()
        }
    
    def list_tools(self, server_name: Optional[str] = None) -> Dict[str, List[Tool]]:
        """
        List available tools.
        
        Args:
            server_name: Specific server (None = all)
        
        Returns:
            Dict of server -> list of tools
        """
        if server_name:
            return {
                server_name: self.tools.get(server_name, [])
            }
        return self.tools
    
    async def auto_connect(self):
        """Auto-connect to servers specified in settings."""
        if not self.enabled:
            return
        
        for server_name in settings.mcp_servers_to_connect:
            logger.info(f"Auto-connecting to server: {server_name}")
            await self.connect_server(server_name)
    
    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """
        Get tools in a format suitable for passing to LLM.
        
        Returns:
            List of tool dicts compatible with OpenAI functions format
        """
        tools = []
        for server_name, server_tools in self.tools.items():
            for tool in server_tools:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": f"{server_name}_{tool.name}",
                        "description": tool.description,
                        "parameters": tool.input_schema
                    }
                })
        return tools
