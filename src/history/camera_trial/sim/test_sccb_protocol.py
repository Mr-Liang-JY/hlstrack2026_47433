"""Independent open-drain wire model: decode GPIO edges as an SCCB slave."""
from pathlib import Path
from types import SimpleNamespace
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
import camera_run

class Wires:
    def __init__(self, present=True):
        self.present = present
        self.control = 0
        self.scl = self.master_sda = True
        self.slave_low = False
        self.mode = 'idle'
        self.bits = self.byte = self.byte_number = 0
        self.pointer = 0
        self.regs = {0x300A:0x56, 0x300B:0x40}
        self.nacks = []
        self.acks = 0
        self.force_scl_low = False

    def read(self, offset):
        if offset == 0:
            return self.control
        return 0xCA02001F | ((self.scl and not self.force_scl_low) << 6) | ((self.master_sda and not self.slave_low) << 7)

    def _byte_received(self, value):
        self.next_mode = 'rx'
        if self.byte_number == 0:
            ack = self.present and (value >> 1) == 0x3C
            if value & 1:
                self.next_mode = 'tx'
                self.tx_byte = self.regs.get(self.pointer, 0)
            self.selected = ack
        else:
            ack = self.selected
            if self.byte_number == 1:
                self.pointer = value << 8
            elif self.byte_number == 2:
                self.pointer |= value
            else:
                if self.pointer == 0x3008 and value == 0x82:
                    self.regs = {0x300A:0x56,0x300B:0x40}
                self.regs[self.pointer] = value
        self.byte_number += 1
        self.ack_next = ack

    def write(self, offset, value):
        assert offset == 0
        new_scl, new_master = not bool(value & 4), not bool(value & 8)
        old_effective = self.master_sda and not self.slave_low
        new_effective = new_master and not self.slave_low
        if self.scl and new_scl and old_effective != new_effective:
            if not new_effective:  # START
                self.mode = 'rx'; self.bits = self.byte = self.byte_number = 0
            else:                 # STOP
                self.mode = 'idle'; self.slave_low = False
        elif not self.scl and new_scl:
            if self.mode == 'rx':
                self.byte = (self.byte << 1) | int(new_effective)
                self.bits += 1
                if self.bits == 8:
                    self._byte_received(self.byte)
                    self.mode = 'prepare_ack'
            elif self.mode == 'ack':
                self.acks += 1
            elif self.mode == 'master_nack':
                self.nacks.append(new_master)
        elif self.scl and not new_scl:
            if self.mode == 'prepare_ack':
                self.slave_low = self.ack_next; self.mode = 'ack'
            elif self.mode == 'ack':
                self.slave_low = False
                self.mode = self.next_mode
                self.bits = self.byte = 0
                if self.mode == 'tx':
                    self.tx_pos = 0
                    self.slave_low = not bool(self.tx_byte & 128)
            elif self.mode == 'tx':
                self.tx_pos += 1
                if self.tx_pos == 8:
                    self.slave_low = False; self.mode = 'master_nack'
                else:
                    self.slave_low = not bool(self.tx_byte & (128 >> self.tx_pos))
            elif self.mode == 'master_nack':
                self.mode = 'wait_stop'
        self.scl, self.master_sda, self.control = new_scl, new_master, value

class Dummy:
    def read(self, offset): return 0

def make(bus):
    return camera_run.Camera(SimpleNamespace(axi_gpio_control=bus,axi_gpio_counts=Dummy(),
        axi_gpio_diag=Dummy(),axi_gpio_clock=Dummy()),Path(__file__).resolve().parents[1]/'config',0)

def main():
    original_sleep = camera_run.time.sleep
    camera_run.time.sleep = lambda _: None
    try:
        bus = Wires()
        camera = make(bus)
        assert camera.reset_and_identify() == 0x5640
        for value in (0,255,0xA5,0x5A):
            camera.write_reg(0x503D,value)
            assert bus.regs[0x503D] == value
            assert camera.read_reg(0x503D) == value
        assert bus.nacks and all(bus.nacks), 'single-byte reads must end with master NACK'
        camera.configure()
        assert camera.initialized and bus.regs[0x3808] == 1 and bus.regs[0x3809] == 0x40
        assert bus.regs[0x380A] == 0 and bus.regs[0x380B] == 0xF0
        camera.show_live(); assert bus.regs[0x503D] == 0
        missing = make(Wires(False))
        try: missing.reset_and_identify()
        except RuntimeError as error: assert '无应答' in str(error)
        else: raise AssertionError('missing sensor was accepted')
        stuck_bus = Wires(); stuck = make(stuck_bus); stuck_bus.force_scl_low = True
        try: stuck._raise_scl()
        except RuntimeError as error: assert 'SCL' in str(error)
        else: raise AssertionError('stuck SCL did not time out')
        print('PASS SCCB: wire-level start/stop, device address, register reads/writes, ACK/NACK, full configuration/readback, absent sensor, stuck SCL timeout')
    finally:
        camera_run.time.sleep = original_sleep

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
