"""Synapse: the program you start. Commands: atlas load / pipes / areas / show / find."""

import commands
from loader import load_atlas

DEFAULT_ATLAS = 'data/atlas.txt'
ATLAS_USAGE = 'Usage: atlas load <path> | pipes | areas | show <name> | find <word> | tree | path <area>'


def load_command(state, path):
    """Try to load an atlas. If anything is wrong, keep the old one (all or nothing)."""
    try:
        atlas = load_atlas(path)
    except ValueError as error:
        print(f'ERROR: {error}')
        if state['path']:
            print(f'Atlas not loaded. Still using {state["path"]}.')
        else:
            print('Atlas not loaded.')
        return

    state['atlas'] = atlas                    # only now do we replace the old atlas
    state['path'] = path
    print(f'SUCCESS: Atlas loaded from {path}: '
          f'{len(atlas.pipes)} pipes, {len(atlas.areas)} areas.')


def atlas_command(state, args):
    """Handle everything after the word 'atlas'."""
    if not args:
        raise ValueError(f'Missing subcommand. {ATLAS_USAGE}')
    sub, rest = args[0], args[1:]

    if sub == 'load':
        if not rest:
            raise ValueError('Missing path. Usage: atlas load <path>')
        load_command(state, ' '.join(rest))
        return

    if sub not in ('pipes', 'areas', 'show', 'find', 'tree', 'path'):
        raise ValueError(f'Unknown atlas command "{sub}". {ATLAS_USAGE}')
    atlas = state['atlas']
    if atlas is None:
        raise ValueError('No atlas loaded. Use: atlas load <path>')

    if sub == 'pipes':
        commands.show_pipes(atlas)
    elif sub == 'areas':
        commands.show_areas(atlas)
    elif sub == 'tree':
        commands.show_tree(atlas)
    elif sub == 'path':
        if not rest:
            raise ValueError('Missing area. Usage: atlas path <area>')
        commands.show_paths(atlas, ' '.join(rest))
    elif sub == 'show':
        if not rest:
            raise ValueError('Missing name. Usage: atlas show <name>')
        commands.show_one(atlas, ' '.join(rest))
    elif sub == 'find':
        if not rest:
            raise ValueError('Missing word. Usage: atlas find <word>')
        commands.find(atlas, ' '.join(rest))


def main():
    state = {'atlas': None, 'path': None}     # what the program currently remembers
    print('Synapse 1.0 - type "help" to see all commands')
    load_command(state, DEFAULT_ATLAS)        # the atlas loads when the program starts

    while True:
        try:
            line = input('synapse> ')
        except EOFError:
            break
        words = line.split()
        if not words:
            continue

        if words[0] == 'exit':
            break
        elif words[0] == 'help':
            print('Commands:\n  atlas load <path>\n  atlas pipes\n  atlas areas\n'
                  '  atlas show <name>\n  atlas find <word>\n  atlas tree\n  atlas path <area>\n  help\n  exit')
        elif words[0] == 'atlas':
            try:
                atlas_command(state, words[1:])
            except ValueError as error:       # a mistake by the user, not a crash
                print(f'ERROR: {error}')
        else:
            print(f'ERROR: Unknown command "{line.strip()}".')


if __name__ == '__main__':
    main()
