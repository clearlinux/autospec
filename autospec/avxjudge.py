#!/usr/bin/python3
import subprocess
import sys
import re
import argparse
import os

# MMX and SSE2 instructions
sse_instructions_xmm = list()

# 0.1 value instructions
avx2_instructions_lv = list()
avx2_instructions_ymm = list()
avx512_instructions_lv = list()


# 1.0 value instructions
avx2_instructions = list()
avx512_instructions = list()

# 2.0 value instructions
avx2_instructions_hv = list()
avx512_instructions_hv = list()




sse_functions = dict()
avx2_functions = dict()
avx512_functions = dict()
sse_functions_ratio = dict()
avx2_functions_ratio = dict()
avx512_functions_ratio = dict()


verbose: int = 0
quiet: int = 0




def init_ins() -> None:


    sse_instructions_xmm.append("paddb")
    sse_instructions_xmm.append("paddd")
    sse_instructions_xmm.append("paddsb")
    sse_instructions_xmm.append("paddsw")
    sse_instructions_xmm.append("paddusb")
    sse_instructions_xmm.append("paddusw")
    sse_instructions_xmm.append("paddw")
    sse_instructions_xmm.append("pmaddwd")
    sse_instructions_xmm.append("pmulhw")
    sse_instructions_xmm.append("pmullw")
    sse_instructions_xmm.append("psubb")
    sse_instructions_xmm.append("psubsb")
    sse_instructions_xmm.append("psubsw")
    sse_instructions_xmm.append("psubusb")
    sse_instructions_xmm.append("paddusw")
    sse_instructions_xmm.append("paddw")
    sse_instructions_xmm.append("pmaddwd")
    sse_instructions_xmm.append("pmulhw")
    sse_instructions_xmm.append("pmullw")
    sse_instructions_xmm.append("psubb")
    sse_instructions_xmm.append("psubd")
    sse_instructions_xmm.append("psubd")
    sse_instructions_xmm.append("psubsb")
    sse_instructions_xmm.append("psubsw")
    sse_instructions_xmm.append("psubusb")
    sse_instructions_xmm.append("psubusw")
    sse_instructions_xmm.append("psubw")


    avx2_instructions_lv.append("shrx")
    avx2_instructions_lv.append("rorx")
    avx2_instructions_lv.append("shlx")
    avx2_instructions_lv.append("shrx")
    avx2_instructions_lv.append("shrx")
    avx2_instructions_lv.append("movbe")


    avx2_instructions_ymm.append("vpaddq")
    avx2_instructions_ymm.append("vpaddd")
    avx2_instructions_ymm.append("vpsubq")
    avx2_instructions_ymm.append("vpsubd")
    avx2_instructions_ymm.append("vmulpd")
    avx2_instructions_ymm.append("vaddpd")
    avx2_instructions_ymm.append("vsubpd")
    avx2_instructions_ymm.append("vmulps")
    avx2_instructions_ymm.append("vaddps")
    avx2_instructions_ymm.append("vsubps")
    avx2_instructions_ymm.append("vpmaxsq")
    avx2_instructions_ymm.append("vpminsq")
    avx2_instructions_ymm.append("vpmuludq")
    avx2_instructions_ymm.append("vpand")
    avx2_instructions_ymm.append("vpmaxud")
    avx2_instructions_ymm.append("vpminud")
    avx2_instructions_ymm.append("vpmaxsd")
    avx2_instructions_ymm.append("vpmaxsw")
    avx2_instructions_ymm.append("vpminsd")
    avx2_instructions_ymm.append("vpminsw")
    avx2_instructions_ymm.append("vpand")
    avx2_instructions_ymm.append("vpor")
    avx2_instructions_ymm.append("vpmulld")


    avx2_instructions.append("vfmadd132ss")
    avx2_instructions.append("vfmadd213ss")
    avx2_instructions.append("vfmadd231ss")
    avx2_instructions.append("vfmadd132sd")
    avx2_instructions.append("vfmadd231sd")
    avx2_instructions.append("vfmadd213sd")

    avx2_instructions.append("vfmsub132ss")
    avx2_instructions.append("vfmsub213ss")
    avx2_instructions.append("vfmsub231ss")
    avx2_instructions.append("vfmsub132sd")
    avx2_instructions.append("vfmsub231sd")
    avx2_instructions.append("vfmsub213sd")

    avx2_instructions.append("vfnmadd132ss")
    avx2_instructions.append("vfnmadd213ss")
    avx2_instructions.append("vfnmadd231ss")
    avx2_instructions.append("vfnmadd132sd")
    avx2_instructions.append("vfnmadd231sd")
    avx2_instructions.append("vfnmadd213sd")

    avx2_instructions.append("vfnmsub132ss")
    avx2_instructions.append("vfnmsub213ss")
    avx2_instructions.append("vfnmsub231ss")
    avx2_instructions.append("vfnmsub132sd")
    avx2_instructions.append("vfnmsub231sd")
    avx2_instructions.append("vfnmsub213sd")

    avx2_instructions_hv.append("vpclmulhqlqdq")
    avx2_instructions_hv.append("vpclmullqhqdq")

    avx2_instructions_hv.append("vfmadd132ps")
    avx2_instructions_hv.append("vfmadd213ps")
    avx2_instructions_hv.append("vfmadd231ps")
    avx2_instructions_hv.append("vfmadd132pd")
    avx2_instructions_hv.append("vfmadd231pd")
    avx2_instructions_hv.append("vfmadd213pd")
    avx2_instructions_hv.append("vfmsub132ps")
    avx2_instructions_hv.append("vfmsub213ps")
    avx2_instructions_hv.append("vfmsub231ps")
    avx2_instructions_hv.append("vfmsub132pd")
    avx2_instructions_hv.append("vfmsub231pd")
    avx2_instructions_hv.append("vfmsub213pd")

    avx2_instructions_hv.append("vfnmadd132ps")
    avx2_instructions_hv.append("vfnmadd213ps")
    avx2_instructions_hv.append("vfnmadd231ps")
    avx2_instructions_hv.append("vfnmadd132pd")
    avx2_instructions_hv.append("vfnmadd231pd")
    avx2_instructions_hv.append("vfnmadd213pd")
    avx2_instructions_hv.append("vfnmsub132ps")
    avx2_instructions_hv.append("vfnmsub213ps")
    avx2_instructions_hv.append("vfnmsub231ps")
    avx2_instructions_hv.append("vfnmsub132pd")
    avx2_instructions_hv.append("vfnmsub231pd")
    avx2_instructions_hv.append("vfnmsub213pd")
    avx2_instructions_hv.append("vdivpd")


    return

