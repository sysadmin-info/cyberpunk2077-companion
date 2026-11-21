"""Exercise the public PowerShell scripts against multiple applications on PATH, offline."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELL = os.environ.get("CP2077_TEST_POWERSHELL") or (
    shutil.which("powershell.exe") if os.name == "nt" else None
) or shutil.which("pwsh")


@unittest.skipUnless(SHELL, "requires Windows PowerShell or pwsh")
class LauncherTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="companion launcher ")
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        self.dirs = [self.work / f"launcher {n}" for n in range(3)]
        for d in self.dirs:
            d.mkdir()
        self.log = self.work / "calls.jsonl"
        recorder = self.work / "record args.py"
        recorder.write_text(
            "import json, os, sys\n"
            "with open(os.environ['CP_TEST_LOG'], 'a', encoding='utf8') as f:\n"
            "    print(json.dumps(sys.argv[1:]), file=f)\n"
            "sys.exit(int(os.environ.get('CP_TEST_EXIT', '0')))\n",
            encoding="utf8",
        )
        self.env = {
            **os.environ,
            "PATH": os.pathsep.join(map(str, self.dirs)),
            "USERPROFILE": str(self.work),
            "CP_TEST_PYTHON": sys.executable,
            "CP_TEST_RECORDER": str(recorder),
            "CP_TEST_LOG": str(self.log),
            "CP_TEST_EXIT": "0",
            "POWERSHELL_TELEMETRY_OPTOUT": "1",
            "POWERSHELL_UPDATECHECK": "Off",
        }
        self.entry = str(ROOT / "cp2077_companion.py")

    def install(self, name, n):
        tag = f"{name}-{n}"
        if os.name == "nt":
            (self.dirs[n] / (name + ".cmd")).write_text(
                f'@"%CP_TEST_PYTHON%" "%CP_TEST_RECORDER%" {tag} %*\n'
                "@exit /b %errorlevel%\n", encoding="ascii"
            )
        else:
            p = self.dirs[n] / name
            p.write_text(
                f'#!/bin/sh\nexec "$CP_TEST_PYTHON" "$CP_TEST_RECORDER" {tag} "$@"\n',
                encoding="ascii",
            )
            p.chmod(0o755)

    def invoke(self, script, *args, expected=0):
        self.log.unlink(missing_ok=True)
        args_ps = [SHELL, "-NoLogo", "-NoProfile", "-NonInteractive"]
        if os.name == "nt":
            args_ps.extend(["-ExecutionPolicy", "Bypass"])
        result = subprocess.run(
            [*args_ps, "-File", str(ROOT / script), *args],
            env=self.env, cwd=self.work, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, expected, (result.stdout, result.stderr))
        calls = [json.loads(line) for line in self.log.read_text("utf8").splitlines()] if self.log.exists() else []
        return calls, result.stderr

    def test_three_launchers_one_command_and_custom_port(self):
        for i in range(3):
            self.install("py", i)
        self.install("python", 0)
        saves = str(self.work / "My save copies")
        calls, _ = self.invoke("run.ps1", "-Port", "9977", "-NoOpen", "-SaveRoot", saves)
        self.assertEqual(calls, [["py-0", "-3", self.entry, "--save-root", saves, "--port", "9977", "--no-open"]])

    def test_python_fallback_default_port_and_offline(self):
        self.install("python", 1)
        self.install("python", 2)
        calls, _ = self.invoke("run.ps1")
        saves = str(self.work) + r"\Saved Games\CD Projekt Red\Cyberpunk 2077"
        self.assertEqual(calls, [["python-1", self.entry, "--save-root", saves, "--port", "8765"]])

    def test_explicit_update_alone_and_then_gui(self):
        self.install("python", 0)
        self.install("py", 1)
        self.install("py", 2)
        call = ["py-1", "-3", self.entry]
        calls, _ = self.invoke("update-item-catalog.ps1")
        self.assertEqual(calls, [[*call, "--update-catalog"]])
        calls, _ = self.invoke("run.ps1", "-UpdateCatalog", "-SaveRoot", str(self.work), "-Port", "9977")
        self.assertEqual(calls, [[*call, "--update-catalog"], [*call, "--save-root", str(self.work), "--port", "9977"]])

    def test_failed_update_stops_before_starting_gui(self):
        self.install("python", 0)
        self.install("python", 1)
        self.env["CP_TEST_EXIT"] = "23"
        for script, args in (("update-item-catalog.ps1", []), ("run.ps1", ["-UpdateCatalog"])):
            with self.subTest(script=script):
                calls, _ = self.invoke(script, *args, expected=23)
                self.assertEqual(calls, [["python-0", self.entry, "--update-catalog"]])

    def test_no_interpreter_prints_actionable_error(self):
        calls, stderr = self.invoke("run.ps1", expected=1)
        self.assertEqual(calls, [])
        self.assertIn(b"Python 3.10+", stderr)
