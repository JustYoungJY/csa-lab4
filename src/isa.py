import struct
from enum import StrEnum


class Opcode(StrEnum):
    # stack / memory
    PUSH = "push"
    POP = "pop"
    LOAD = "load"
    STORE = "store"
    PUSH_M = "push_m"
    POP_M = "pop_m"

    # arithmetic / logic
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    MOD = "mod"
    CMP = "cmp"
    GT = "gt"
    LT = "lt"

    # 64-bit arithmetic (carry / overflow aware)
    ADC = "adc"
    SBB = "sbb"
    MUL64 = "mul64"
    PUSH_CARRY = "push_carry"
    PUSH_OVERFLOW = "push_overflow"

    # control flow
    JMP = "jmp"
    JZ = "jz"
    CALL = "call"
    RET = "ret"
    IRET = "iret"
    HALT = "halt"
    STI = "sti"


OPCODE_TO_BIN = {
    Opcode.PUSH: 0x01,
    Opcode.POP: 0x02,
    Opcode.LOAD: 0x03,
    Opcode.STORE: 0x04,
    Opcode.ADD: 0x05,
    Opcode.SUB: 0x06,
    Opcode.MUL: 0x07,
    Opcode.DIV: 0x08,
    Opcode.MOD: 0x09,
    Opcode.CMP: 0x0A,
    Opcode.GT: 0x0B,
    Opcode.LT: 0x0C,
    Opcode.JMP: 0x0D,
    Opcode.JZ: 0x0E,
    Opcode.CALL: 0x0F,
    Opcode.RET: 0x10,
    Opcode.IRET: 0x11,
    Opcode.HALT: 0x12,
    Opcode.PUSH_M: 0x13,
    Opcode.POP_M: 0x14,
    Opcode.ADC: 0x15,
    Opcode.SBB: 0x16,
    Opcode.MUL64: 0x17,
    Opcode.PUSH_CARRY: 0x18,
    Opcode.PUSH_OVERFLOW: 0x19,
    Opcode.STI: 0x1A,
}

BIN_TO_OPCODE = {v: k for k, v in OPCODE_TO_BIN.items()}


class Instruction:
    def __init__(self, opcode: Opcode, arg: int = 0) -> None:
        self.opcode = opcode
        self.arg = arg

    def encode(self) -> bytes:
        """Pack instruction into 32 bits: [8-bit opcode][24-bit signed operand]."""
        op_int = OPCODE_TO_BIN[self.opcode]
        arg_24 = self.arg & 0xFFFFFF
        machine_word = (op_int << 24) | arg_24
        return struct.pack(">I", machine_word)

    @classmethod
    def decode(cls, data: bytes) -> "Instruction":
        """Unpack 4 bytes back into an Instruction."""
        machine_word = struct.unpack(">I", data)[0]
        op_int = machine_word >> 24
        arg_24 = machine_word & 0xFFFFFF
        # sign-extend the 24-bit value
        arg = arg_24 - 0x1000000 if arg_24 & 0x800000 else arg_24
        return cls(BIN_TO_OPCODE[op_int], arg)

    def __str__(self) -> str:
        if self.opcode in [
            Opcode.PUSH,
            Opcode.JMP,
            Opcode.JZ,
            Opcode.CALL,
            Opcode.PUSH_M,
            Opcode.POP_M,
        ]:
            return f"{self.opcode.value} {self.arg}"
        return f"{self.opcode.value}"


def write_code(
    binary_filename: str,
    debug_filename: str,
    instructions: list[Instruction],
) -> None:
    """Write instructions to a binary file and a human-readable hex dump."""
    with open(binary_filename, "wb") as f_bin:
        for instr in instructions:
            f_bin.write(instr.encode())

    with open(debug_filename, "w", encoding="utf-8") as f_dbg:
        for addr, instr in enumerate(instructions):
            machine_word = struct.unpack(">I", instr.encode())[0]
            f_dbg.write(f"{addr:04d} - {machine_word:08X} - {instr}\n")


def read_code(binary_filename: str) -> list[Instruction]:
    """Read a binary file and return the list of instructions."""
    instructions: list[Instruction] = []
    with open(binary_filename, "rb") as f:
        while chunk := f.read(4):
            if len(chunk) < 4:
                break
            instructions.append(Instruction.decode(chunk))
    return instructions
