# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.
#
# This code was inspired in the autotest project,
#
# Copyright (C) 2025 AMD Inc.
# Author: Gautham R. Shenoy <gautham.shenoy@amd.com>
# Author: Swapnil Sapkal <swaipnil.sapkal@amd.com>


from avocado.utils import cpu, process

topo_type_to_name = {0: "RESERVED", 1: "CORE", 2: "CCX", 3: "CCD", 4: "PKG"}
topo_name_to_type = {"RESERVED": 0, "CORE": 1, "CCX": 2, "CCD": 3, "PKG": 4}


class TopoRegs:
    """
    Models the registers and their contents for CPUID 0x80000026
    """

    def __init__(self, eax, ebx, ecx, edx):
        self.eax = eax
        self.ebx = ebx
        self.ecx = ecx
        self.edx = edx

        self.core_mask_width_spec = (eax, 0, 4)
        self.nr_threads_spec = (ebx, 0, 15)
        self.sub_leaf_spec = (ecx, 0, 7)
        self.level_type_spec = (ecx, 8, 15)
        self.apic_id_spec = (edx, 0, 31)

        self.core_mask_width = self.get_core_mask_width()
        self.nr_threads = self.get_nr_threads()
        self.sub_leaf = self.get_sub_leaf()
        self.level_type = self.get_level_type_int()
        self.level_name = self.get_level_type_name()
        self.apic_id = self.get_apic_id()
        self.level_id = self.apic_id >> self.core_mask_width
        self.mask = gen_lsb_mask(self.core_mask_width)

    def __parse_obj(self, obj):
        (reg, start, end) = obj
        return extract_bits(reg, start, end)

    def get_core_mask_width(self):
        return self.__parse_obj(self.core_mask_width_spec)

    def get_nr_threads(self):
        return self.__parse_obj(self.nr_threads_spec)

    def get_sub_leaf(self):
        return self.__parse_obj(self.sub_leaf_spec)

    def get_level_type_int(self):
        return self.__parse_obj(self.level_type_spec)

    def get_level_type_name(self):
        return topo_type_to_name[self.__parse_obj(self.level_type_spec)]

    def get_apic_id(self):
        return self.__parse_obj(self.apic_id_spec)


class CpuTopo80000026:
    """
    Models the output of CPUID 0x80000026 for a cpu
    """

    def __init__(self, cpu_no):
        sub_leaf = 0
        self.levels = {}
        self.cpu_topology = {}
        while True:
            self.cpu_no = cpu_no
            (eax, ebx, ecx, edx) = cpu.get_cpuid_leaf(cpu_no, "0x80000026", sub_leaf)
            topo_reg = TopoRegs(eax, ebx, ecx, edx)

            if topo_reg.level_type == 0:
                break

            self.levels[topo_reg.level_name] = topo_reg
            sub_leaf = sub_leaf + 1

    def get_cpu_topo(self, kernel_mode=False):
        pkg_mask = self.levels["PKG"].mask
        core_mask = self.levels["CORE"].mask
        apic_id = self.levels["CORE"].apic_id
        thread_id = apic_id & core_mask

        self.cpu_topology["CPU"] = self.cpu_no
        self.cpu_topology["THREAD"] = thread_id

        for k in self.levels.keys():
            topo_reg = self.levels[k]
            """
            kernel core_id is unique only within socket, this case returns core_id within socket
            when kernel_mode is true
            """
            if kernel_mode == True and topo_reg.level_type == topo_name_to_type["CORE"]:
                level_id = (topo_reg.apic_id & pkg_mask) >> topo_reg.core_mask_width
            else:
                level_id = topo_reg.level_id
            self.cpu_topology[k] = level_id
        return self.cpu_topology


def gen_lsb_mask(nr_bits):
    return (1 << nr_bits) - 1


def extract_bits(val, start_bit, end_bit):
    nr_bits = end_bit - start_bit + 1
    lsb_mask = gen_lsb_mask(nr_bits)
    return (val >> start_bit) & lsb_mask


def get_cpuid_80000026_topo():
    topo = {}
    for i in range(0, cpu.total_count()):
        top = CpuTopo80000026(i)
        topo[i] = top.get_cpu_topo(True)
    return topo


def get_kernel_topology(cpuid_bin_path=None):
    topo = {}
    nr_cpus = int(process.run("nproc", shell=True).stdout.decode())

    for i in range(0, nr_cpus):
        cpuid_output = process.run(
            f"taskset -c {i} {cpuid_bin_path} 0x0000000b", shell=True
        ).stdout.decode()
        val = cpuid_output.split(":")[1].split()[3].split("=")[1].split("x")[1]
        decval = int(val, 16)
        thread_id = decval % 2

        syspath = "/sys/devices/system/cpu"
        core_id = int(
            process.run(
                f"cat {syspath}/cpu{i}/topology/core_id", shell=True
            ).stdout.decode()
        )
        ccx_id = int(
            process.run(
                f"cat {syspath}/cpu{i}/cache/index3/id", shell=True
            ).stdout.decode()
        )
        die_id = int(
            process.run(
                f"cat {syspath}/cpu{i}/topology/die_id", shell=True
            ).stdout.decode()
        )
        pkg_id = int(
            process.run(
                f"cat {syspath}/cpu{i}/topology/physical_package_id", shell=True
            ).stdout.decode()
        )

        topo[i] = {}
        topo[i]["CPU"] = i
        topo[i]["THREAD"] = thread_id
        topo[i]["CORE"] = core_id
        topo[i]["CCX"] = ccx_id
        topo[i]["CCD"] = die_id
        topo[i]["PKG"] = pkg_id
    return topo