def is_sse(instruction:str, args:str) -> float:

    val: float = -1.0
    if "xmm" in args:
        if ("pd" in instruction or "ps" in instruction or instruction in sse_instructions_xmm):
            val = 1.0
        else:
            val = 0.01
    return val


def is_avx2(instruction:str, args:str) -> float:
    val: float = -1.0

    if "ymm" in args:
        if ("pd" in instruction or "ps" in instruction or instruction in avx2_instructions_ymm) and "xor" not in instruction and "vmov" not in instruction:
            val = 1.0
        else:
            val = 0.01

    if instruction in avx2_instructions_lv:
        val = max(val, 0.1)
    if instruction in avx2_instructions:
        val = max(val, 1.0)
    if instruction in avx2_instructions_hv:
        val = max(val, 2.0)

    return val

def has_high_register(args: str) -> int:
    if "mm16" in args:
        return 1
    if "mm17" in args:
        return 1
    if "mm18" in args:
        return 1
    if "mm19" in args:
        return 1
    if "mm20" in args:
        return 1
    if "mm21" in args:
        return 1
    if "mm22" in args:
        return 1
    if "mm23" in args:
        return 1
    if "mm24" in args:
        return 1
    if "mm25" in args:
        return 1
    if "mm26" in args:
        return 1
    if "mm27" in args:
        return 1
    if "mm28" in args:
        return 1
    if "mm29" in args:
        return 1
    if "mm30" in args:
        return 1
    if "mm31" in args:
        return 1
    return 0

