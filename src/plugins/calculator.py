"""Knowledge Foundry — Calculator Plugin.

Provides basic arithmetic capabilities to agents.
"""

from __future__ import annotations

import ast
import operator
from typing import Any

from src.core.interfaces import Plugin, PluginManifest, PluginResult


class CalculatorPlugin(Plugin):
    """Plugin for evaluating mathematical expressions safely."""

    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="calculator",
            version="1.0.0",
            description="Performs basic arithmetic operations (+, -, *, /, ^).",
            actions=["evaluate"],
            permissions=["none"],
        )

    async def execute(self, action: str, params: dict[str, Any]) -> PluginResult:
        if action != "evaluate":
            return PluginResult(success=False, error=f"Unknown action: {action}")

        expression = params.get("expression")
        if not expression:
            return PluginResult(success=False, error="Missing 'expression' parameter")

        try:
            result = self._safe_eval(expression)
            return PluginResult(success=True, data={"result": result})
        except Exception as e:
            return PluginResult(success=False, error=f"Calculation error: {str(e)}")

    def _safe_eval(self, expr: str) -> float | int:
        """Safely evaluate a mathematical expression using ast.literal_eval logic."""
        # Allowed operators
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }

        def eval_node(node: ast.AST) -> float | int:
            if isinstance(node, ast.Constant):  # Num in older python
                if isinstance(node.value, (int, float)):
                    return node.value
                raise ValueError("Expression must contain only numbers")
            
            if isinstance(node, ast.BinOp):
                left = eval_node(node.left)
                right = eval_node(node.right)
                if type(node.op) in operators:
                    return operators[type(node.op)](left, right)  # type: ignore
                raise ValueError(f"Unsupported operator: {type(node.op)}")
                
            if isinstance(node, ast.UnaryOp):
                operand = eval_node(node.operand)
                if type(node.op) in operators:
                    return operators[type(node.op)](operand)  # type: ignore
                raise ValueError(f"Unsupported unary operator: {type(node.op)}")
                
            raise ValueError(f"Unsupported expression node: {type(node)}")

        try:
            tree = ast.parse(expr, mode='eval')
            return eval_node(tree.body)
        except SyntaxError:
            raise ValueError("Invalid syntax")
