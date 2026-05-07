import logging
import struct
import sys

from isa import Instruction, Opcode, read_code

# Memory-mapped I/O port addresses
PORT_OUT_CHAR = 4080
PORT_IN = 4081
PORT_OUT_INT = 4082
PORT_OUT_INT64_HI = 4083
PORT_OUT_INT64_LO = 4084

MASK32 = 0xFFFFFFFF


def signed32(x: int) -> int:
    """Truncate an arbitrary integer to the signed 32-bit range."""
    x = x & MASK32
    return x - 0x1_0000_0000 if x & 0x8000_0000 else x


class DataPath:
    def __init__(self, memory_size: int) -> None:
        self.memory: list[int] = [0] * memory_size
        self.data_stack: list[int] = []
        self.return_stack: list[int] = []
        self.input_buffer: list[str] = []
        self.output_buffer: list[str] = []
        self.carry: int = 0
        self.overflow: int = 0
        self._int64_hi_buf: int = 0

    def read_mem(self, addr: int) -> int:
        if addr == PORT_IN:
            return ord(self.input_buffer.pop(0)) if self.input_buffer else 0
        return self.memory[addr]

    def write_mem(self, addr: int, val: int) -> None:
        if addr == PORT_OUT_CHAR:
            self.output_buffer.append(chr(val % 256))
        elif addr == PORT_OUT_INT:
            self.output_buffer.append(str(val))
        elif addr == PORT_OUT_INT64_HI:
            self._int64_hi_buf = signed32(val)
        elif addr == PORT_OUT_INT64_LO:
            hi_s = self._int64_hi_buf
            lo_u = val & MASK32
            self.output_buffer.append(str(hi_s * (1 << 32) + lo_u))
        else:
            self.memory[addr] = val

    def get_tos(self) -> int:
        return self.data_stack[-1] if self.data_stack else 0

    def update_add_flags(self, a_u: int, b_u: int, result_u: int) -> None:
        """Update C and V after an addition (ADD, ADC)."""
        result_bits = result_u & MASK32
        self.carry = 1 if result_u > MASK32 else 0
        sa, sb, sr = a_u >> 31, b_u >> 31, result_bits >> 31
        self.overflow = 1 if sa == sb and sr != sa else 0

    def update_sub_flags(self, a_u: int, b_u: int, result: int) -> None:
        """Update C and V after a subtraction (SUB, SBB)."""
        result_bits = result & MASK32
        self.carry = 1 if result < 0 else 0
        sa, sb, sr = a_u >> 31, b_u >> 31, result_bits >> 31
        self.overflow = 1 if sa != sb and sr != sa else 0


