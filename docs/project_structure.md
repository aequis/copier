# Project File Structure Plan

This document outlines the approved plan for restructuring the project's file organization to improve clarity, modularity, and maintainability.

## Proposed Structure

```
copier/                     # Project Root
├── .git/                   # Git directory (existing)
├── .venv/                  # Virtual environment (existing)
├── .roomodes               # Roomodes config (existing)
├── config/                 # Directory for configuration files
│   └── mypy.ini            # Moved mypy config
├── docs/                   # Directory for documentation and plans
│   ├── structure_refactor_plan.md
│   ├── improvement_plan.md
│   ├── cwrsync_integration_plan.md
│   ├── settings_implementation_plan.md
│   └── project_structure.md # This file
├── src/                    # Source code directory
│   └── copier/             # Main application package
│       ├── __init__.py     # Makes 'copier' a package
│       ├── main.py         # Entry point (renamed from main_pyside.py)
│       ├── config.py       # Application config logic (moved)
│       ├── state_manager.py # State management (moved)
│       ├── gui/            # Sub-package for GUI components
│       │   ├── __init__.py
│       │   ├── manager.py    # Renamed from gui_manager.py
│       │   └── widgets.py    # Extracted from gui_manager.py
│       └── rsync/          # Sub-package for Rsync logic
│           ├── __init__.py
│           ├── controller.py # Renamed from rsync_controller.py
│           └── runner.py     # Renamed from rsync_runner.py
├── tests/                  # Placeholder for future tests
│   └── __init__.py
├── .gitignore              # Recommended: To ignore .venv, __pycache__, etc.
├── requirements.txt        # Root level is standard
├── requirements-dev.txt    # Root level is standard
└── README.md               # Recommended: Project overview, setup, usage
```

## Rationale and Benefits

1.  **Clear Separation:** Application source code (`src/copier/`) is distinctly separated from configuration (`config/`), documentation (`docs/`), tests (`tests/`), and project metadata (`requirements*.txt`, `.gitignore`, `README.md`).
2.  **Modularity:** Grouping related code (GUI, Rsync) into sub-packages (`gui/`, `rsync/`) makes the codebase easier to navigate and understand.
3.  **Standard Practice:** Using a `src` layout is common for Python applications.
4.  **Improved Imports:** Imports within the application code will become more explicit (e.g., `from copier.gui import manager`).
5.  **Scalability:** Provides a solid foundation for adding new features or tests.
6.  **Discoverability:** Easier for developers to understand the project layout.

## Running the Application Post-Refactor

After restructuring, the application should be run from the project root directory (`c:/Users/aequi/projects/copier`) using Python's `-m` flag:

```bash
python -m copier.main
```

This command tells Python to execute the `main.py` module within the `copier` package located in the `src` directory.