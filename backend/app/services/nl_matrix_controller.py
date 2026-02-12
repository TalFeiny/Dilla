"""
NL Matrix Controller
Natural language → matrix actions (columns, filters, computed columns)
"""

import logging
from typing import Dict, Any, Optional

from app.services.matrix_query_orchestrator import MatrixQueryOrchestrator

logger = logging.getLogger(__name__)


class NLMatrixController:
    """Controls matrix via natural language commands"""
    
    def __init__(self):
        self.matrix_orchestrator = MatrixQueryOrchestrator()
    
    async def process_nl_command(
        self,
        command: str,
        fund_id: Optional[str] = None,
        portfolio_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a natural language matrix command
        
        Args:
            command: Natural language command (e.g., "show ARR and burn rate")
            fund_id: Optional fund ID
            portfolio_id: Optional portfolio ID
            
        Returns:
            Dict with columns, rows, cellUpdates
        """
        logger.info(f"Processing NL matrix command: {command}")
        
        # TODO: Use LLM to parse command into structured intent
        intent = self._parse_intent(command)
        
        # Map intent to matrix actions
        if intent["type"] == "show_columns":
            return await self._handle_show_columns(intent, fund_id, portfolio_id)
        elif intent["type"] == "add_column":
            return await self._handle_add_column(intent, fund_id, portfolio_id)
        elif intent["type"] == "update_cells":
            return await self._handle_update_cells(intent, fund_id, portfolio_id)
        else:
            return {
                "columns": [],
                "rows": [],
                "cellUpdates": []
            }
    
    def _parse_intent(self, command: str) -> Dict[str, Any]:
        """Parse natural language into structured intent"""
        # TODO: Use LLM to parse
        command_lower = command.lower()
        
        if "show" in command_lower or "display" in command_lower:
            return {
                "type": "show_columns",
                "columns": self._extract_column_names(command)
            }
        elif "add" in command_lower or "create" in command_lower:
            return {
                "type": "add_column",
                "column_name": self._extract_column_name(command),
                "column_type": "computed"
            }
        elif "update" in command_lower or "set" in command_lower:
            return {
                "type": "update_cells",
                "updates": []
            }
        else:
            return {"type": "unknown"}
    
    def _extract_column_names(self, command: str) -> List[str]:
        """Extract column names from command"""
        # TODO: Implement proper extraction
        columns = []
        if "arr" in command.lower():
            columns.append("ARR")
        if "burn" in command.lower():
            columns.append("burn_rate")
        if "valuation" in command.lower():
            columns.append("valuation")
        return columns
    
    def _extract_column_name(self, command: str) -> str:
        """Extract column name from add/create command"""
        # TODO: Implement proper extraction
        return "new_column"
    
    async def _handle_show_columns(
        self,
        intent: Dict[str, Any],
        fund_id: Optional[str],
        portfolio_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle show columns intent"""
        # Use MatrixQueryOrchestrator to get columns
        return {
            "columns": intent.get("columns", []),
            "rows": [],
            "cellUpdates": []
        }
    
    async def _handle_add_column(
        self,
        intent: Dict[str, Any],
        fund_id: Optional[str],
        portfolio_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle add column intent"""
        return {
            "columns": [{
                "name": intent.get("column_name"),
                "type": intent.get("column_type")
            }],
            "rows": [],
            "cellUpdates": []
        }
    
    async def _handle_update_cells(
        self,
        intent: Dict[str, Any],
        fund_id: Optional[str],
        portfolio_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle update cells intent"""
        return {
            "columns": [],
            "rows": [],
            "cellUpdates": intent.get("updates", [])
        }
