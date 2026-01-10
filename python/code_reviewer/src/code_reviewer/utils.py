from typing import Any, Dict, List, Union

def parse_adf(node: Union[Dict[str, Any], List[Any], str, None]) -> str:
    """
    Recursively convert Atlassian Document Format (ADF) JSON into readable text.
    
    Args:
        node (Union[Dict[str, Any], List[Any], str, None]): 
            A single ADF node or list of nodes from Jira's API response.
    
    Returns:
        str: A human-readable, Markdown-like string representation.
    """
    if isinstance(node, dict):
        node_type = node.get("type")

        if node_type == "paragraph":
            return "".join(parse_adf(child) for child in node.get("content", [])) + "\n"

        elif node_type == "text":
            text = node.get("text", "")
            marks = node.get("marks", [])
            for mark in marks:
                if mark["type"] == "strong":
                    text = f"**{text}**"
                elif mark["type"] == "code":
                    text = f"`{text}`"
            return text

        elif node_type == "bulletList":
            return "".join("- " + parse_adf(item) for item in node.get("content", []))

        elif node_type == "orderedList":
            lines = []
            for i, item in enumerate(node.get("content", []), start=1):
                text = parse_adf(item).strip()
                lines.append(f"{i}. {text}")
            return "\n".join(lines) + "\n"

        elif node_type == "listItem":
            return "".join(parse_adf(child) for child in node.get("content", []))

        elif "content" in node:
            return "".join(parse_adf(child) for child in node["content"])

    elif isinstance(node, list):
        return "".join(parse_adf(child) for child in node)

    return ""
