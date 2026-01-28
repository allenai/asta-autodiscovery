import os
import json


class TreeLogger:
    level: int
    agent_name: str
    node_idx: int

    def __init__(self, log_dir: str):
        """Initialize logger that stores logs for each node in a tree exploration.

        Args:
            log_dir: Directory to store all log files
        """
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

    def log_node(self, level: int, node_idx: int, message: str | dict):
        """Log a message for a specific node.

        Args:
            level: Level of the node in the tree
            node_idx: Index of the node within its level
            message: Message to log (string or dictionary)
        """
        filename = os.path.join(self.log_dir, f"node_{level}_{node_idx}.json")

        with open(filename, "a") as f:
            if isinstance(message, dict):
                f.write(json.dumps(message, indent=2))
            else:
                f.write(json.dumps(json.loads(message), indent=2))

    def load_node(self, level: int, node_idx: int, as_json: bool = False) -> list[str | dict]:
        """Load the contents of a log file for a specific node.

        Args:
            level: Level of the node in the tree
            node_idx: Index of the node within its level
            as_json: If True, attempt to parse lines as JSON. If False, return raw strings.

        Returns:
            List of messages from the log file. Each message is either a string or
            dictionary depending on how it was originally logged and the as_json flag.

        Raises:
            FileNotFoundError: If the log file does not exist
        """
        filename = os.path.join(self.log_dir, f"node_{level}_{node_idx}.json")

        messages = None
        with open(filename, "r") as f:
            if as_json:
                messages = json.load(f)
            else:
                messages = f.read()

        return messages