class ControlUnit:
    def __init__(self, datapath: DataPath, io_schedule: list[tuple[int, str]]) -> None:
        self.dp = datapath
        self.pc: int = 1
        self.tick_counter: int = 0
        self.schedule: list[tuple[int, str]] = io_schedule

        self.ie: bool = False
        self.irq: bool = False
        self.halted: bool = False

    def tick(self) -> None:
        self.tick_counter += 1

        if self.schedule and self.tick_counter >= self.schedule[0][0]:
            _, char = self.schedule.pop(0)
            self.dp.input_buffer.append(char)

    def decode_and_execute(self) -> None:
        self.irq = bool(self.dp.input_buffer)
        if self.ie and self.irq:
            self.dp.return_stack.append(self.pc)
            self.pc = 0
            self.ie = False
            self.irq = False
            self.tick()

        machine_word = self.dp.read_mem(self.pc)
        instr = Instruction.decode(struct.pack(">I", machine_word))
        self.pc += 1
        self.tick()

        logging.info(
            f"TICK: {self.tick_counter:04} | PC: {self.pc - 1:04} | OP: {instr!s:<14} | "
            f"TOS: {self.dp.get_tos():12} | DS: {len(self.dp.data_stack)} | "
            f"RS: {len(self.dp.return_stack)} | C: {self.dp.carry} | V: {self.dp.overflow}"
        )

        opcode = instr.opcode

        if opcode == Opcode.HALT:
            self.halted = True
            self.tick()

        elif opcode == Opcode.PUSH:
            self.dp.data_stack.append(instr.arg)
            self.tick()
        elif opcode == Opcode.POP:
            self.dp.data_stack.pop()
            self.tick()
        elif opcode == Opcode.PUSH_M:
            self.dp.data_stack.append(self.dp.read_mem(instr.arg))
            self.tick()
        elif opcode == Opcode.POP_M:
            self.dp.write_mem(instr.arg, self.dp.data_stack.pop())
            self.tick()

        elif opcode == Opcode.LOAD:
            addr = self.dp.data_stack.pop()
            self.dp.data_stack.append(self.dp.read_mem(addr))
            self.tick()
        elif opcode == Opcode.STORE:
            val = self.dp.data_stack.pop()
            addr = self.dp.data_stack.pop()
            self.dp.write_mem(addr, val)
            self.tick()

        elif opcode == Opcode.ADD:
            b = self.dp.data_stack.pop()
            a = self.dp.data_stack.pop()
            a_u, b_u = a & MASK32, b & MASK32
            result_u = a_u + b_u
            self.dp.update_add_flags(a_u, b_u, result_u)
            self.dp.data_stack.append(signed32(result_u & MASK32))
            self.tick()

        elif opcode == Opcode.SUB:
            b = self.dp.data_stack.pop()
            a = self.dp.data_stack.pop()
            a_u, b_u = a & MASK32, b & MASK32
            result = a_u - b_u
            self.dp.update_sub_flags(a_u, b_u, result)
            self.dp.data_stack.append(signed32(result & MASK32))
            self.tick()

        elif opcode == Opcode.MUL:
            b = self.dp.data_stack.pop()
            a = self.dp.data_stack.pop()
            self.dp.data_stack.append(signed32(a * b))
            self.tick()

        elif opcode == Opcode.DIV:
            b = self.dp.data_stack.pop()
            a = self.dp.data_stack.pop()
            res = int(a / b) if b != 0 else 0
            self.dp.data_stack.append(res)
            self.tick()

        elif opcode == Opcode.MOD:
            b = self.dp.data_stack.pop()
            a = self.dp.data_stack.pop()
            res = (a - int(a / b) * b) if b != 0 else 0
            self.dp.data_stack.append(res)
            self.tick()

        elif opcode == Opcode.CMP:
            b = self.dp.data_stack.pop()
            a = self.dp.data_stack.pop()
            self.dp.data_stack.append(1 if a == b else 0)
            self.tick()

        elif opcode == Opcode.GT:
            b = self.dp.data_stack.pop()
            a = self.dp.data_stack.pop()
            self.dp.data_stack.append(1 if a > b else 0)
            self.tick()

        elif opcode == Opcode.LT:
            b = self.dp.data_stack.pop()
            a = self.dp.data_stack.pop()
            self.dp.data_stack.append(1 if a < b else 0)
            self.tick()

        elif opcode == Opcode.ADC:
            b = self.dp.data_stack.pop()
            a = self.dp.data_stack.pop()
            a_u, b_u = a & MASK32, b & MASK32
            result_u = a_u + b_u + self.dp.carry
            self.dp.update_add_flags(a_u, b_u, result_u)
            self.dp.data_stack.append(signed32(result_u & MASK32))
            self.tick()

        elif opcode == Opcode.SBB:
            b = self.dp.data_stack.pop()
            a = self.dp.data_stack.pop()
            a_u, b_u = a & MASK32, b & MASK32
            result = a_u - b_u - self.dp.carry
            self.dp.update_sub_flags(a_u, b_u, result)
            self.dp.data_stack.append(signed32(result & MASK32))
            self.tick()

        elif opcode == Opcode.MUL64:
            b = self.dp.data_stack.pop()
            a = self.dp.data_stack.pop()
            full = signed32(a) * signed32(b)
            lo = full & MASK32
            hi_bits = (full >> 32) & MASK32
            self.dp.data_stack.append(signed32(lo))
            self.dp.data_stack.append(signed32(hi_bits))
            self.tick()

        elif opcode == Opcode.PUSH_CARRY:
            self.dp.data_stack.append(self.dp.carry)
            self.tick()

        elif opcode == Opcode.PUSH_OVERFLOW:
            self.dp.data_stack.append(self.dp.overflow)
            self.tick()

        elif opcode == Opcode.JMP:
            self.pc = instr.arg
            self.tick()
        elif opcode == Opcode.JZ:
            val = self.dp.data_stack.pop()
            if val == 0:
                self.pc = instr.arg
            self.tick()
        elif opcode == Opcode.CALL:
            self.dp.return_stack.append(self.pc)
            self.pc = instr.arg
            self.tick()
        elif opcode == Opcode.RET:
            self.pc = self.dp.return_stack.pop()
            self.tick()
        elif opcode == Opcode.IRET:
            self.pc = self.dp.return_stack.pop()
            self.ie = True
            self.tick()
        elif opcode == Opcode.STI:
            self.ie = True
            self.tick()

        else:
            raise ValueError(f"Unknown opcode: {opcode!r} (PC={self.pc - 1})")


def load_schedule(filename: str | None) -> list[tuple[int, str]]:
    """Read an I/O schedule file and return a list of (tick, char) pairs."""
    _esc = {"\\n": "\n", "\\0": "\x00", "\\t": "\t", "\\r": "\r"}

    schedule: list[tuple[int, str]] = []
    if not filename:
        return schedule
    with open(filename, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n").rstrip("\r")
            if not line or line.startswith("#"):
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            tick = int(parts[0])
            token = parts[1]
            if token in _esc:
                char = _esc[token]
            elif len(token) == 4 and token[:2] == "\\x":
                char = chr(int(token[2:], 16))
            else:
                char = token[0]
            schedule.append((tick, char))
    return sorted(schedule, key=lambda x: x[0])


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python machine.py <binary.bin> [schedule.txt]")
        sys.exit(1)

    binary_file = sys.argv[1]
    schedule_file: str | None = sys.argv[2] if len(sys.argv) > 2 else None

    logging.basicConfig(format="%(message)s", level=logging.INFO)

    dp = DataPath(memory_size=4096)
    for i, instr in enumerate(read_code(binary_file)):
        dp.memory[i] = struct.unpack(">I", instr.encode())[0]

    schedule = load_schedule(schedule_file)
    cu = ControlUnit(dp, schedule)

    try:
        while not cu.halted:
            cu.decode_and_execute()
    except Exception as e:
        logging.error(f"Aborted: {e}")

    logging.info(f"Ticks: {cu.tick_counter}")

    print("Output:", "".join(dp.output_buffer))


if __name__ == "__main__":
    main()
