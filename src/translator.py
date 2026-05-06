import re
import sys
from typing import Any, TypeAlias

from isa import Instruction, Opcode, write_code

# Memory-mapped I/O port addresses
PORT_OUT_CHAR = 4080
PORT_IN = 4081
PORT_OUT_INT = 4082
PORT_OUT_INT64_HI = 4083
PORT_OUT_INT64_LO = 4084

MEM_DATA_START = 1024


AstNode: TypeAlias = int | str | list[Any]


def tokenize(source_code: str) -> list[str]:
    """Split source into tokens. Strips Lisp comments."""
    cleaned = re.sub(r";[^\n]*", "", source_code)
    return re.findall(r'"[^"]*"|[()]|[^()\s]+', cleaned)


def parse(tokens: list[str]) -> AstNode:
    """Build an AST from the token list."""
    if not tokens:
        raise EOFError("Unexpected end of file")

    token = tokens.pop(0)

    if token == "(":
        ast: list[AstNode] = []
        while tokens and tokens[0] != ")":
            ast.append(parse(tokens))
        if not tokens:
            raise SyntaxError("Expected closing ')'")
        tokens.pop(0)
        return ast
    elif token == ")":
        raise SyntaxError("Unexpected ')'")
    else:
        if token.startswith('"'):
            return token
        try:
            return int(token)
        except ValueError:
            return token


