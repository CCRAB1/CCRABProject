import os

def maybe_attach_debugger():
    if os.getenv("AIRFLOW_REMOTE_DEBUG", "False").lower() not in {"1", "true", "yes"}:
        return

    import pydevd_pycharm

    pydevd_pycharm.settrace(
        os.getenv("PYDEVD_HOST", "host.docker.internal"),
        port=int(os.getenv("PYDEVD_PORT", "5678")),
        stdout_to_server=True,
        stderr_to_server=True,
        suspend=os.getenv("PYDEVD_SUSPEND", "False").lower() in {"1", "true", "yes"},
    )
