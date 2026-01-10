"""E2B Sandbox tools for secure code execution."""

import time
from typing import Dict, Optional

from e2b_code_interpreter import Sandbox
from e2b.sandbox.commands.command_handle import CommandExitException
from agnt5 import tool, Context

from coding_agent_agnt5.config import config


class E2BSandboxTools:
    """E2B Sandbox integration tools for secure code execution.

    Provides methods to:
    - Create sandboxes
    - Write/read files
    - Execute shell commands
    """

    @staticmethod
    @tool(auto_schema=True)
    async def create_sandbox(
        ctx: Context,
        sandbox_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        envs: Optional[Dict[str, str]] = None,
    ) -> dict:
        """Create a new E2B sandbox for code execution.

        Args:
            ctx: Context for logging
            sandbox_id: Optional existing sandbox ID (for reconnection)
            metadata: Custom metadata tags for the sandbox
            envs: Environment variables for the sandbox

        Returns:
            dict: Contains 'status' message and 'sandbox_id'
                  Or 'error' if creation failed
        """
        try:
            # If sandbox_id provided, try to reconnect
            if sandbox_id:
                ctx.logger.info(f"Reconnecting to existing sandbox: {sandbox_id}")
                try:
                    sandbox = Sandbox.connect(sandbox_id)
                    return {
                        "status": f"Reconnected to sandbox: {sandbox_id}",
                        "sandbox_id": sandbox_id,
                    }
                except Exception as e:
                    ctx.logger.warning(
                        f"Reconnection failed: {e}, creating new sandbox"
                    )

            # Create new sandbox
            ctx.logger.info("Creating new E2B sandbox")

            sandbox_options = {}
            if metadata:
                sandbox_options["metadata"] = metadata
            if envs:
                sandbox_options["envs"] = envs

            e2b_api_key = config.E2B_API_KEY
            if e2b_api_key:
                sandbox_options["api_key"] = e2b_api_key
            else:
                ctx.logger.warning("No E2B_API_KEY found in config")

            sandbox = Sandbox.create(**sandbox_options)
            sandbox_id = sandbox.sandbox_id

            ctx.logger.info(f"✅ Sandbox created: {sandbox_id}")

            return {
                "status": f"Sandbox created successfully: {sandbox_id}",
                "sandbox_id": sandbox_id,
            }

        except Exception as e:
            ctx.logger.error(f"Failed to create sandbox: {e}")
            return {"error": f"Sandbox creation failed: {str(e)}"}

    @staticmethod
    @tool(auto_schema=True)
    async def write_file(
        ctx: Context,
        sandbox_id: str,
        path: str,
        content: str
    ) -> str:
        """Write a file to the E2B sandbox.

        Args:
            ctx: Context for logging
            sandbox_id: E2B sandbox identifier
            path: File path to write (e.g., "main.py", "test.py")
            content: File content as string

        Returns:
            str: Success message or error description
        """
        if not sandbox_id:
            return "Error: sandbox_id is required"

        try:
            ctx.logger.debug(f"Writing file: {path} ({len(content)} chars)")

            sandbox = Sandbox.connect(sandbox_id)
            sandbox.files.write(path, content)

            ctx.logger.info(f"✅ File written: {path}")
            return f"File written successfully: {path}"

        except Exception as e:
            ctx.logger.error(f"Failed to write file {path}: {e}")
            return f"Error writing file {path}: {str(e)}"

    @staticmethod
    @tool(auto_schema=True)
    async def read_file(
        ctx: Context,
        sandbox_id: str,
        path: str
    ) -> str:
        """Read a file from the E2B sandbox.

        Args:
            ctx: Context for logging
            sandbox_id: E2B sandbox identifier
            path: File path to read

        Returns:
            str: File content or error message
        """
        if not sandbox_id:
            return "Error: sandbox_id is required"

        try:
            ctx.logger.debug(f"Reading file: {path}")

            sandbox = Sandbox.connect(sandbox_id)
            content = sandbox.files.read(path)

            ctx.logger.info(f"✅ File read: {path} ({len(content)} chars)")
            return f"File content from {path}:\n{content}"

        except Exception as e:
            ctx.logger.error(f"Failed to read file {path}: {e}")
            return f"Error reading file {path}: {str(e)}"

    @staticmethod
    @tool(auto_schema=True)
    async def list_files(
        ctx: Context,
        sandbox_id: str,
        path: str = "/"
    ) -> str:
        """List files and directories in the sandbox.

        Args:
            ctx: Context for logging
            sandbox_id: E2B sandbox identifier
            path: Directory path to list (default: "/")

        Returns:
            str: Formatted list of files and directories
        """
        if not sandbox_id:
            return "Error: sandbox_id is required"

        try:
            sandbox = Sandbox.connect(sandbox_id)
            file_list = sandbox.files.list(path)

            result = f"Files and directories in {path}:\n"
            for file_info in file_list:
                file_type = "DIR" if file_info.type == "dir" else "FILE"
                result += f"  {file_type}: {file_info.name}\n"

            ctx.logger.info(f"Listed {len(file_list)} items in {path}")
            return result

        except Exception as e:
            ctx.logger.error(f"Failed to list files in {path}: {e}")
            return f"Error listing files: {str(e)}"

    @staticmethod
    @tool(auto_schema=True)
    async def delete_file(
        ctx: Context,
        sandbox_id: str,
        path: str
    ) -> str:
        """Delete a file or directory from the sandbox.

        Args:
            ctx: Context for logging
            sandbox_id: E2B sandbox identifier
            path: Path to delete

        Returns:
            str: Success or error message
        """
        if not sandbox_id:
            return "Error: sandbox_id is required"

        try:
            sandbox = Sandbox.connect(sandbox_id)
            sandbox.files.remove(path)

            ctx.logger.info(f"✅ Deleted: {path}")
            return f"Successfully deleted: {path}"

        except Exception as e:
            ctx.logger.error(f"Failed to delete {path}: {e}")
            return f"Error deleting {path}: {str(e)}"

    @staticmethod
    @tool(auto_schema=True)
    async def run_command(
        ctx: Context,
        sandbox_id: str,
        command: str,
        working_directory: Optional[str] = None,
        timeout_ms: int = 30000,
        capture_output: bool = True,
    ) -> dict:
        """Run a shell command in the E2B sandbox.

        This is the primary method for executing code and tests.

        Args:
            ctx: Context for logging
            sandbox_id: E2B sandbox identifier
            command: Shell command to execute (e.g., "pytest test.py")
            working_directory: Working directory for command execution
            timeout_ms: Command timeout in milliseconds (default: 30s)
            capture_output: Whether to capture stdout/stderr (default: True)

        Returns:
            dict: Execution result with keys:
                - exit_code: int (0 for success, non-zero for failure)
                - stdout: str (standard output)
                - stderr: str (standard error)
                - error: str (error message if any)
                - success: bool (True if exit_code == 0)
                - execution_time_ms: float (execution time)
        """
        if not sandbox_id:
            return {
                "exit_code": None,
                "stdout": "",
                "stderr": "Error: sandbox_id is required",
                "error": "No sandbox_id",
                "success": False,
                "execution_time_ms": 0,
            }

        try:
            ctx.logger.info(f"🚀 Running command: {command}")

            sandbox = Sandbox.connect(sandbox_id)
            start_time = time.time()

            run_options = {
                "timeout": timeout_ms // 1000,  # Convert ms to seconds
                "background": False,
            }
            if working_directory:
                run_options["cwd"] = working_directory

            try:
                # Run command - handle both success and CommandExitException
                result = sandbox.commands.run(command, **run_options)
                exit_code = result.exit_code
                stdout = result.stdout
                stderr = result.stderr
                error = result.error

            except CommandExitException as e:
                # Non-zero exit codes raise this exception
                exit_code = e.exit_code
                stdout = e.stdout
                stderr = e.stderr
                error = e.error
                ctx.logger.debug(f"Command failed with exit code {exit_code}")

            execution_time = (time.time() - start_time) * 1000  # ms

            # Log result summary
            if exit_code == 0:
                ctx.logger.info(f"✅ Command succeeded ({execution_time:.0f}ms)")
            else:
                ctx.logger.warning(
                    f"❌ Command failed with exit code {exit_code} ({execution_time:.0f}ms)"
                )

            return {
                "exit_code": exit_code,
                "stdout": stdout if capture_output else "",
                "stderr": stderr if capture_output else "",
                "error": error,
                "success": exit_code == 0,
                "execution_time_ms": execution_time,
            }

        except Exception as e:
            # Unexpected errors (connection issues, SDK errors, etc.)
            ctx.logger.error(f"Unexpected error running command: {e}")
            return {
                "exit_code": None,
                "stdout": "",
                "stderr": str(e),
                "error": str(e),
                "success": False,
                "execution_time_ms": 0,
            }

    @staticmethod
    @tool(auto_schema=True)
    async def run_code(
        ctx: Context,
        sandbox_id: str,
        code: str,
        language: str = "python",
        envs: Optional[Dict[str, str]] = None,
        timeout_ms: int = 60000,
    ) -> str:
        """Run code directly in the E2B sandbox (alternative to run_command).

        Args:
            ctx: Context for logging
            sandbox_id: E2B sandbox identifier
            code: Code to execute
            language: Programming language ("python", "javascript", "typescript")
            envs: Environment variables for execution
            timeout_ms: Timeout in milliseconds

        Returns:
            str: JSON string with execution results
        """
        if not sandbox_id:
            return '{"error": "sandbox_id is required"}'

        try:
            ctx.logger.info(f"Running {language} code ({len(code)} chars)")

            sandbox = Sandbox.connect(sandbox_id)

            run_options = {
                "language": language,
                "timeout": timeout_ms / 1000,  # Convert to seconds
            }
            if envs:
                run_options["envs"] = envs

            execution = sandbox.run_code(code, **run_options)

            ctx.logger.info("✅ Code execution completed")
            return execution.to_json()

        except Exception as e:
            ctx.logger.error(f"Code execution failed: {e}")
            return f'{{"error": "{str(e)}"}}'