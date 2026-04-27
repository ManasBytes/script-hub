import ast
import sys
from pathlib import Path

# Maps declared config types to the set of annotation strings considered a match.
# File-type variables (.xlsx, .csv, Directory) have no meaningful annotation — empty set.
_TYPE_ANNOTATIONS: dict[str, set[str]] = {
    "int":    {"int"},
    "float":  {"float"},
    "bool":   {"bool"},
    "string": {"str", "string"},
}


def detect_dependencies(source: str) -> list[str]:
    """Return sorted list of third-party top-level packages imported by source."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                imports.add(node.module.split(".")[0])

    stdlib = sys.stdlib_module_names  # available Python 3.10+
    return sorted(
        pkg for pkg in imports
        if pkg not in stdlib and not pkg.startswith("_")
    )


def _check_variable(tree: ast.AST, name: str, declared_type: str) -> dict:
    """
    Walk the AST and look for every place `name` is referenced.

    Returns a dict with:
      found            – bool, True if the name appears anywhere as an identifier
      first_line       – int | None, first source line where it appears
      annotated_as     – str | None, the annotation text if an annotated form was found
      annotation_matches – bool | None
            True  = annotation found and matches declared_type
            False = annotation found but doesn't match
            None  = no annotation (or declared_type is a file type, so N/A)
    """
    expected = _TYPE_ANNOTATIONS.get(declared_type, set())
    is_type_checkable = bool(expected)

    found = False
    first_line: int | None = None
    annotated_as: str | None = None
    annotation_matches: bool | None = None

    for node in ast.walk(tree):
        # Plain name reference (any context: Load, Store, Del)
        if isinstance(node, ast.Name) and node.id == name:
            found = True
            if first_line is None:
                first_line = node.lineno

        # Annotated assignment:  name: SomeType = ...
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id == name:
                found = True
                ann_text = ast.unparse(node.annotation)
                if annotated_as is None:
                    annotated_as = ann_text
                if is_type_checkable and annotation_matches is None:
                    annotation_matches = ann_text.lower() in {
                        t.lower() for t in expected
                    }
                if first_line is None:
                    first_line = target.lineno

        # Function / lambda parameter:  def fn(name: SomeType)
        elif isinstance(node, ast.arg) and node.arg == name:
            found = True
            if node.annotation:
                ann_text = ast.unparse(node.annotation)
                if annotated_as is None:
                    annotated_as = ann_text
                if is_type_checkable and annotation_matches is None:
                    annotation_matches = ann_text.lower() in {
                        t.lower() for t in expected
                    }
            if first_line is None:
                first_line = node.lineno

    # If variable was found but is type-checkable with no annotation, flag it.
    if found and is_type_checkable and annotated_as is None:
        annotation_matches = None  # explicitly: found but unannotated

    return {
        "found": found,
        "first_line": first_line,
        "annotated_as": annotated_as,
        "annotation_matches": annotation_matches,
    }


def analyze_script(
    script_path: str,
    input_variables: list[dict],
    config_variables: list[dict],
    output_variables: list[dict],
) -> dict:
    """
    Full analysis of a Python script file.

    Returns:
      parse_error   – str | None
      dependencies  – list[str]  (third-party package names)
      variables     – dict[name, check_result]
    """
    source = Path(script_path).read_text(encoding="utf-8")

    try:
        tree = ast.parse(source, filename=script_path)
    except SyntaxError as exc:
        return {"parse_error": str(exc), "dependencies": [], "variables": {}}

    dependencies = detect_dependencies(source)

    variables: dict[str, dict] = {}
    groups = [
        ("input",  input_variables),
        ("config", config_variables),
        ("output", output_variables),
    ]
    for category, var_list in groups:
        for var in var_list:
            var_name = var.get("name", "").strip()
            var_type = var.get("type", "").strip()
            if not var_name:
                continue
            variables[var_name] = {
                "category": category,
                "declared_type": var_type,
                **_check_variable(tree, var_name, var_type),
            }

    return {"parse_error": None, "dependencies": dependencies, "variables": variables}
