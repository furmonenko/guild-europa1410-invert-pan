# Europa 1410: Inverted Middle-Mouse Pan

A small mod for **The Guild 1 Remake: Europa 1410** that inverts camera panning with the middle mouse button. Instead of following the cursor, the camera now moves the opposite way, so dragging feels like grabbing and pulling the map, as in most strategy games.

Only the middle-mouse drag changes. Keyboard panning (WASD and the arrow keys), rotation and zoom are untouched.

## Install

1. Download `Europa1410-InvertPan-<version>.zip` from [Releases](../../releases).
2. Extract the three files (`ZZ_InvertPan_P.pak`, `.utoc`, `.ucas`) into
   `<game folder>\Europa1410\Content\Paks\~mods\`
   (create the `~mods` folder if it does not exist).

To uninstall, delete those three files.

Tested on game version 0.4.5.25766. The mod replaces the game's input mapping asset (`IMC_Game`), so it conflicts with any other mod that changes key bindings, and a game update that changes the bindings needs a rebuilt mod.

## Build from source

Requires Python 3.10+ on Windows.

```
python build.py tools                      # download pinned repak/retoc
python build.py install --game "<game folder>"
```

`build.py` extracts `IMC_Game` from your copy of the game, adds the existing `InputModifierNegate` modifier to the Mouse2D camera mapping and repacks it. It stops with an error if the asset no longer looks as expected.

## License

MIT
