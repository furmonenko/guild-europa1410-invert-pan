"""Invert middle-mouse camera panning in The Guild 1 Remake: Europa 1410.

The game binds IA_MoveCamera to Mouse2D with an IA_MMB_Hold chord and no modifiers
(IMC_Game), so the camera follows the cursor. This adds the existing
InputModifierNegate subobject to that one mapping; keyboard panning is untouched.

    python build.py tools               download pinned repak/retoc into tools/
    python build.py build               extract IMC_Game, patch it, build dist/ZZ_InvertPan_P.{pak,utoc,ucas}
    python build.py package             build, then zip the mod for a release
    python build.py install|uninstall   copy the mod into / remove it from the game's Paks/~mods

Pass --game <dir> if the game is not in the default Steam library.
"""
import argparse
import hashlib
import io
import shutil
import struct
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK, DIST, TOOLS = ROOT / 'work', ROOT / 'dist', ROOT / 'tools'
DEFAULT_GAME = r'C:\Program Files (x86)\Steam\steamapps\common\The Guild - Europa 1410'
MOD_NAME = 'ZZ_InvertPan_P'
MOD_VERSION = '1.0.0'
ENGINE_VERSION = 'UE5_6'
ASSET = 'Europa1410/Content/Blueprints/Input/MappingContexts/IMC_Game'
EXPORT_ENTRY = 96  # FObjectExport size in this package version
TOOLS_PINNED = {
    'repak': ('https://github.com/trumank/repak/releases/download/v0.2.3/repak_cli-x86_64-pc-windows-msvc.zip',
              '6720d602144d75df477a99d5bedb6ea780997546afc335901d4937cafeaa73fa'),
    'retoc': ('https://github.com/trumank/retoc/releases/download/v0.1.5/retoc_cli-x86_64-pc-windows-msvc.zip',
              'cc036b06ad3bdcf7003690b00d82719980c374e48a95bf0654f9959148d263aa'),
}


def tool(name):
    exe = TOOLS / name / f'{name}.exe'
    if not exe.exists():
        sys.exit(f'{exe} not found - run `python build.py tools` first')
    return str(exe)


def i32(buf, at):
    return struct.unpack_from('<i', buf, at)[0]


def read_package(head):
    names, at = [], i32(head, 0x70)
    for _ in range(i32(head, 0x6c)):
        length = i32(head, at)
        at += 4
        if length < 0:
            names.append(head[at:at - 2 * length].decode('utf-16le')[:-1])
            at += -2 * length
        else:
            names.append(head[at:at + length - 1].decode())
            at += length
        at += 4  # name hash
    imports = [names[i32(head, i32(head, 0x90) + 32 * i + 20)] for i in range(i32(head, 0x8c))]
    exports = []
    for i in range(i32(head, 0x84)):
        at = i32(head, 0x88) + EXPORT_ENTRY * i
        exports.append((names[i32(head, at + 16)], i32(head, at + 16 + 4), at))
    return names, imports, exports


def patch(head, body):
    names, imports, exports = read_package(head)
    if names[:1] != ['A'] or 'Mouse2D' not in names or 'IA_MoveCamera' not in imports:
        sys.exit('IMC_Game layout changed - inspect it before patching')
    move_camera = -(imports.index('IA_MoveCamera') + 1)
    negate = next(i for i, (name, num, _) in enumerate(exports, 1)
                  if name == 'InputModifierNegate' and num == 1)  # InputModifierNegate_0, all axes
    # Mouse2D mapping: Modifiers = [] -> [negate], followed by Action and FKey{KeyName}.
    tail = struct.pack('<i', move_camera) + b'\x00\x03' + struct.pack('<ii', names.index('Mouse2D'), 0)
    old = struct.pack('<i', 0) + tail
    if body.count(old) != 1:
        sys.exit(f'expected one unmodified Mouse2D->IA_MoveCamera mapping, found {body.count(old)}')
    at = body.index(old)
    body = body[:at] + struct.pack('<ii', 1, negate) + tail + body[at + len(old):]

    head = bytearray(head)
    header_size = len(head)
    for _, _, entry in exports:
        size, offset = struct.unpack_from('<qq', head, entry + 28)
        if offset - header_size <= at < offset - header_size + size:
            struct.pack_into('<q', head, entry + 28, size + 4)
        elif offset - header_size > at:
            struct.pack_into('<q', head, entry + 36, offset + 4)
    bulk_start = struct.unpack_from('<q', head, 0xf8)[0]
    if bulk_start != header_size + len(body) - 4 - 4:  # body still holds the +4, minus package tag
        sys.exit('unexpected BulkDataStartOffset')
    struct.pack_into('<q', head, 0xf8, bulk_start + 4)
    return bytes(head), body


