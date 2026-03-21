"""
Command Execution - Run Shell Commands
"""
import asyncio
import subprocess
from typing import Dict, Any
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class CommandExecutor:
    """
    Executes shell commands with timeout and error handling
    """

    async def run_command(
        self,
        command: str,
        timeout: int = 30,
        shell: bool = True
    ) -> Dict[str, Any]:
        """
        Run a shell command asynchronously

        Args:
            command: Command to execute
            timeout: Timeout in seconds
            shell: Whether to use shell

        Returns:
            Dictionary with stdout, stderr, exit_code
        """
        logger.info(f"Executing command: {command}")

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=shell
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )

                result = {
                    "stdout": stdout.decode('utf-8', errors='replace'),
                    "stderr": stderr.decode('utf-8', errors='replace'),
                    "exit_code": process.returncode
                }

                logger.debug(f"Command completed with exit code: {process.returncode}")
                return result

            except asyncio.TimeoutError:
                process.kill()
                logger.warning(f"Command timed out after {timeout}s")
                return {
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout} seconds",
                    "exit_code": -1
                }

        except Exception as e:
            logger.error(f"Command execution error: {e}", exc_info=True)
            return {
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1
            }
