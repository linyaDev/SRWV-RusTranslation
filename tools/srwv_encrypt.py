"""
Encrypt files for Super Robot Wars V CPK archives.
Uses Blowfish ECB (big-endian) with key "SRVW Steam Game".
Usage: python srwv_encrypt.py <input_dir> <output_dir>
       python srwv_encrypt.py <input_file> <output_file>
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
    rem = len(data) % 4
    if rem:
        out[-(rem):] = data[-(rem):]
    return bytes(out)

def encrypt_file(inpath, outpath):
    cipher = Blowfish.new(KEY, Blowfish.MODE_ECB)
    with open(inpath, 'rb') as f:
        data = f.read()
    remainder = len(data) % 8
    if remainder:
        plaintext = data[:-remainder]
        tail = data[-remainder:]
    else:
        plaintext = data
        tail = b''
    # SRW V uses big-endian Blowfish: swap 4-byte words before and after
    swapped = swap_endian_words(plaintext)
    encrypted_swapped = cipher.encrypt(swapped)
    encrypted = swap_endian_words(encrypted_swapped) + tail
    os.makedirs(os.path.dirname(outpath) if os.path.dirname(outpath) else '.', exist_ok=True)
    with open(outpath, 'wb') as f:
        f.write(encrypted)

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input_dir_or_file> <output_dir_or_file>")
        sys.exit(1)
    inpath = sys.argv[1]
    outpath = sys.argv[2]
    if os.path.isfile(inpath):
        print(f"Encrypting: {os.path.basename(inpath)}")
        encrypt_file(inpath, outpath)
    else:
        for root, dirs, files in os.walk(inpath):
            for fname in files:
                inp = os.path.join(root, fname)
                relpath = os.path.relpath(inp, inpath)
                outp = os.path.join(outpath, relpath)
                print(f"Encrypting: {relpath}")
                encrypt_file(inp, outp)
    print("Done!")

if __name__ == '__main__':
    main()
