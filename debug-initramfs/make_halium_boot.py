#!/usr/bin/env python3
import struct
import sys

def pages(size, page_size):
    return (size + page_size - 1) // page_size

def pad(data, page_size):
    rem = len(data) % page_size
    if rem:
        data += b"\x00" * (page_size - rem)
    return data

def main(orig_path, new_kernel_path, new_ramdisk_path, out_path, extra_cmdline_add=""):
    orig = open(orig_path, "rb").read()
    assert orig[0:8] == b"ANDROID!"

    (kernel_size, kernel_addr,
     ramdisk_size, ramdisk_addr,
     second_size, second_addr,
     tags_addr, page_size,
     header_version, os_version) = struct.unpack("<IIIIIIIIII", orig[8:48])
    name = orig[48:64]
    cmdline = orig[64:576]
    img_id = orig[576:608]
    extra_cmdline = orig[608:1632]
    recovery_dtbo_size, recovery_dtbo_offset, header_size = struct.unpack("<IQI", orig[1632:1648])
    dtb_size, dtb_addr = struct.unpack("<IQ", orig[1648:1660])

    off2 = pages(kernel_size, page_size) * page_size + page_size + pages(ramdisk_size, page_size) * page_size
    orig_second = orig[off2:][:second_size]
    off3 = off2 + pages(second_size, page_size) * page_size
    orig_dtb = orig[off3:][:dtb_size]

    new_kernel = open(new_kernel_path, "rb").read()
    new_ramdisk = open(new_ramdisk_path, "rb").read()
    new_kernel_size = len(new_kernel)
    new_ramdisk_size = len(new_ramdisk)

    if extra_cmdline_add:
        current = extra_cmdline.rstrip(b"\x00").decode()
        new_extra = (current + " " + extra_cmdline_add).strip()
        extra_cmdline = new_extra.encode().ljust(1024, b"\x00")
        print(f"cmdline (base): {cmdline.rstrip(chr(0).encode()).decode()!r}")
        print(f"extra_cmdline (new): {new_extra!r}")

    header = b"ANDROID!"
    header += struct.pack(
        "<IIIIIIIIII",
        new_kernel_size, kernel_addr,
        new_ramdisk_size, ramdisk_addr,
        second_size, second_addr,
        tags_addr, page_size,
        header_version, os_version,
    )
    header += name
    header += cmdline
    header += img_id
    header += extra_cmdline
    header += struct.pack("<IQI", recovery_dtbo_size, recovery_dtbo_offset, header_size)
    header += struct.pack("<IQ", dtb_size, dtb_addr)
    header = pad(header, page_size)
    assert len(header) == page_size, f"header does not fit in one page: {len(header)}"

    out = header
    out += pad(new_kernel, page_size)
    out += pad(new_ramdisk, page_size)
    out += pad(orig_second, page_size)
    out += pad(orig_dtb, page_size)

    if len(out) < len(orig):
        out += b"\x00" * (len(orig) - len(out))
    elif len(out) > len(orig):
        print(f"WARNING: new image ({len(out)} bytes) is larger than the original "
              f"boot partition size ({len(orig)} bytes) — will NOT fit, do not flash this.")

    with open(out_path, "wb") as f:
        f.write(out)

    print(f"Wrote {out_path}: {len(out)} bytes (kernel {new_kernel_size}, "
          f"ramdisk {new_ramdisk_size}, dtb {dtb_size}, orig partition size {len(orig)})")

if __name__ == "__main__":
    extra = sys.argv[5] if len(sys.argv) > 5 else ""
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], extra)
