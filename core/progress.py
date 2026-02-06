class ProgressReporter:
    """
    Thread-safe progress + metrics reporter.
    UI passes callbacks.
    Engine pulls cancellation state cooperatively.
    """

    def __init__(self, on_stage=None, on_metrics=None, is_cancelled=None):
        self._on_stage = on_stage
        self._on_metrics = on_metrics
        self._is_cancelled = is_cancelled or (lambda: False)

    # -------- Engine hooks --------
    def stage(self, stage_name):
        if self._on_stage:
            self._on_stage(stage_name)

        if self.cancelled:
            raise CancelledError()

    def metrics(self, data: dict):
        if self._on_metrics:
            self._on_metrics(data)

        if self.cancelled:
            raise CancelledError()

    # -------- State --------
    @property
    def cancelled(self):
        return bool(self._is_cancelled())


class CancelledError(Exception):
    """Raised when user cancels reconciliation."""
    pass
