"""Synapse: the program you start. Goal 3 gives it the 'atlas load' command."""

from loader import load_atlas

DEFAULT_ATLAS = 'data/atlas.txt'


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
            print('Commands:\n  atlas load <path>\n  help\n  exit')
        elif words[0] == 'atlas' and len(words) >= 2 and words[1] == 'load':
            if len(words) < 3:
                print('ERROR: Missing path. Usage: atlas load <path>')
            else:
                load_command(state, ' '.join(words[2:]))
        else:
            print(f'ERROR: Unknown command "{line.strip()}".')


if __name__ == '__main__':
    main()