def cmd_tools(args):
    for name, (url, sha) in TOOLS_PINNED.items():
        if (TOOLS / name / f'{name}.exe').exists():
            print(f'{name}: already present')
            continue
        data = urllib.request.urlopen(url).read()
        if hashlib.sha256(data).hexdigest() != sha:
            sys.exit(f'{name}: sha256 mismatch, refusing to use {url}')
        zipfile.ZipFile(io.BytesIO(data)).extractall(TOOLS / name)
        print(f'{name}: installed')


def cmd_build(args):
    paks = Path(args.game) / 'Europa1410/Content/Paks'
    if not paks.is_dir():
        sys.exit(f'{paks} not found - pass --game <game dir>')
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.rmtree(DIST, ignore_errors=True)
    subprocess.run([tool('retoc'), 'to-legacy', '--no-shaders', '--no-script-objects', '--filter', 'IMC_Game',
                    '--version', ENGINE_VERSION, paks, WORK / 'original'], check=True, stdout=subprocess.DEVNULL)
    src = WORK / 'original' / ASSET
    head, body = patch(src.with_suffix('.uasset').read_bytes(), src.with_suffix('.uexp').read_bytes())
    dst = WORK / MOD_NAME / ASSET
    dst.parent.mkdir(parents=True)
    dst.with_suffix('.uasset').write_bytes(head)
    dst.with_suffix('.uexp').write_bytes(body)

    DIST.mkdir()
    subprocess.run([tool('retoc'), 'to-zen', '--version', ENGINE_VERSION, WORK / MOD_NAME,
                    DIST / f'{MOD_NAME}.utoc'], check=True, stdout=subprocess.DEVNULL)
    if not (DIST / f'{MOD_NAME}.pak').exists():  # UE5 mounts the IoStore pair only next to a .pak
        empty = WORK / 'empty' / MOD_NAME
        empty.mkdir(parents=True)
        (empty / 'placeholder.txt').write_text('InvertPan\n')
        subprocess.run([tool('repak'), 'pack', '--quiet', '--version', 'V11', empty], check=True)
        shutil.move(WORK / 'empty' / f'{MOD_NAME}.pak', DIST / f'{MOD_NAME}.pak')
    print(f'built {DIST}')


def cmd_package(args):
    cmd_build(args)
    out = DIST / f'Europa1410-InvertPan-{MOD_VERSION}.zip'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for ext in ('pak', 'utoc', 'ucas'):
            z.write(DIST / f'{MOD_NAME}.{ext}', f'{MOD_NAME}.{ext}')
    print(f'packaged {out}')


def cmd_install(args):
    cmd_build(args)
    mods = Path(args.game) / 'Europa1410/Content/Paks/~mods'
    mods.mkdir(exist_ok=True)
    for ext in ('pak', 'utoc', 'ucas'):
        shutil.copy2(DIST / f'{MOD_NAME}.{ext}', mods / f'{MOD_NAME}.{ext}')
    print(f'installed into {mods}')


def cmd_uninstall(args):
    for ext in ('pak', 'utoc', 'ucas'):
        (Path(args.game) / 'Europa1410/Content/Paks/~mods' / f'{MOD_NAME}.{ext}').unlink(missing_ok=True)
    print('uninstalled')


def main():
    commands = {'tools': cmd_tools, 'build': cmd_build, 'package': cmd_package,
                'install': cmd_install, 'uninstall': cmd_uninstall}
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=commands)
    parser.add_argument('--game', default=DEFAULT_GAME, help='game install directory')
    args = parser.parse_args()
    commands[args.command](args)


if __name__ == '__main__':
    main()
