"""
Decrypt files extracted from Super Robot Wars V CPK archives.
Uses Blowfish ECB (big-endian) with key "SRVW Steam Game".
Usage: python srwv_decrypt.py <input_dir> <output_dir>
"""
import sys
import os
import struct
from Crypto.Cipher import Blowfish

KEY = b"SRVW Steam Game"

def swap_endian_words(data):
    """Swap byte order of each 4-byte word (BE <-> LE)."""
    out = bytearray(len(data))
    for i in range(0, len(data) - 3, 4):
        out[i:i+4] = struct.pack('<I', struct.unpack('>I', data[i:i+4])[0])
    # handle trailing bytes that don't fill a word
    rem = len(data) % 4
    if rem:
        out[-(rem):] = data[-(rem):]
    return bytes(out)

def decrypt_file(inpath, outpath):
    cipher = Blowfish.new(KEY, Blowfish.MODE_ECB)
    with open(inpath, 'rb') as f:
        data = f.read()
    # Blowfish ECB works on 8-byte blocks
    remainder = len(data) % 8
    if remainder:
        encrypted = data[:-remainder]
        tail = data[-remainder:]
    else:
        encrypted = data
        tail = b''
    # SRW V uses big-endian Blowfish: swap 4-byte words before and after
    swapped = swap_endian_words(encrypted)
    decrypted_swapped = cipher.decrypt(swapped)
    decrypted = swap_endian_words(decrypted_swapped) + tail
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    with open(outpath, 'wb') as f:
        f.write(decrypted)

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input_dir> <output_dir>")
        sys.exit(1)
    indir = sys.argv[1]
    outdir = sys.argv[2]
    for root, dirs, files in os.walk(indir):
        for fname in files:
            inpath = os.path.join(root, fname)
            relpath = os.path.relpath(inpath, indir)
            outpath = os.path.join(outdir, relpath)
            print(f"Decrypting: {relpath}")
            decrypt_file(inpath, outpath)
    print("Done!")

if __name__ == '__main__':
    main()
