# Code Structure Refactoring: Implementation Plan

This plan outlines the incremental steps to refactor the Copier application using the Coordinator pattern, aiming to keep the application functional after each step.

**Goal:** Refactor the application to use the Coordinator pattern, centralizing state and decoupling components as described in `docs/structure_refactor_plan.md`.

**Revised Step-by-Step Plan (Prioritizing Functionality):**

1.  **Introduce `AppState`:**
    *   Create the central state class (`src/copier/state_manager.py`) with all necessary properties and a `state_changed` signal using `PySide6.QtCore.Signal`.
    *   *(App functional)*

2.  **Introduce `AppCoordinator`:**
    *   Create the coordinator class (`src/copier/coordinator.py`).
    *   In its `__init__`, instantiate `AppState`, the *existing* `GuiManager`, and `RsyncController`.
    *   Integrate into `src/copier/main.py` to create the `AppCoordinator` instance, which then creates the other components.
    *   *(App functional)*

3.  **Provide `AppState` Access:**
    *   Modify `GuiManager` and `RsyncController` `__init__` methods to accept the `AppState` instance and store it (e.g., `self._app_state`).
    *   Update instantiation calls in `AppCoordinator` to pass the shared `AppState` instance.
    *   *(App functional)*

4.  **Connect `AppState` to `GuiManager` Updates:**
    *   Implement a `GuiManager.update_ui_from_state(self, state: AppState)` slot that reads the state object and updates UI elements.
    *   In `AppCoordinator`, connect `self.app_state.state_changed.connect(self.gui_manager.update_ui_from_state)`.
    *   *(App functional, potentially redundant UI updates initially)*

5.  **Migrate State Writing (via Coordinator):**
    *   Connect `GuiManager` action signals (e.g., `run_clicked`, `destination_dropped`) to new slots in `AppCoordinator` (e.g., `_handle_run_clicked`).
    *   Implement these coordinator slots to update `AppState` (e.g., `self.app_state.set_destination(path)`). `AppState` methods emit `state_changed`.
    *   Connect `RsyncController` outcome signals (e.g., `rsync_finished_success`) to new slots in `AppCoordinator` that update `AppState`.
    *   *(App functional, state management becoming centralized)*

6.  **Migrate State Reading:**
    *   Refactor `GuiManager` and `RsyncController` to read state *only* from `self._app_state`.
    *   Remove internal state variables/checks that duplicate `AppState` information.
    *   *(App functional, components now rely on the single source of truth)*

7.  **Decouple `RsyncController` from `GuiManager`:**
    *   Remove the `gui` parameter from `RsyncController.__init__`.
    *   Remove direct calls from `RsyncController` to `GuiManager`.
    *   Use signals (e.g., `log_message = Signal(str, str)`) connected through the coordinator for necessary communication like logging.
    *   *(App functional)*

8.  **Refine `RsyncController` Interface:**
    *   Change methods like `start_or_resume_rsync` to accept data explicitly (e.g., `start_rsync(self, sources: list[str], destination: str, options: dict)`).
    *   Update the coordinator to read data from `AppState` and pass it when calling these methods.
    *   Remove state-reading logic from `RsyncController`.
    *   *(App functional)*

9.  **Cleanup and Testing:**
    *   Remove obsolete methods, slots, signals, and internal state variables from `GuiManager` and `RsyncController`.
    *   Review `main.py` and ensure the `AppCoordinator` is the primary driver.
    *   Add/update unit tests for `AppState`, `AppCoordinator`, and the refactored components.
    *   *(App functional and refactored)*