def is_avx512(instruction:str, args:str) -> float:
    val: float = -1.0

    if instruction in avx512_instructions_lv:
        val = max(val, 0.1)
    if instruction in avx512_instructions:
        val = max(val, 1.0)
    if instruction in avx512_instructions_hv:
        val = max(val, 2.0)

    if "xor" not in instruction and "ymm" in args and has_high_register(args):
        val = max(val, 0.02)
    if "xor" not in instruction and has_high_register(args):
        val = max(val, 0.01)

    if "zmm" in args:
        if ("pd" in instruction or "ps" in instruction or "vpadd" in instruction or "vpsub" in instruction or instruction in avx2_instructions_ymm) and "xor" not in instruction and "vmov" not in instruction:
            val = max(val, 1.0)
        else:
            val = max(val, 0.01)
        if is_avx2(instruction, args) > 0:
            val = max(val, is_avx2(instruction, args))


    return val

def ratio(f: float) -> str:
    f = f * 100
    f = round(f)/100.0
    return str(f)



def print_top_functions() -> None:

    print("Top SSE functions by instruction count")
    count = 0
    for f in sorted(sse_functions_ratio, key=sse_functions_ratio.get, reverse=True):
        if count < 5:
            sf = f
            while len(sf) < 30:
                sf = sf + " "
            print("    ",sf, "\t", ratio(sse_functions_ratio[f]),"%")
            count += 1

    print()
    print("Top SSE functions by value")
    count = 0
    for f in sorted(sse_functions, key=sse_functions.get, reverse=True):
        if count < 5:
            sf = f
            while len(sf) < 30:
                sf = sf + " "
            print("    ",sf, "\t", ratio(sse_functions[f]))
            count += 1

    print()

    print("Top AVX2 functions by instruction count")
    count = 0
    for f in sorted(avx2_functions_ratio, key=avx2_functions_ratio.get, reverse=True):
        if count < 5:
            sf = f
            while len(sf) < 30:
                sf = sf + " "
            print("    ",sf, "\t", ratio(avx2_functions_ratio[f]),"%")
            count += 1

    print()
    print("Top AVX2 functions by value")
    count = 0
    for f in sorted(avx2_functions, key=avx2_functions.get, reverse=True):
        if count < 5:
            sf = f
            while len(sf) < 30:
                sf = sf + " "
            print("    ",sf, "\t", ratio(avx2_functions[f]))
            count += 1

    print()

    print("Top AVX512 functions by instruction count")
    count = 0
    for f in sorted(avx512_functions_ratio, key=avx512_functions_ratio.get, reverse=True):
        if count < 5:
            sf = f
            while len(sf) < 30:
                sf = sf + " "
            print("    ",sf, "\t", ratio(avx512_functions_ratio[f]),"%")
            count += 1

    print()
    print("Top AVX512 functions by value")
    count = 0
    for f in sorted(avx512_functions, key=avx512_functions.get, reverse=True):
        if count < 5:
            sf = f
            while len(sf) < 30:
                sf = sf + " "
            print("    ",sf, "\t", ratio(avx512_functions[f]))
            count += 1

    return