class Compiler:
    def __init__(self) -> None:
        self.instructions: list[Instruction] = []
        self.variables: dict[str, int] = {}  # name: memory address
        self.data_ptr: int = MEM_DATA_START
        self.labels: dict[str, int] = {}  # function name: first instruction address
        self.unresolved_jumps: list[tuple[int, str]] = []

    def add_inst(self, opcode: Opcode, arg: int = 0) -> int:
        idx = len(self.instructions)
        self.instructions.append(Instruction(opcode, arg))
        return idx

    def allocate_var(self, name: str) -> int:
        if name not in self.variables:
            self.variables[name] = self.data_ptr
            self.data_ptr += 1
        return self.variables[name]

    def allocate_string(self, text: str) -> int:
        """Store a C-string in data memory and return its start address."""
        start_addr = self.data_ptr
        text = text[1:-1]
        for char in text:
            self.add_inst(Opcode.PUSH, self.data_ptr)
            self.add_inst(Opcode.PUSH, ord(char))
            self.add_inst(Opcode.STORE)
            self.data_ptr += 1

        self.add_inst(Opcode.PUSH, self.data_ptr)
        self.add_inst(Opcode.PUSH, 0)
        self.add_inst(Opcode.STORE)
        self.data_ptr += 1
        return start_addr

    def _emit_not(self) -> None:
        """Flip a boolean on TOS: 0 -> 1, non-zero -> 0."""
        self.add_inst(Opcode.PUSH, 0)
        self.add_inst(Opcode.CMP)

    def compile_expr(self, expr: AstNode) -> None:
        """Compile one expression. Always leaves exactly one value on the data stack."""

        if isinstance(expr, int):
            self.add_inst(Opcode.PUSH, expr)

        elif isinstance(expr, str) and expr.startswith('"'):
            addr = self.allocate_string(expr)
            self.add_inst(Opcode.PUSH, addr)

        elif isinstance(expr, str):
            addr = self.allocate_var(expr)
            self.add_inst(Opcode.PUSH_M, addr)

        elif isinstance(expr, list):
            if len(expr) == 0:
                self.add_inst(Opcode.PUSH, 0)
                return

            op = expr[0]

            if op in ("+", "-", "*", "/", "mod", "=", ">", "<"):
                self.compile_expr(expr[1])
                self.compile_expr(expr[2])
                opcode_map = {
                    "+": Opcode.ADD,
                    "-": Opcode.SUB,
                    "*": Opcode.MUL,
                    "/": Opcode.DIV,
                    "mod": Opcode.MOD,
                    "=": Opcode.CMP,
                    ">": Opcode.GT,
                    "<": Opcode.LT,
                }
                self.add_inst(opcode_map[op])

            elif op in ("<=", ">=", "!=", "not"):
                if op == "not":
                    self.compile_expr(expr[1])
                elif op == "<=":
                    self.compile_expr(expr[1])
                    self.compile_expr(expr[2])
                    self.add_inst(Opcode.GT)
                elif op == ">=":
                    self.compile_expr(expr[1])
                    self.compile_expr(expr[2])
                    self.add_inst(Opcode.LT)
                elif op == "!=":
                    self.compile_expr(expr[1])
                    self.compile_expr(expr[2])
                    self.add_inst(Opcode.CMP)
                self._emit_not()

            elif op == "setq":
                var_name = expr[1]
                addr = self.allocate_var(var_name)
                self.add_inst(Opcode.PUSH, addr)
                self.compile_expr(expr[2])
                self.add_inst(Opcode.STORE)
                self.add_inst(Opcode.PUSH_M, addr)

            elif op == "if":
                self.compile_expr(expr[1])
                jz_idx = self.add_inst(Opcode.JZ, 0)
                self.compile_expr(expr[2])
                jmp_idx = self.add_inst(Opcode.JMP, 0)

                self.instructions[jz_idx].arg = len(self.instructions)
                if len(expr) > 3:
                    self.compile_expr(expr[3])
                else:
                    self.add_inst(Opcode.PUSH, 0)

                self.instructions[jmp_idx].arg = len(self.instructions)

            elif op == "loop":
                cond_expr = expr[1]
                body_expr = expr[2]

                self.add_inst(Opcode.PUSH, 0)

                loop_start = len(self.instructions)

                self.compile_expr(cond_expr)
                jz_idx = self.add_inst(Opcode.JZ, 0)

                self.add_inst(Opcode.POP)
                self.compile_expr(body_expr)

                self.add_inst(Opcode.JMP, loop_start)

                self.instructions[jz_idx].arg = len(self.instructions)

            elif op == "progn":
                sub_exprs = expr[1:]
                if not sub_exprs:
                    self.add_inst(Opcode.PUSH, 0)
                    return
                for i, sub_expr in enumerate(sub_exprs):
                    self.compile_expr(sub_expr)
                    if i < len(sub_exprs) - 1:
                        self.add_inst(Opcode.POP)

            elif op == "defun":
                func_name = expr[1]
                args = expr[2]
                body_exprs = expr[3:]

                jmp_end_idx = self.add_inst(Opcode.JMP, 0)
                self.labels[func_name] = len(self.instructions)

                temp_args: list[int] = []
                for arg in reversed(args):
                    tmp = self.allocate_var(f"_tmp_{func_name}_{arg}")
                    self.add_inst(Opcode.POP_M, tmp)
                    temp_args.insert(0, tmp)

                for i, arg in enumerate(args):
                    addr = self.allocate_var(arg)
                    self.add_inst(Opcode.PUSH_M, addr)
                    self.add_inst(Opcode.PUSH_M, temp_args[i])
                    self.add_inst(Opcode.POP_M, addr)

                for i, body_expr in enumerate(body_exprs):
                    self.compile_expr(body_expr)
                    if i < len(body_exprs) - 1:
                        self.add_inst(Opcode.POP)

                ret_slot = self.allocate_var("_ret_val")
                self.add_inst(Opcode.POP_M, ret_slot)

                for arg in reversed(args):
                    addr = self.allocate_var(arg)
                    self.add_inst(Opcode.POP_M, addr)

                self.add_inst(Opcode.PUSH_M, ret_slot)
                self.add_inst(Opcode.RET)

                self.instructions[jmp_end_idx].arg = len(self.instructions)
                self.add_inst(Opcode.PUSH, 0)

            elif op == "read":
                self.add_inst(Opcode.PUSH_M, PORT_IN)

            elif op == "write":
                self.compile_expr(expr[1])
                self.compile_expr(expr[2])
                self.add_inst(Opcode.STORE)
                self.add_inst(Opcode.PUSH, 0)

            elif op == "print-char":
                self.add_inst(Opcode.PUSH, PORT_OUT_CHAR)
                self.compile_expr(expr[1])
                self.add_inst(Opcode.STORE)
                self.add_inst(Opcode.PUSH, 0)

            elif op == "print-int":
                self.add_inst(Opcode.PUSH, PORT_OUT_INT)
                self.compile_expr(expr[1])
                self.add_inst(Opcode.STORE)
                self.add_inst(Opcode.PUSH, 0)

            elif op == "print-int64":
                self.add_inst(Opcode.PUSH, PORT_OUT_INT64_HI)
                self.compile_expr(expr[1])
                self.add_inst(Opcode.STORE)
                self.add_inst(Opcode.PUSH, PORT_OUT_INT64_LO)
                self.compile_expr(expr[2])
                self.add_inst(Opcode.STORE)
                self.add_inst(Opcode.PUSH, 0)

            elif op == "adc":
                self.compile_expr(expr[1])
                self.compile_expr(expr[2])
                self.add_inst(Opcode.ADC)

            elif op == "sbb":
                self.compile_expr(expr[1])
                self.compile_expr(expr[2])
                self.add_inst(Opcode.SBB)

            elif op == "push-carry":
                self.add_inst(Opcode.PUSH_CARRY)

            elif op == "push-overflow":
                self.add_inst(Opcode.PUSH_OVERFLOW)

            elif op == "mul64":
                self.compile_expr(expr[1])
                self.compile_expr(expr[2])
                self.add_inst(Opcode.MUL64)
                hi_addr = self.allocate_var(expr[4])
                lo_addr = self.allocate_var(expr[3])
                self.add_inst(Opcode.POP_M, hi_addr)
                self.add_inst(Opcode.POP_M, lo_addr)
                self.add_inst(Opcode.PUSH, 0)

            elif op == "load":
                self.compile_expr(expr[1])
                self.add_inst(Opcode.LOAD)

            elif op == "store-at":
                self.compile_expr(expr[1])
                self.compile_expr(expr[2])
                self.add_inst(Opcode.STORE)
                self.add_inst(Opcode.PUSH, 0)

            elif op == "halt":
                self.add_inst(Opcode.HALT)
                self.add_inst(Opcode.PUSH, 0)

            elif isinstance(op, str):
                for arg in expr[1:]:
                    self.compile_expr(arg)
                call_idx = self.add_inst(Opcode.CALL, 0)
                self.unresolved_jumps.append((call_idx, op))

    def resolve_labels(self) -> None:
        for inst_idx, func_name in self.unresolved_jumps:
            if func_name in self.labels:
                self.instructions[inst_idx].arg = self.labels[func_name]
            else:
                raise ValueError(f"Unknown function: {func_name}")


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python translator.py <input.lisp> <output.bin>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_bin = sys.argv[2]
    output_log = output_bin + ".log"

    with open(input_file, encoding="utf-8") as f:
        source_code = f.read()

    tokens = tokenize(source_code)
    tokens = ["(", "progn", *tokens, ")"]
    ast = parse(tokens)
    assert isinstance(ast, list), "top-level parse must return a list"

    isr_exprs: list[AstNode] = []
    main_exprs: list[AstNode] = []
    for sub in ast[1:]:
        if isinstance(sub, list) and sub and sub[0] == "defisr":
            isr_exprs = sub[1:]
        else:
            main_exprs.append(sub)

    compiler = Compiler()

    isr_jmp = compiler.add_inst(Opcode.JMP, 0)

    if isr_exprs:
        split = 0
        for e in main_exprs:
            if isinstance(e, list) and e and e[0] in ("setq", "defun"):
                split += 1
            else:
                break
        init_part = main_exprs[:split]
        logic_part = main_exprs[split:]

        compiler.compile_expr(["progn", *init_part])
        compiler.add_inst(Opcode.STI)
        compiler.compile_expr(["progn", *logic_part])
    else:
        compiler.compile_expr(["progn", *main_exprs])

    compiler.add_inst(Opcode.HALT)

    isr_start = len(compiler.instructions)
    compiler.instructions[isr_jmp].arg = isr_start

    if isr_exprs:
        for i, e in enumerate(isr_exprs):
            compiler.compile_expr(e)
            if i < len(isr_exprs) - 1:
                compiler.add_inst(Opcode.POP)
        compiler.add_inst(Opcode.POP)

    compiler.add_inst(Opcode.IRET)

    compiler.resolve_labels()

    write_code(output_bin, output_log, compiler.instructions)
    print(f"Compiled OK. Binary: {output_bin}, dump: {output_log}")


if __name__ == "__main__":
    main()
