import re
def sanitize_latex_input(data):
    """Recursively sanitize LaTeX special characters in a nested data structure."""
    # Define LaTeX escape sequences
    latex_escape_dict = {
        '#': r'\#',
        '$': r'\$',
        '%': r'\%',
        '&': r'\&',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde',
        '^': r'\textasciicircum',
        '\\': r'\textbackslash'
    }

    def _escape_latex(text):
        """Helper function to escape LaTeX special characters in a string."""
        return re.sub(r'[#$%&_{}~^\\]', lambda m: latex_escape_dict.get(m.group(0), m.group(0)), str(text))

    def _sanitize_recursive(item):
        """Recursively sanitize items in nested data structures."""
        if isinstance(item, dict):
            return {k: _sanitize_recursive(v) for k, v in item.items()}
        elif isinstance(item, list):
            return [_sanitize_recursive(i) for i in item]
        elif isinstance(item, str):
            return _escape_latex(item)
        return item

    return _sanitize_recursive(data)