def do_file(filename: str,quiet: int) -> None:

    global total_sse_count
    global total_avx2_count
    global total_avx512_count

    global total_sse_score
    global total_avx2_score
    global total_avx512_score

    init_ins()

    if verbose:
        print("Analyzing", filename)

    function = ""

    sse_count = 0
    avx2_count = 0
    avx512_count = 0

    sse_score = 0.0
    avx2_score = 0.0
    avx512_score = 0.0

    instructions = 0

    total_sse_count = 0
    total_avx2_count = 0
    total_avx512_count = 0

    total_sse_score = 0.0
    total_avx2_score = 0.0
    total_avx512_score = 0.0


    out, err = subprocess.Popen(["objdump","-d", filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    alllines = out.decode("latin-1")
    lines =  alllines.split("\n")

    for line in lines:
        score_sse = -1.0
        score_avx2 = -1.0
        score_avx512 = -1.0

        sse_str = " "
        avx2_str = " "
        avx512_str = ""

        match = re.search(".*[0-9a-f]+\:\t[0-9a-f\ ]+\t([a-zA-Z0-9]+) (.*)", line)

        if match:
            ins = match.group(1)
            arg = match.group(2)

            score_sse = is_sse(ins, arg)
            score_avx2 = is_avx2(ins, arg)
            score_avx512 = is_avx512(ins, arg)

            avx2_str= " "
            instructions += 1

        match = re.search("\<([a-zA-Z0-9_@\.\-]+)\>\:", line)
        if match:
            funcname = match.group(1)
            if instructions > 0 and verbose > 0:
                print(function,"\t",ratio(sse_count/instructions),"\t", ratio(avx2_count / instructions), "\t", ratio(avx512_count/instructions), "\t", avx2_score,"\t", avx512_score)

            if sse_count >= 1:
                sse_functions[function] = sse_score
                sse_functions_ratio[function] = 100.0 * sse_count / instructions
            if avx2_count >= 1:
                avx2_functions[function] = avx2_score
                avx2_functions_ratio[function] = 100.0 * avx2_count / instructions
            if avx512_count >= 1:
                avx512_functions[function] = avx512_score
                avx512_functions_ratio[function] = 100.0 * avx512_count/instructions

            total_sse_count += sse_count
            total_sse_score += sse_score

            total_avx2_count += avx2_count
            total_avx2_score += avx2_score

            total_avx512_count += avx512_count
            total_avx512_score += avx512_score

            instructions = 0
            function = funcname


            sse_count = 0
            avx2_count = 0
            avx512_count = 0

            sse_score = 0.0
            avx2_score = 0.0
            avx512_score = 0.0

        if score_sse >= 0.0:
            sse_str = str(score_sse)
            sse_score += score_sse
            sse_count += 1

        if score_avx2 >= 0.0:
            avx2_str = str(score_avx2)
            avx2_score += score_avx2
            avx2_count += 1

        if score_avx512 >= 0.0:
            avx512_str = str(score_avx512)
            avx512_score += score_avx512
            avx512_count += 1


        if verbose:
            print(sse_str,"\t",avx2_str,"\t", avx512_str,"\t", line)
    if not quiet:
        print_top_functions()
        print()
        print("File total (SSE): ", total_sse_count,"instructions with score", round(total_sse_score))
        print("File total (AVX2): ", total_avx2_count,"instructions with score", round(total_avx2_score))
        print("File total (AVX512): ", total_avx512_count,"instructions with score", round(total_avx512_score))
        print()
    return total_sse_count


def main():
    global verbose
    global total_avx2_count
    global total_avx512_count
    global total_avx2_score
    global total_avx512_score
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
    parser.add_argument("-1", "--unlinksse", help="unlink the file if it has no SSE instructions", action="store_true")
    parser.add_argument("-2", "--unlinkavx2", help="unlink the file if it has no AVX2 instructions", action="store_true")
    parser.add_argument("-5", "--unlinkavx512", help="unlink the file if it has no AVX512 instructions", action="store_true")
    parser.add_argument("filename", help = "The filename to inspect")

    args = parser.parse_args()
    if args.verbose:
        verbose = 1

    quiet = 0
    do_file(args.filename,quiet)

    if args.unlinksse:
        if total_sse_count < 10 and total_sse_score <= 1.0:
            print(args.filename, "\tsse count:", total_sse_count,"\tsse value:", ratio(total_sse_score))
            try:
                os.unlink(args.filename)
            except:
                None

    if args.unlinkavx2:
        if total_avx2_count < 10 and total_avx2_score <= 1.0:
            print(args.filename, "\tavx2 count:", total_avx2_count,"\tavx2 value:", ratio(total_avx2_score))
            try:
                os.unlink(args.filename)
            except:
                None

    if args.unlinkavx512:
        if total_avx512_count < 10 and total_avx512_score < 2.0:
            print(args.filename, "\tavx512 count:", total_avx512_count,"\tavx512 value:", ratio(total_avx512_score))
            try:
                os.unlink(args.filename)
            except:
                None



if __name__ == '__main__':
    main()

