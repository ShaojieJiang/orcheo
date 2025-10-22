export const DEFAULT_PYTHON_CODE = `def process_data(input_data):
    """Process incoming workflow data.

    Args:
        input_data: The dictionary payload provided to this node.

    Returns:
        A dictionary containing the transformed result that will
        be passed to the next node in the workflow.
    """
    result = input_data

    # Example: filter items with value greater than 100
    if isinstance(input_data, dict) and "items" in input_data:
        result = {
            "filtered_items": [
                item for item in input_data["items"]
                if isinstance(item, dict) and item.get("value", 0) > 100
            ]
        }

    return result
`;
