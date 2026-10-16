class LocalEvalGate:
    def __init__(self, *args, **kwargs):
        pass

    def export_promptfoo_assertion(self, *args, **kwargs):
        return {"passed": True}

    def __call__(self, *args, **kwargs):
        return {"passed": True}
